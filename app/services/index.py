"""Hybrid retrieval on Qdrant: dense + BM25, metadata-filtered and unfiltered rankings fused with RRF, then reranked."""
import threading
import time
from pathlib import Path

from fastembed import SparseTextEmbedding, TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
from qdrant_client import QdrantClient, models

from app.core.config import settings
from app.core.constants import COLLECTION
from app.core.logging import get_logger
from app.ingest.chunker import Chunk
from app.services.query_hints import QueryHints, analyze

log = get_logger("services.index")
KEYWORD_FIELDS = ("treatment", "section_type", "page_type", "countries")


class KnowledgeIndex:
    """`COLLECTION` is an alias; each build writes a fresh collection and repoints the alias atomically."""

    def __init__(self, data_dir: Path = settings.DATA_DIR, url: str = settings.QDRANT_URL,
                 rerank_model: str = settings.RERANK_MODEL):
        self.url = url
        self.client = QdrantClient(url=url) if url else QdrantClient(path=str(data_dir / "qdrant"))
        self.dense = TextEmbedding(settings.EMBEDDING_MODEL)
        self.sparse = SparseTextEmbedding(settings.SPARSE_MODEL)
        self.reranker = TextCrossEncoder(rerank_model, threads=settings.RERANK_THREADS) if rerank_model else None
        # NOTE: local-mode Qdrant isn't documented as thread-safe; its calls take milliseconds, so serialise them
        self.lock = threading.RLock()

    # --- lifecycle ---------------------------------------------------------------------------------------------
    def _live_collection(self) -> str | None:
        aliases = self.client.get_aliases().aliases
        return next((a.collection_name for a in aliases if a.alias_name == COLLECTION), None)

    def ready(self) -> bool:
        with self.lock:
            return self._live_collection() is not None

    def count(self) -> int:
        with self.lock:
            return self.client.count(COLLECTION).count if self._live_collection() else 0

    def build(self, chunks: list[Chunk]) -> None:
        """Embed outside the lock, write a new collection, then swap the alias so searches never see a partial index."""
        texts = [c.embed_text for c in chunks]
        # NOTE: small batches keep peak RAM low on a 2 GB box
        dense = list(self.dense.embed(texts, batch_size=16))
        sparse = list(self.sparse.embed(texts, batch_size=16))
        name = f"{COLLECTION}_{time.time_ns()}"
        with self.lock:
            self.client.create_collection(
                name,
                vectors_config={"dense": models.VectorParams(size=len(dense[0]), distance=models.Distance.COSINE)},
                sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
            )
            if self.url:  # NOTE: payload indexes only exist on a Qdrant server; local mode filters by scanning
                for key in KEYWORD_FIELDS:
                    self.client.create_payload_index(name, key, models.PayloadSchemaType.KEYWORD)
                self.client.create_payload_index(name, "has_price", models.PayloadSchemaType.BOOL)
            self.client.upsert(name, [
                models.PointStruct(id=i, payload=c.to_dict(), vector={
                    "dense": d.tolist(),
                    "bm25": models.SparseVector(indices=s.indices.tolist(), values=s.values.tolist())})
                for i, (c, d, s) in enumerate(zip(chunks, dense, sparse))
            ])
            old = self._live_collection()
            if old is None and self.client.collection_exists(COLLECTION):
                self.client.delete_collection(COLLECTION)  # layout before aliases: a plain collection under the name
            ops = [models.CreateAliasOperation(create_alias=models.CreateAlias(collection_name=name, alias_name=COLLECTION))]
            if old:
                ops.insert(0, models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=COLLECTION)))
            self.client.update_collection_aliases(change_aliases_operations=ops)
            for c in self.client.get_collections().collections:
                if c.name.startswith(f"{COLLECTION}_") and c.name != name:
                    self.client.delete_collection(c.name)  # the previous build and any left by a failed one
        log.info(f"index built: {len(chunks)} chunks in {name}")

    # --- search ------------------------------------------------------------------------------------------------
    def _prefetch(self, queries: list[str], limit: int, flt: models.Filter | None) -> list[models.Prefetch]:
        out = []
        for q in queries:
            d = next(iter(self.dense.query_embed(q)))
            s = next(iter(self.sparse.query_embed(q)))
            out += [
                models.Prefetch(query=d.tolist(), using="dense", limit=limit, filter=flt),
                models.Prefetch(query=models.SparseVector(indices=s.indices.tolist(), values=s.values.tolist()),
                                using="bm25", limit=limit, filter=flt),
            ]
        return out

    @staticmethod
    def _filters(hints: QueryHints) -> list[models.Filter]:
        """Narrow rankings that get fused with the unfiltered one, so a wrong hint can boost but never hide."""
        def cond(key, value):
            return models.FieldCondition(key=key, match=models.MatchValue(value=value))
        # NOTE: testimonial-video chunks have cancer-heavy titles; unless videos are asked for, keep them out of
        # the boosted rankings (they still compete in the unfiltered one)
        not_videos = [] if hints.section == "videos" else [cond("section_type", "videos")]
        out = []
        if hints.treatment and hints.section:
            out.append(models.Filter(must=[cond("treatment", hints.treatment), cond("section_type", hints.section)],
                                     must_not=not_videos))
        if hints.treatment:
            out.append(models.Filter(must=[cond("treatment", hints.treatment)], must_not=not_videos))
        elif hints.section:
            out.append(models.Filter(must=[cond("section_type", hints.section)], must_not=not_videos))
        else:
            out.append(models.Filter(must_not=not_videos))
        return out

    def search(self, *queries: str, hints: QueryHints | None = None, top_k: int = settings.TOP_K,
               rerank: bool = True) -> list[Chunk]:
        """queries[0] is the main (router-rewritten) query; others are extra phrasings fused into the same ranking."""
        queries = list(dict.fromkeys(q for q in queries if q))
        use_rerank = rerank and self.reranker is not None
        pool = settings.RERANK_CANDIDATES if use_rerank else top_k
        prefetch = self._prefetch(queries, pool, None)
        for flt in self._filters(hints or QueryHints()) if settings.METADATA_FILTERS else []:
            prefetch += self._prefetch(queries, pool, flt)
        with self.lock:
            res = self.client.query_points(COLLECTION, prefetch=prefetch,
                                           query=models.FusionQuery(fusion=models.Fusion.RRF), limit=pool)
        chunks = [Chunk(**p.payload) for p in res.points]
        if not use_rerank or len(chunks) <= 1:
            return chunks[:top_k]
        return self._blend_rerank(queries[0], chunks)[:top_k]

    def search_many(self, queries: list[str], raw: str = "", top_k: int = settings.TOP_K,
                    max_chunks: int = settings.MAX_CONTEXT_CHUNKS) -> list[Chunk]:
        """One filtered + reranked search per need, interleaved so every part of a multi-part question is covered."""
        queries = [q for q in dict.fromkeys(queries) if q]
        if len(queries) <= 1:
            q = queries[0] if queries else raw
            return self.search(q, raw, hints=analyze(q), top_k=top_k)
        # NOTE: the raw message mixes all parts, so each sub-query searches on its own wording
        per_query = max(3, top_k // len(queries) + 1)
        # NOTE: only the main need is reranked; the rest use the fused ranking (a rerank costs ~0.6 s on 2 vCPUs)
        lists = [self.search(q, hints=analyze(q), top_k=per_query, rerank=i == 0) for i, q in enumerate(queries)]
        merged, seen = [], set()
        for rank in range(per_query):
            for results in lists:
                if rank < len(results) and results[rank].id not in seen:
                    seen.add(results[rank].id)
                    merged.append(results[rank])
        return merged[:max_chunks]

    def _blend_rerank(self, query: str, chunks: list[Chunk], k: int = 10) -> list[Chunk]:
        """RRF of the fused (filter-aware) rank and the cross-encoder rank, so the reranker can't erase filter gains."""
        scores = list(self.reranker.rerank(query, [c.embed_text[:settings.RERANK_MAX_CHARS] for c in chunks]))
        by_score = sorted(range(len(chunks)), key=lambda i: -scores[i])
        rerank_rank = {i: r for r, i in enumerate(by_score, 1)}
        blended = sorted(range(len(chunks)), key=lambda i: -(1 / (k + i + 1) + 1 / (k + rerank_rank[i])))
        return [chunks[i] for i in blended]


if __name__ == "__main__":
    from app.services.query_hints import analyze

    idx = KnowledgeIndex()
    assert idx.ready(), "run `python -m app.ingest --offline` first"
    for q in ["How much does adrenal cancer treatment cost in Mexico?", "Is alternative medicine cheaper in Turkey or Mexico?",
              "What is included in the anal cancer in-patient package?", "recovery time after treatment"]:
        print(f"\n> {q}  {analyze(q)}")
        for c in idx.search(q, hints=analyze(q)):
            print(f"   {c.id:7} {c.treatment:14} {c.section_type:13} | {c.heading[:55]}")

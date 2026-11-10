"""Hybrid (dense + BM25) index on Qdrant local mode, fused with RRF."""
import json
import shutil
from pathlib import Path

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models

from app.core.config import settings
from app.core.constants import COLLECTION
from app.core.logging import get_logger
from app.ingest.chunker import Chunk

log = get_logger("services.index")


class KnowledgeIndex:
    def __init__(self, data_dir: Path = settings.DATA_DIR):
        self.data_dir = data_dir
        self.dense = TextEmbedding(settings.EMBEDDING_MODEL)
        self.sparse = SparseTextEmbedding(settings.SPARSE_MODEL)
        self.client: QdrantClient | None = None
        self.chunks: dict[str, Chunk] = {}

    @property
    def _db_path(self) -> Path:
        return self.data_dir / "qdrant"

    def build(self, chunks: list[Chunk]) -> None:
        """Build into a temp dir, then swap, so a failed rebuild never breaks the live index."""
        tmp = self.data_dir / "qdrant_tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        client = QdrantClient(path=str(tmp))
        dim = len(next(iter(self.dense.embed(["dim"]))))
        client.create_collection(
            COLLECTION,
            vectors_config={"dense": models.VectorParams(size=dim, distance=models.Distance.COSINE)},
            sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )
        texts = [c.embed_text for c in chunks]
        # NOTE: small batches keep peak RAM low on a 2 GB box
        dense = list(self.dense.embed(texts, batch_size=16))
        sparse = list(self.sparse.embed(texts, batch_size=16))
        client.upsert(COLLECTION, [
            models.PointStruct(
                id=i,
                vector={"dense": d.tolist(), "bm25": models.SparseVector(indices=s.indices.tolist(), values=s.values.tolist())},
                payload=c.to_dict(),
            )
            for i, (c, d, s) in enumerate(zip(chunks, dense, sparse))
        ])
        client.close()
        if self.client:
            self.client.close()
        shutil.rmtree(self._db_path, ignore_errors=True)
        tmp.rename(self._db_path)
        (self.data_dir / "chunks.json").write_text(json.dumps([c.to_dict() for c in chunks], indent=1))
        log.info(f"index built: {len(chunks)} chunks")
        self.load()

    def load(self) -> bool:
        if not (self.data_dir / "chunks.json").exists():
            return False
        self.client = QdrantClient(path=str(self._db_path))
        self.chunks = {c["id"]: Chunk(**c) for c in json.loads((self.data_dir / "chunks.json").read_text())}
        return True

    def search(self, *queries: str, top_k: int = settings.TOP_K) -> list[Chunk]:
        """Hybrid search; several phrasings of one question are fused into a single RRF ranking."""
        prefetch = []
        for q in dict.fromkeys(q for q in queries if q):
            d = next(iter(self.dense.query_embed(q)))
            s = next(iter(self.sparse.query_embed(q)))
            prefetch += [
                models.Prefetch(query=d.tolist(), using="dense", limit=top_k * 3),
                models.Prefetch(query=models.SparseVector(indices=s.indices.tolist(), values=s.values.tolist()),
                                using="bm25", limit=top_k * 3),
            ]
        res = self.client.query_points(COLLECTION, prefetch=prefetch,
                                       query=models.FusionQuery(fusion=models.Fusion.RRF), limit=top_k)
        return [self.chunks[p.payload["id"]] for p in res.points]

if __name__ == "__main__":
    idx = KnowledgeIndex()
    assert idx.load(), "run `python -m app.ingest` first"
    for q in ["How much does adrenal cancer treatment cost in Mexico?", "Is alternative medicine cheaper in Turkey or Mexico?",
              "What is included in the anal cancer in-patient package?", "recovery time after treatment", "Do you have patient videos?"]:
        print(f"\n> {q}")
        for c in idx.search(q):
            print(f"   {c.id:7} {c.page_title[:40]:40} | {c.heading[:60]}")

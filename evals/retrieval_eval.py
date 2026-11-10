"""Offline retrieval benchmark: recall@k and MRR over evals/retrieval.yaml (no LLM calls)."""
import argparse
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.ingest.chunker import Chunk  # noqa: E402
from app.services.index import KnowledgeIndex  # noqa: E402
from app.services.query_hints import analyze  # noqa: E402


def is_hit(chunk: Chunk, expect: list[dict]) -> bool:
    return any(e["page"] in chunk.url and e["heading"].lower() in chunk.heading.lower() for e in expect)


def evaluate(index: KnowledgeIndex, cases: list[dict], k: int = 6, verbose: bool = False,
             hints: bool = True, rerank: bool = True) -> dict:
    hits_k, hits_20, rr = 0, 0, 0.0
    for case in cases:
        query = case.get("rewritten", case["q"])
        results = index.search(query, case["q"], hints=analyze(query) if hints else None, top_k=20, rerank=rerank)
        rank = next((i for i, c in enumerate(results, 1) if is_hit(c, case["expect"])), None)
        hits_k += bool(rank and rank <= k)
        hits_20 += bool(rank)
        rr += 1 / rank if rank and rank <= k else 0
        if verbose and not (rank and rank <= k):
            top = " | ".join(f"{c.id} {c.heading[:30]}" for c in results[:3])
            print(f"  MISS (rank {rank}) {case['q'][:60]!r} -> {top}")
    n = len(cases)
    return {"queries": n, f"recall@{k}": round(hits_k / n, 3), "recall@20": round(hits_20 / n, 3),
            f"mrr@{k}": round(rr / n, 3)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", type=int, default=6)
    ap.add_argument("-v", "--verbose", action="store_true", help="print misses")
    a = ap.parse_args()
    idx = KnowledgeIndex()
    assert idx.ready(), "run `python -m app.ingest --offline` first"
    cases = yaml.safe_load((ROOT / "evals/retrieval.yaml").read_text())
    hard = [c for c in cases if c.get("hard")]
    # NOTE: ablation, so each retrieval stage's contribution is visible on its own
    for name, h, r in [("baseline", False, False), ("+filters", True, False), ("+rerank", False, True), ("+both", True, True)]:
        t0 = time.time()
        res_all = evaluate(idx, cases, a.k, a.verbose and name == "+both", hints=h, rerank=r)
        ms = (time.time() - t0) / len(cases) * 1000
        res_hard = evaluate(idx, hard, a.k, hints=h, rerank=r)
        print(f"{name:9} all {res_all}  hard {res_hard}  {ms:.0f} ms/query")

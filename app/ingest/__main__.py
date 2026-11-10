"""`python -m app.ingest`: crawl -> parse -> chunk -> rebuild index."""
import argparse
import hashlib
import json

from app.core.config import SOURCE_PAGES, settings
from app.core.logging import get_logger, setup_logging
from app.ingest.chunker import chunk_pages
from app.ingest.crawler import Crawler
from app.ingest.parser import parse_page

log = get_logger("ingest")


def run_ingest(index=None, offline: bool = False) -> dict:
    """Fetch pages into snapshot/ (or reuse it when offline), rebuild the index if anything changed."""
    from app.services.index import KnowledgeIndex

    raw = settings.SNAPSHOT_DIR
    raw.mkdir(parents=True, exist_ok=True)
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = settings.DATA_DIR / "manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    if offline:
        htmls = [(t, u, (raw / f"{n}_{t}.html").read_text()) for n, (t, u) in enumerate(SOURCE_PAGES, 1)]
    else:
        htmls = [(p.page_type, p.url, p.html) for p in Crawler().fetch_all()]
        for n, (t, _, html) in enumerate(htmls, 1):
            (raw / f"{n}_{t}.html").write_text(html)

    pages = [parse_page(html, url, t) for t, url, html in htmls]
    chunks = chunk_pages(pages)
    # NOTE: hash the parsed chunks, not raw HTML: raw pages change every request (csrf tokens, timestamps)
    new = {p.url: hashlib.sha256("\n".join(json.dumps(c.to_dict(), sort_keys=True) for c in chunks if c.url == p.url)
                                 .encode()).hexdigest() for p in pages}
    changed = [u for u in new if old.get(u) != new[u]]

    index = index or KnowledgeIndex()
    if changed or not index.ready():
        index.build(chunks)
    manifest_path.write_text(json.dumps(new, indent=1))
    log.info(f"ingest done: {len(chunks)} chunks, {len(changed)} pages changed")
    return {"chunks": len(chunks), "pages": len(pages), "changed_pages": changed}


if __name__ == "__main__":
    setup_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="rebuild from snapshot/ without fetching")
    print(run_ingest(offline=ap.parse_args().offline))

"""Polite fetcher for the fixed allowlist of source pages."""
import hashlib
import time
from dataclasses import dataclass
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import SOURCE_PAGES, settings
from app.core.logging import get_logger

log = get_logger("ingest.crawler")


@dataclass
class FetchedPage:
    page_type: str
    url: str
    html: str

    @property
    def sha(self) -> str:
        return hashlib.sha256(self.html.encode()).hexdigest()


class Crawler:
    def __init__(self, pages=SOURCE_PAGES, user_agent: str = settings.USER_AGENT, min_delay: float = settings.CRAWL_DELAY):
        self.pages = pages
        self.user_agent = user_agent
        self.min_delay = min_delay
        self.client = httpx.Client(headers={"User-Agent": user_agent}, timeout=30, follow_redirects=True)

    def _robots(self) -> RobotFileParser:
        rp = RobotFileParser()
        resp = self.client.get("https://www.placidway.com/robots.txt")
        rp.parse(resp.text.splitlines())
        return rp

    def fetch_all(self) -> list[FetchedPage]:
        rp = self._robots()
        delay = max(self.min_delay, float(rp.crawl_delay(self.user_agent) or 0))
        out = []
        for i, (page_type, url) in enumerate(self.pages):
            if not rp.can_fetch(self.user_agent, url):
                log.warning(f"robots.txt disallows {url}, skipping")
                continue
            if i:
                time.sleep(delay)
            resp = self.client.get(url)
            resp.raise_for_status()
            log.info(f"fetched {url} ({len(resp.text) // 1024} KB)")
            out.append(FetchedPage(page_type, url, resp.text))
        return out


if __name__ == "__main__":
    pages = Crawler().fetch_all()
    raw = settings.DATA_DIR / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for n, p in enumerate(pages, 1):
        (raw / f"{n}_{p.page_type}.html").write_text(p.html)
    print(f"saved {len(pages)} pages to {raw}")

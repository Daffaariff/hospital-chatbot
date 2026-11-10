"""Sections -> retrieval chunks with stable, readable ids and filterable metadata."""
from dataclasses import asdict, dataclass, field

from app.core.constants import CHUNK_MAX_CHARS as MAX_CHARS
from app.ingest.parser import ParsedPage
from app.ingest.site_rules import COUNTRIES, PAGE_TOPICS, SECTION_TYPES
from app.services.guards import money_amounts


@dataclass
class Chunk:
    id: str
    url: str
    page_type: str
    page_title: str
    heading: str
    text: str
    treatment: str = "other"        # adenocarcinoma | adrenal | anal | itc | videos | alt_medicine
    section_type: str = "info"      # cost | included | excluded | optional | itinerary | clinic_prices | faq | videos | info
    has_price: bool = False
    countries: list[str] = field(default_factory=list)

    @property
    def embed_text(self) -> str:
        return f"{self.page_title}\n{self.heading}\n{self.text}"

    def to_dict(self) -> dict:
        return asdict(self)


def _split(text: str) -> list[str]:
    """Split on line boundaries so table rows and list items never break."""
    if len(text) <= MAX_CHARS:
        return [text]
    parts, cur = [], ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) > MAX_CHARS:
            parts.append(cur)
            cur = ""
        cur = f"{cur}\n{line}" if cur else line
    return parts + [cur] if cur else parts


def page_topic(url: str) -> str:
    return next((topic for frag, topic in PAGE_TOPICS.items() if frag in url), "other")


def section_type(heading: str, page_type: str) -> str:
    if page_type == "videos":
        return "videos"
    h = heading.lower()
    match = next((kind for key, kind in SECTION_TYPES if key in h), None)
    return match or ("faq" if heading.rstrip().endswith("?") else "info")


def chunk_pages(pages: list[ParsedPage]) -> list[Chunk]:
    chunks = []
    for p_no, page in enumerate(pages, 1):
        n = 0
        for sec in page.sections:
            for part in _split(sec.text):
                n += 1
                full = f"{sec.heading}\n{part}"
                chunks.append(Chunk(
                    id=f"P{p_no}-C{n}", url=page.url, page_type=page.page_type, page_title=page.title,
                    heading=sec.heading, text=part, treatment=page_topic(page.url),
                    section_type=section_type(sec.heading, page.page_type), has_price=bool(money_amounts(full)),
                    countries=[c for c in COUNTRIES if c in full]))
    return chunks


if __name__ == "__main__":
    from collections import Counter

    from app.core.config import SOURCE_PAGES, settings
    from app.ingest.parser import parse_page

    raw = settings.SNAPSHOT_DIR
    pages = [parse_page((raw / f"{n}_{t}.html").read_text(), u, t) for n, (t, u) in enumerate(SOURCE_PAGES, 1)]
    chunks = chunk_pages(pages)
    sizes = [len(c.text) for c in chunks]
    print(f"{len(chunks)} chunks, avg {sum(sizes) // len(sizes)} chars, max {max(sizes)}")
    print("treatment:", dict(Counter(c.treatment for c in chunks)))
    print("section:  ", dict(Counter(c.section_type for c in chunks)))
    print("priced:   ", sum(c.has_price for c in chunks))
    assert all(len(c.text) <= MAX_CHARS + 300 for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)
    assert all(c.treatment != "other" for c in chunks)

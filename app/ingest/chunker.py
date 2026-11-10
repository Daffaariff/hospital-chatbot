"""Sections -> retrieval chunks with stable, readable ids."""
from dataclasses import asdict, dataclass

from app.ingest.parser import ParsedPage

MAX_CHARS = 1500


@dataclass
class Chunk:
    id: str
    url: str
    page_type: str
    page_title: str
    heading: str
    text: str

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


def chunk_pages(pages: list[ParsedPage]) -> list[Chunk]:
    chunks = []
    for p_no, page in enumerate(pages, 1):
        n = 0
        for sec in page.sections:
            for part in _split(sec.text):
                n += 1
                chunks.append(Chunk(f"P{p_no}-C{n}", page.url, page.page_type, page.title, sec.heading, part))
    return chunks


if __name__ == "__main__":
    from app.core.config import SOURCE_PAGES, settings
    from app.ingest.parser import parse_page

    raw = settings.SNAPSHOT_DIR
    pages = [parse_page((raw / f"{n}_{t}.html").read_text(), u, t) for n, (t, u) in enumerate(SOURCE_PAGES, 1)]
    chunks = chunk_pages(pages)
    sizes = [len(c.text) for c in chunks]
    print(f"{len(chunks)} chunks, avg {sum(sizes) // len(sizes)} chars, max {max(sizes)}")
    assert all(len(c.text) <= MAX_CHARS + 300 for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)

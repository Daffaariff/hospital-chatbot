"""HTML -> clean sections (heading + text) per page type."""
import re
from dataclasses import dataclass, field
from html import unescape

from bs4 import BeautifulSoup, Comment, Tag

from app.ingest.site_rules import NOISE, PAGE_RULES

@dataclass
class Section:
    heading: str
    text: str


@dataclass
class ParsedPage:
    url: str
    page_type: str
    title: str
    sections: list[Section] = field(default_factory=list)


def clean(text: str) -> str:
    text = unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def table_to_lines(table: Tag) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = [clean(td.get_text(" ", strip=True)) for td in tr.find_all(["th", "td"])]
        cells = [c for c in cells if c and c.lower() not in {"quote", "get quote", "request quote"}]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)



def split_by_headings(root: Tag, drop_headings: list[str]) -> list[Section]:
    """Walk h2/h3 in document order; text between headings belongs to the previous heading."""
    sections, heading, buf = [], "", []

    def flush():
        txt = clean("\n".join(dict.fromkeys(b for b in buf if b)))
        if txt and not any(d.lower() in heading.lower() for d in drop_headings):
            sections.append(Section(heading, txt))

    for node in root.descendants:
        if not isinstance(node, Tag):
            continue
        if node.name in {"h1", "h2", "h3", "summary"}:  # NOTE: <summary> holds FAQ questions in <details>
            flush()
            heading, buf = clean(node.get_text(" ", strip=True)), []
        elif node.name in {"p", "li", "table", "dd"}:
            if node.find_parent(["table", "li"]) is not None:
                continue
            buf.append(table_to_lines(node) if node.name == "table" else
                       ("- " if node.name == "li" else "") + clean(node.get_text(" ", strip=True)))
    flush()
    return sections


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "lxml")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    return soup


def _title(soup: BeautifulSoup) -> str:
    return clean(soup.title.get_text()) if soup.title else ""


def parse_videos(soup: BeautifulSoup, url: str) -> ParsedPage:
    page = ParsedPage(url, "videos", _title(soup))
    by_cat: dict[str, list[str]] = {}
    for card in soup.select(".related-videos-card"):
        title, link = card.find("h3"), card.select_one("h3 a[href]")
        # NOTE: site class names are swapped: .provider-name holds the category, .subtreatment the clinic
        clinic, cat = card.select_one(".subtreatment"), card.select_one(".provider-name")
        if not title or not clinic or "ITC" not in clinic.get_text():
            continue
        href = link["href"] if link else ""
        href = f"https://www.placidway.com{href}" if href.startswith("/") else href
        line = f"- {clean(title.get_text(' ', strip=True))}" + (f" ({href})" if href else "")
        by_cat.setdefault((clean(cat.get_text(" ", strip=True)) if cat else "") or "Other", []).append(line)
    for cat, lines in by_cat.items():
        lines = list(dict.fromkeys(lines))
        for i in range(0, len(lines), 12):
            page.sections.append(Section(f"ITC clinic videos: {cat}", "\n".join(lines[i:i + 12])))
    return page


def parse_page(html: str, url: str, page_type: str) -> ParsedPage:
    soup = _soup(html)
    if page_type == "videos":
        return parse_videos(soup, url)
    rules = PAGE_RULES[page_type]
    page = ParsedPage(url, page_type, _title(soup))
    if page_type == "price_comparison":
        summary = next((p for p in soup.select("p.desc") if "on average" in p.get_text()), None)
        if summary:
            page.sections.append(Section("Overview: Alternative Medicine cost abroad", clean(summary.get_text(" ", strip=True))))
    roots = [el for sel in rules["keep"] for el in soup.select(sel)]
    for root in roots:
        for sel in NOISE:
            for el in root.select(sel):
                el.decompose()
        page.sections += split_by_headings(root, rules["drop_headings"])
    page.sections = [s for s in page.sections if len(s.text) > 20]
    return page



if __name__ == "__main__":
    from app.core.config import SOURCE_PAGES, settings

    raw = settings.SNAPSHOT_DIR
    for n, (ptype, url) in enumerate(SOURCE_PAGES, 1):
        p = parse_page((raw / f"{n}_{ptype}.html").read_text(), url, ptype)
        print(f"\n######## {n} {ptype} | {p.title} | {len(p.sections)} sections, {sum(len(s.text) for s in p.sections)} chars")
        for s in p.sections:
            print(f"  ## {s.heading[:80]}  ({len(s.text)})")

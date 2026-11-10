from pathlib import Path

from app.ingest.chunker import MAX_CHARS, chunk_pages
from app.ingest.parser import parse_page
from app.services.guards import money_amounts

FIX = Path(__file__).parent / "fixtures"


def _page(name, ptype):
    return parse_page((FIX / f"{name}.html").read_text(), f"https://example/{name}", ptype)


def test_package_price_table_kept_as_rows():
    text = "\n".join(s.text for s in _page("package", "package").sections)
    assert "Out-Patient Program | 3 Weeks | $18,995" in text
    assert "In-Patient Program | 3 Weeks | $30,000" in text


def test_promo_cards_and_reviews_stripped():
    # NOTE: raw HTML also holds other clinics' promo prices (e.g. $33,400, $24,000, $7,800); only page facts may survive
    expected = {"package": {200, 300, 462, 950, 2600, 3800, 3950, 4250, 4650, 6200, 7200, 18995, 30000},
                "clinic_profile": {18995}, "price_list": {18995}}
    for name, amounts in expected.items():
        page = _page(name, name)
        text = "\n".join(s.text for s in page.sections)
        assert money_amounts(text) == amounts, name
        assert "Guest P" not in text


def test_comparison_has_overview_and_clinics():
    page = _page("price_comparison", "price_comparison")
    text = "\n".join(s.text for s in page.sections)
    assert "on average" in page.sections[0].text
    for country in ("Turkey", "Mexico", "Thailand"):
        assert country in text


def test_chunks_respect_size_and_unique_ids():
    chunks = chunk_pages([_page("package", "package"), _page("price_list", "price_list")])
    assert len({c.id for c in chunks}) == len(chunks)
    assert all(len(c.text) <= MAX_CHARS + 300 for c in chunks)

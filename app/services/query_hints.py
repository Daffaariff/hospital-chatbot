"""Derive retrieval filters (treatment, section type) from the router's English query."""
import re
from dataclasses import dataclass
from difflib import get_close_matches

from app.ingest.site_rules import SECTION_TERMS, TREATMENT_TERMS

_WORD = re.compile(r"[a-z]+")


@dataclass(frozen=True)
class QueryHints:
    treatment: str | None = None
    section: str | None = None

    def __bool__(self) -> bool:
        return bool(self.treatment or self.section)


def analyze(query: str) -> QueryHints:
    q = query.lower()
    treatment = None
    for word in _WORD.findall(q):
        term = word if word in TREATMENT_TERMS else None
        if not term and len(word) >= 6:
            # NOTE: fuzzy only for longer words, so typos like "adrenl" match but "analysis" never becomes "anal"
            close = get_close_matches(word, TREATMENT_TERMS, n=1, cutoff=0.85)
            term = close[0] if close else None
        if term:
            treatment = TREATMENT_TERMS[term]
            break
    section = next((kind for phrase, kind in SECTION_TERMS if phrase in q), None)
    return QueryHints(treatment, section)


if __name__ == "__main__":
    assert analyze("What is the price of the adenocarcinoma package?") == QueryHints("adenocarcinoma", "cost")
    assert analyze("adrenl cancer price") == QueryHints("adrenal", "cost")
    assert analyze("What extra costs are not covered for anal cancer?") == QueryHints("anal", "excluded")
    assert analyze("Is the staff bilingual?") == QueryHints()
    assert analyze("analysis of results") == QueryHints()
    assert analyze("Which clinic in Turkey has the cheapest ozone therapy?").section == "clinic_prices"
    print("query hints ok")

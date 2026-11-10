from app.ingest.chunker import Chunk, section_type
from app.services.index import KnowledgeIndex
from app.services.query_hints import QueryHints, analyze


def test_section_types_from_headings():
    assert section_type("Cost of Adrenal Cancer Treatment in Tijuana, Mexico", "package") == "cost"
    assert section_type("Included in the In-Patient Program ($30,000 USD)", "package") == "included"
    assert section_type("Excluded Services and Contingency Costs", "package") == "excluded"
    assert section_type("5. Why is the treatment period three weeks?", "package") == "faq"
    assert section_type("anything", "videos") == "videos"


def test_hints_never_filter_alone():
    # a filtered ranking is always fused with the unfiltered one, so a wrong hint can't hide the right chunk
    flts = KnowledgeIndex._filters(QueryHints("adrenal", "cost"))
    assert len(flts) == 2 and all(f.must for f in flts)
    assert KnowledgeIndex._filters(QueryHints()) == []


def test_query_hints_examples():
    assert analyze("Is a CT scan not included for anal cancer?") == QueryHints("anal", "excluded")
    assert analyze("adrenl cancer price").treatment == "adrenal"

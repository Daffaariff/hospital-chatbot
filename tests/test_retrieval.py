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
    # filtered rankings are fused with the unfiltered one, so a wrong hint can't hide the right chunk
    flts = KnowledgeIndex._filters(QueryHints("adrenal", "cost"))
    assert len(flts) == 2 and all(f.must and f.must_not for f in flts)
    no_hint = KnowledgeIndex._filters(QueryHints())
    assert len(no_hint) == 1 and no_hint[0].must_not and not no_hint[0].must  # only demotes videos
    assert not KnowledgeIndex._filters(QueryHints(section="videos"))[0].must_not  # videos asked for: keep them


def test_query_hints_examples():
    assert analyze("Is a CT scan not included for anal cancer?") == QueryHints("anal", "excluded")
    assert analyze("adrenl cancer price").treatment == "adrenal"


def test_search_many_interleaves_parts():
    class Stub(KnowledgeIndex):
        def __init__(self):
            pass

        def search(self, *queries, hints=None, top_k=6, rerank=True):
            q = queries[0]
            return [Chunk(f"{q}-{i}", "u", "package", "t", "h", "x") for i in range(top_k)]
    out = Stub().search_many(["price", "included", "duration"], "raw", top_k=6, max_chunks=8)
    ids = [c.id for c in out]
    assert ids[:3] == ["price-0", "included-0", "duration-0"] and len(ids) == 8

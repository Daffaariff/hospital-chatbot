from app.ingest.chunker import Chunk
from app.schemas.chat import AnswerOut, ChatMessage, ChatRequest, RouterOut
from app.services.chat_service import ChatService, _alternate

PRICE = Chunk("P2-C3", "https://x/adrenal", "package", "Adrenal Cancer Treatment in Tijuana", "Cost",
              "Out-Patient Program | 3 Weeks | $18,995\nIn-Patient Program | 3 Weeks | $30,000")


class FakeLLM:
    def __init__(self, route, answers):
        self.route, self.answers, self.calls = route, list(answers), 0

    def complete_structured(self, *, model, system, messages, schema, effort="medium"):
        self.calls += 1
        return self.route if schema is RouterOut else self.answers.pop(0)


class FakeIndex:
    chunks = {PRICE.id: PRICE}

    def search(self, *queries, top_k=6):
        return [PRICE]


class FakeStore:
    def __init__(self):
        self.unanswered = []

    def log_unanswered(self, *a):
        self.unanswered.append(a)


def _svc(route, answers):
    return ChatService(FakeLLM(route, answers), FakeIndex(), FakeStore())


def _route(intent="price", reply=""):
    return RouterOut(standalone_query="adrenal cost", intent=intent, language="English", direct_reply=reply)


def test_grounded_price_answer_cites_page():
    svc = _svc(_route(), [AnswerOut(answerable=True, answer="Out-Patient: $18,995 USD for 3 weeks.", cited_ids=["P2-C3"], medical_topic=False)])
    r = svc.answer(ChatRequest(message="How much is adrenal treatment?"))
    assert r.answered and r.sources[0].url == "https://x/adrenal"


def test_invented_price_is_retried_then_refused():
    bad = AnswerOut(answerable=True, answer="It costs $9,999.", cited_ids=["P2-C3"], medical_topic=False)
    svc = _svc(_route(), [bad, bad])
    r = svc.answer(ChatRequest(message="How much?"))
    assert not r.answered and "$9,999" not in r.answer and svc.llm.calls == 3
    assert svc.store.unanswered


def test_user_wrong_price_can_be_quoted_back():
    ok = AnswerOut(answerable=True, answer="It is not $50; the page lists $18,995.", cited_ids=["P2-C3"], medical_topic=False)
    r = _svc(_route(), [ok]).answer(ChatRequest(message="I heard it costs $50. Confirm that."))
    assert r.answered


def test_uncited_answer_rejected():
    a = AnswerOut(answerable=True, answer="Yes.", cited_ids=["MADE-UP"], medical_topic=False)
    assert not _svc(_route(), [a, a]).answer(ChatRequest(message="q")).answered


def test_booking_skips_retrieval_and_offers_lead_form():
    svc = _svc(_route("booking", "I can't book appointments."), [])
    r = svc.answer(ChatRequest(message="Book me tomorrow"))
    assert r.show_lead_form and svc.llm.calls == 1


def test_disclaimer_only_once():
    a = AnswerOut(answerable=True, answer="ITC offers immunotherapy.", cited_ids=["P2-C3"], medical_topic=True)
    first = _svc(_route("info"), [a]).answer(ChatRequest(message="what therapies?"))
    assert "not medical advice" in first.answer
    hist = [ChatMessage(role="user", content="what therapies?"), ChatMessage(role="assistant", content=first.answer)]
    second = _svc(_route("info"), [a]).answer(ChatRequest(message="more?", history=hist))
    assert "not medical advice" not in second.answer


def test_alternate_fixes_history_shape():
    h = [{"role": "assistant", "content": "hi"}, {"role": "user", "content": "a"}, {"role": "user", "content": "b"},
         {"role": "assistant", "content": "c"}, {"role": "user", "content": "dangling"}]
    assert [m["role"] for m in _alternate(h)] == ["user", "assistant"]


def test_price_in_section_heading_counts_as_evidence():
    inpatient = Chunk("P4-C5", "https://x/anal", "package", "Anal Cancer Treatment", "Included in the In-Patient Program ($30,000 USD)",
                      "- 24/7 medical supervision\n- Full room and board")
    svc = _svc(_route("info"), [AnswerOut(answerable=True, answer="The In-Patient program costs $30,000 USD.", cited_ids=["P4-C5"], medical_topic=False)])
    svc.index.chunks = {inpatient.id: inpatient}
    svc.index.search = lambda *q, top_k=6: [inpatient]
    assert svc.answer(ChatRequest(message="What is in the in-patient package?")).answered


def test_not_found_keeps_related_source():
    a = AnswerOut(answerable=False, answer="Our pages don't state a recovery time.", cited_ids=["P2-C3"], medical_topic=False)
    r = _svc(_route("info"), [a]).answer(ChatRequest(message="recovery time?"))
    assert not r.answered and r.sources[0].url == "https://x/adrenal" and r.show_lead_form

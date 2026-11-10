from app.ingest.chunker import Chunk
from app.schemas.chat import AnswerOut, ChatMessage, ChatRequest, ClaimCheck, ClaimVerdict, RouterOut
from app.services.chat_service import ChatService, _alternate

PRICE = Chunk("P2-C3", "https://x/adrenal", "package", "Adrenal Cancer Treatment in Tijuana", "Cost",
              "Out-Patient Program | 3 Weeks | $18,995\nIn-Patient Program | 3 Weeks | $30,000")


class FakeLLM:
    def __init__(self, route, answers, claims=()):
        self.route, self.answers, self.claims, self.calls = route, list(answers), list(claims), 0

    def complete_structured(self, *, model, system, messages, schema, effort="medium"):
        self.calls += 1
        if schema is RouterOut:
            return self.route
        if schema is ClaimCheck:
            c = self.claims.pop(0) if self.claims else []
            if isinstance(c, Exception):
                raise c
            return ClaimCheck(claims=[ClaimVerdict(claim=x, supported=False) for x in c] + [ClaimVerdict(claim="ok", supported=True)])
        return self.answers.pop(0)

    def stream_structured(self, *, model, system, messages, schema, effort="medium"):
        self.calls += 1
        raw = self.answers.pop(0).model_dump_json()
        for i in range(0, len(raw), 7):
            yield raw[i:i + 7]


class FakeIndex:
    chunks = {PRICE.id: PRICE}

    def search(self, *queries, top_k=6):
        return [PRICE]


class FakeStore:
    def __init__(self):
        self.unanswered = []

    def log_unanswered(self, *a):
        self.unanswered.append(a)


def _svc(route, answers, claims=()):
    return ChatService(FakeLLM(route, answers, claims), FakeIndex(), FakeStore())


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


def test_invented_duration_is_rejected():
    bad = AnswerOut(answerable=True, answer="It is a 2-week program with an 85% success rate.", cited_ids=["P2-C3"], medical_topic=False)
    r = _svc(_route(), [bad, bad]).answer(ChatRequest(message="How long is it?"))
    assert not r.answered and "85%" not in r.answer


def test_unsupported_claim_retried_then_accepted():
    bad = AnswerOut(answerable=True, answer="ITC is JCI accredited and costs $18,995.", cited_ids=["P2-C3"], medical_topic=False)
    good = AnswerOut(answerable=True, answer="The Out-Patient program costs $18,995.", cited_ids=["P2-C3"], medical_topic=False)
    svc = _svc(_route(), [bad, good], claims=[["ITC is JCI accredited"], []])
    r = svc.answer(ChatRequest(message="Tell me about ITC"))
    assert r.answered and "JCI" not in r.answer and svc.llm.calls == 5


def test_claim_check_outage_fails_open():
    ok = AnswerOut(answerable=True, answer="The Out-Patient program costs $18,995.", cited_ids=["P2-C3"], medical_topic=False)
    assert _svc(_route(), [ok], claims=[RuntimeError("api down")]).answer(ChatRequest(message="cost?")).answered


def _events(svc, msg):
    return list(svc.stream(ChatRequest(message=msg)))


def test_stream_sends_sentences_then_final():
    a = AnswerOut(answerable=True, cited_ids=["P2-C3"], medical_topic=False,
                  answer="The Out-Patient program is 3 weeks. It costs $18,995.")
    ev = _events(_svc(_route(), [a]), "cost?")
    deltas = "".join(e["text"] for e in ev if e["type"] == "delta")
    assert deltas == a.answer and ev[-1]["type"] == "final" and ev[-1]["response"].answered


def test_stream_never_shows_invented_number():
    bad = AnswerOut(answerable=True, cited_ids=["P2-C3"], medical_topic=False,
                    answer="The program is 3 weeks. It costs $9,999 in total.")
    ev = _events(_svc(_route(), [bad, bad]), "cost?")
    shown = "".join(e["text"] for e in ev if e["type"] == "delta")
    assert "$9,999" not in shown
    assert any(e["type"] == "reset" for e in ev)  # first sentence was shown, then withdrawn
    assert not ev[-1]["response"].answered

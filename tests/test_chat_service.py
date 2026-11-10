import asyncio

from app.adapters.limited import LimitedLLM
from app.ingest.chunker import Chunk
from app.schemas.chat import AnswerOut, ChatMessage, ChatRequest, ClaimCheck, ClaimVerdict, RouterOut
from app.services.chat_service import ChatService, _alternate

PRICE = Chunk("P2-C3", "https://x/adrenal", "package", "Adrenal Cancer Treatment in Tijuana", "Cost",
              "Out-Patient Program | 3 Weeks | $18,995\nIn-Patient Program | 3 Weeks | $30,000")


class FakeLLM:
    def __init__(self, route, answers, claims=()):
        self.route, self.answers, self.claims, self.calls, self.closed = route, list(answers), list(claims), 0, False

    async def complete_structured(self, *, model, system, messages, schema, effort="medium"):
        self.calls += 1
        if schema is RouterOut:
            return self.route
        if schema is ClaimCheck:
            c = self.claims.pop(0) if self.claims else []
            if isinstance(c, Exception):
                raise c
            return ClaimCheck(claims=[ClaimVerdict(claim=x, supported=False) for x in c] + [ClaimVerdict(claim="ok", supported=True)])
        return self.answers.pop(0)

    async def stream_structured(self, *, model, system, messages, schema, effort="medium"):
        self.calls += 1
        raw = self.answers.pop(0).model_dump_json()
        try:
            for i in range(0, len(raw), 7):
                self.sent = i + 7
                yield raw[i:i + 7]
        finally:
            self.closed, self.total = True, len(raw)


class FakeIndex:
    def search_many(self, queries, raw="", top_k=6, max_chunks=8):
        return [PRICE]


class FakeStore:
    def __init__(self):
        self.unanswered = []

    def log_unanswered(self, *a):
        self.unanswered.append(a)


class SvcForTest(ChatService):
    def ask(self, req):
        return asyncio.run(self.answer(req))


def _svc(route, answers, claims=()):
    return SvcForTest(FakeLLM(route, answers, claims), FakeIndex(), FakeStore())


def _route(intent="price", reply="", considering=False):
    return RouterOut(need="adrenal cost", standalone_query="adrenal cost", extra_queries=[], assumption="",
                     intent=intent, considering_treatment=considering, language="English", direct_reply=reply)


def test_grounded_price_answer_cites_page():
    svc = _svc(_route(), [AnswerOut(followups=[], answerable=True, answer="Out-Patient: $18,995 USD for 3 weeks.", cited_ids=["P2-C3"], medical_topic=False)])
    r = svc.ask(ChatRequest(message="How much is adrenal treatment?"))
    assert r.answered and r.sources[0].url == "https://x/adrenal"


def test_invented_price_is_retried_then_refused():
    bad = AnswerOut(followups=[], answerable=True, answer="It costs $9,999.", cited_ids=["P2-C3"], medical_topic=False)
    svc = _svc(_route(), [bad, bad])
    r = svc.ask(ChatRequest(message="How much?"))
    assert not r.answered and "$9,999" not in r.answer and svc.llm.calls == 3
    assert svc.store.unanswered


def test_user_wrong_price_can_be_quoted_back():
    ok = AnswerOut(followups=[], answerable=True, answer="It is not $50; the page lists $18,995.", cited_ids=["P2-C3"], medical_topic=False)
    r = _svc(_route(), [ok]).ask(ChatRequest(message="I heard it costs $50. Confirm that."))
    assert r.answered


def test_uncited_answer_rejected():
    a = AnswerOut(followups=[], answerable=True, answer="Yes.", cited_ids=["MADE-UP"], medical_topic=False)
    assert not _svc(_route(), [a, a]).ask(ChatRequest(message="q")).answered


def test_booking_skips_retrieval_and_offers_lead_form():
    svc = _svc(_route("booking", "I can't book appointments."), [])
    r = svc.ask(ChatRequest(message="Book me tomorrow"))
    assert r.show_lead_form and svc.llm.calls == 1


def test_disclaimer_only_once():
    a = AnswerOut(followups=[], answerable=True, answer="ITC offers immunotherapy.", cited_ids=["P2-C3"], medical_topic=True)
    first = _svc(_route("info"), [a]).ask(ChatRequest(message="what therapies?"))
    assert "not medical advice" in first.answer
    hist = [ChatMessage(role="user", content="what therapies?"), ChatMessage(role="assistant", content=first.answer)]
    second = _svc(_route("info"), [a]).ask(ChatRequest(message="more?", history=hist))
    assert "not medical advice" not in second.answer


def test_alternate_fixes_history_shape():
    h = [{"role": "assistant", "content": "hi"}, {"role": "user", "content": "a"}, {"role": "user", "content": "b"},
         {"role": "assistant", "content": "c"}, {"role": "user", "content": "dangling"}]
    assert [m["role"] for m in _alternate(h)] == ["user", "assistant"]


def test_price_in_section_heading_counts_as_evidence():
    inpatient = Chunk("P4-C5", "https://x/anal", "package", "Anal Cancer Treatment", "Included in the In-Patient Program ($30,000 USD)",
                      "- 24/7 medical supervision\n- Full room and board")
    svc = _svc(_route("info"), [AnswerOut(followups=[], answerable=True, answer="The In-Patient program costs $30,000 USD.", cited_ids=["P4-C5"], medical_topic=False)])
    svc.index.search_many = lambda *q, **kw: [inpatient]
    assert svc.ask(ChatRequest(message="What is in the in-patient package?")).answered


def test_not_found_keeps_related_source():
    a = AnswerOut(followups=[], answerable=False, answer="Our pages don't state a recovery time.", cited_ids=["P2-C3"], medical_topic=False)
    r = _svc(_route("info"), [a]).ask(ChatRequest(message="recovery time?"))
    assert not r.answered and r.sources[0].url == "https://x/adrenal" and r.show_lead_form


def test_invented_duration_is_rejected():
    bad = AnswerOut(followups=[], answerable=True, answer="It is a 2-week program with an 85% success rate.", cited_ids=["P2-C3"], medical_topic=False)
    r = _svc(_route(), [bad, bad]).ask(ChatRequest(message="How long is it?"))
    assert not r.answered and "85%" not in r.answer


def test_unsupported_claim_retried_then_accepted():
    bad = AnswerOut(followups=[], answerable=True, answer="ITC is JCI accredited and costs $18,995.", cited_ids=["P2-C3"], medical_topic=False)
    good = AnswerOut(followups=[], answerable=True, answer="The Out-Patient program costs $18,995.", cited_ids=["P2-C3"], medical_topic=False)
    svc = _svc(_route(), [bad, good], claims=[["ITC is JCI accredited"], []])
    r = svc.ask(ChatRequest(message="Tell me about ITC"))
    assert r.answered and "JCI" not in r.answer and svc.llm.calls == 5


def test_claim_check_outage_fails_open():
    ok = AnswerOut(followups=[], answerable=True, answer="The Out-Patient program costs $18,995.", cited_ids=["P2-C3"], medical_topic=False)
    assert _svc(_route(), [ok], claims=[RuntimeError("api down")]).ask(ChatRequest(message="cost?")).answered


def _events(svc, msg):
    async def collect():
        return [e async for e in svc.stream(ChatRequest(message=msg))]
    return asyncio.run(collect())


def test_stream_sends_sentences_then_final():
    a = AnswerOut(followups=[], answerable=True, cited_ids=["P2-C3"], medical_topic=False,
                  answer="The Out-Patient program is 3 weeks. It costs $18,995.")
    ev = _events(_svc(_route(), [a]), "cost?")
    deltas = "".join(e["text"] for e in ev if e["type"] == "delta")
    assert deltas == a.answer and ev[-1]["type"] == "final" and ev[-1]["response"].answered


def test_stream_never_shows_invented_number():
    bad = AnswerOut(followups=[], answerable=True, cited_ids=["P2-C3"], medical_topic=False,
                    answer="The program is 3 weeks. It costs $9,999 in total.")
    ev = _events(_svc(_route(), [bad, bad]), "cost?")
    shown = "".join(e["text"] for e in ev if e["type"] == "delta")
    assert "$9,999" not in shown
    assert any(e["type"] == "reset" for e in ev)  # first sentence was shown, then withdrawn
    assert not ev[-1]["response"].answered


def test_leaving_mid_answer_closes_the_llm_stream():
    a = AnswerOut(followups=[], answerable=True, cited_ids=["P2-C3"], medical_topic=False,
                  answer="The Out-Patient program is 3 weeks. It costs $18,995. It includes daily care.")
    svc = _svc(_route(), [a])

    async def leave_after_first_sentence():
        events = svc.stream(ChatRequest(message="cost?"))
        async for e in events:
            if e["type"] == "delta":
                break
        await events.aclose()  # what the WebSocket handler does when the user disconnects
    asyncio.run(leave_after_first_sentence())
    assert svc.llm.closed and svc.llm.sent < svc.llm.total  # stopped early, not run to the end


def test_limited_llm_caps_concurrency():
    class Slow:
        running = peak = 0

        async def complete_structured(self, **kw):
            Slow.running += 1
            Slow.peak = max(Slow.peak, Slow.running)
            await asyncio.sleep(0.01)
            Slow.running -= 1
            return "ok"

    async def burst():
        llm = LimitedLLM(Slow(), max_concurrency=3)
        await asyncio.gather(*(llm.complete_structured(model="m") for _ in range(10)))
    asyncio.run(burst())
    assert Slow.peak == 3


def test_lead_form_for_someone_considering_treatment():
    a = AnswerOut(followups=[], answerable=True, cited_ids=["P2-C3"], medical_topic=True, answer="ITC treats adrenal cancer.")
    assert _svc(_route("info", considering=True), [a]).ask(ChatRequest(message="my dad has adrenal cancer")).show_lead_form
    assert not _svc(_route("info"), [a]).ask(ChatRequest(message="what therapies?")).show_lead_form

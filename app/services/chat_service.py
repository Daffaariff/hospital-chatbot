"""Grounded answer pipeline: route -> retrieve -> stream answer (checked per sentence) -> final guards."""
from collections.abc import Generator, Iterator

from pydantic import ValidationError

from app.adapters.protocols import LLMPort, LLMRefusal
from app.core.config import settings
from app.core.logging import get_logger
from app.ingest.chunker import Chunk
from app.core.constants import LEAD_INTENTS, NO_RETRIEVAL_INTENTS, PRICE_INTENTS
from app.helpers.json_text import extract_json
from app.core.messages import DISCLAIMER, NOT_FOUND, SOURCE_CONTACT, SOURCE_QUOTE, STATUS_CHECKING, STATUS_SEARCHING
from app.prompts.system_prompts import (ANSWER_SYSTEM, CLAIM_CHECK_SYSTEM, PLACIDWAY_FACTS, RETRY_NOTE, ROUTER_SYSTEM,
                                       VOICE_STYLE)
from app.schemas.chat import AnswerOut, ChatRequest, ChatResponse, ClaimCheck, RouterOut, Source
from app.services.guards import unsupported_facts, valid_citations
from app.services.index import KnowledgeIndex
from app.services.store import Store
from app.services.streaming import JsonFieldStream, SentenceBuffer

log = get_logger("services.chat")

# Events: {"type": "status", "text"} · {"type": "delta", "text"} · {"type": "reset"} · {"type": "final", "response"}
Event = dict


def _pick(table: dict[str, str], language: str) -> str:
    return table.get(language.split()[0].capitalize(), table["English"])


def _alternate(history: list[dict]) -> list[dict]:
    """Claude needs user/assistant turns that alternate, start with user and end with assistant."""
    out: list[dict] = []
    for m in history:
        if not out and m["role"] != "user":
            continue
        if out and out[-1]["role"] == m["role"]:
            out[-1] = {**out[-1], "content": out[-1]["content"] + "\n" + m["content"]}
        else:
            out.append(dict(m))
    return out[:-1] if out and out[-1]["role"] == "user" else out


class ChatService:
    def __init__(self, llm: LLMPort, index: KnowledgeIndex, store: Store):
        self.llm, self.index, self.store = llm, index, store

    def answer(self, req: ChatRequest) -> ChatResponse:
        """Non-streaming entry point: same pipeline, returns the final response."""
        for event in self.stream(req):
            if event["type"] == "final":
                return event["response"]
        raise RuntimeError("pipeline ended without a final event")

    def stream(self, req: ChatRequest) -> Iterator[Event]:
        history = _alternate([m.model_dump() for m in req.history[-settings.HISTORY_TURNS * 2:]])
        route = self._route(history, req.message)
        log.info(f"intent={route.intent} lang={route.language} query={route.standalone_query!r}")

        if route.intent in NO_RETRIEVAL_INTENTS:
            lead = route.intent in LEAD_INTENTS
            yield {"type": "final", "response": ChatResponse(
                answer=route.direct_reply or _pick(NOT_FOUND, route.language), answered=True, intent=route.intent,
                show_lead_form=lead, sources=[Source(title=SOURCE_CONTACT, url=settings.QUOTE_URL)] if lead else [])}
            return

        yield {"type": "status", "text": STATUS_SEARCHING}
        chunks = self.index.search(route.standalone_query, req.message)
        out, problem = yield from self._grounded_answer(req, history, route, chunks)
        yield {"type": "final", "response": self._finish(req, route, chunks, out, problem)}

    def _finish(self, req: ChatRequest, route: RouterOut, chunks: list[Chunk], out: AnswerOut | None,
                problem: str | None) -> ChatResponse:
        by_id = {c.id: c for c in chunks}
        quote = Source(title=SOURCE_QUOTE, url=settings.QUOTE_URL)
        if problem:
            self.store.log_unanswered(req.message, route.standalone_query, problem)
            return ChatResponse(answer=_pick(NOT_FOUND, route.language), answered=False, intent=route.intent,
                                show_lead_form=True, sources=[quote])
        cited = [by_id[i] for i in valid_citations(out.cited_ids, set(by_id))]
        sources = list({c.url: Source(title=c.page_title, url=c.url) for c in cited}.values())
        if not out.answerable:
            # NOTE: a "not on our pages" reply may still point to the closest related page
            self.store.log_unanswered(req.message, route.standalone_query, "not in content")
            return ChatResponse(answer=out.answer or _pick(NOT_FOUND, route.language), answered=False,
                                intent=route.intent, show_lead_form=True, sources=[*sources, quote])
        answer = out.answer
        if (out.medical_topic or route.intent == "medical_advice") and not self._disclaimer_shown(req):
            answer += "\n\n_" + _pick(DISCLAIMER, route.language) + "_"
        return ChatResponse(answer=answer, sources=sources, answered=True, intent=route.intent,
                            show_lead_form=route.intent in PRICE_INTENTS)

    def _route(self, history: list[dict], message: str) -> RouterOut:
        convo = "\n".join(f"{m['role']}: {m['content'][:1500]}" for m in history)
        prompt = f"<conversation>\n{convo}\n</conversation>\n<latest_user_message>\n{message}\n</latest_user_message>"
        return self.llm.complete_structured(model=settings.ROUTER_MODEL, system=ROUTER_SYSTEM,
                                            messages=[{"role": "user", "content": prompt}], schema=RouterOut, effort="low")

    def _grounded_answer(self, req: ChatRequest, history: list[dict], route: RouterOut,
                         chunks: list[Chunk]) -> Generator[Event, None, tuple[AnswerOut | None, str | None]]:
        """Stream the answer sentence by sentence, verify it, retry once with the reason. Returns (answer, problem)."""
        if not chunks:
            return None, "no chunks retrieved"
        context = "\n".join(f'<chunk id="{c.id}" page="{c.page_title}" section="{c.heading}">\n{c.text}\n</chunk>' for c in chunks)
        system = ANSWER_SYSTEM.format(language=route.language) + (VOICE_STYLE if req.channel == "voice" else "")
        user = (f"<context>\n{context}\n</context>\n<search_query>{route.standalone_query}</search_query>\n"
                f"<question>\n{req.message}\n</question>")
        by_id = {c.id: c for c in chunks}
        # NOTE: numbers the user typed are allowed so "$50 is not correct" passes the check
        context_evidence = [c.embed_text for c in chunks] + [req.message]
        out, problem = None, None
        for _ in range(2):
            messages = [*history, {"role": "user", "content": user}]
            raw, shown, problem = "", False, None
            field, sentences = JsonFieldStream(), SentenceBuffer()
            stream = self.llm.stream_structured(model=settings.ANSWER_MODEL, system=system, messages=messages,
                                                schema=AnswerOut, effort="medium")
            try:
                for delta in stream:
                    raw += delta
                    for piece in sentences.push(field.feed(delta)):
                        # NOTE: a sentence is only shown after its numbers are found in the retrieved context
                        if bad := unsupported_facts(piece, context_evidence):
                            problem = f"numbers not found in the context: {bad}"
                            break
                        shown = True
                        yield {"type": "delta", "text": piece}
                    if problem:
                        break
            except LLMRefusal as e:
                problem = f"refusal: {e}"
            finally:
                stream.close()

            if not problem:
                for piece in sentences.flush():
                    if bad := unsupported_facts(piece, context_evidence):
                        problem = f"numbers not found in the context: {bad}"
                    else:
                        shown = True
                        yield {"type": "delta", "text": piece}
            if not problem:
                try:
                    out = AnswerOut.model_validate_json(extract_json(raw))
                except ValidationError:
                    problem = "model output was not valid JSON"
            if not problem:
                yield {"type": "status", "text": STATUS_CHECKING}
                problem = self._check(req, out, by_id)
            if not problem:
                return out, None

            log.warning(f"guard rejected answer: {problem}")
            if shown:
                yield {"type": "reset"}
            if problem.startswith("refusal"):
                return None, problem
            user = f"{user}\n\n{RETRY_NOTE.format(problem=problem)}"
        return out, problem

    def _check(self, req: ChatRequest, out: AnswerOut, by_id: dict[str, Chunk]) -> str | None:
        """Final checks on the complete answer against the chunks it cites."""
        cited = valid_citations(out.cited_ids, set(by_id))
        evidence = [by_id[i].embed_text for i in cited]  # page title + heading + text
        bad = unsupported_facts(out.answer, evidence + [req.message])
        if not cited and (out.answerable or bad):
            return "no valid chunk ids cited"
        if bad:
            return f"numbers not found in the cited chunks: {bad}"
        if cited and (claims := self._unsupported_claims(out.answer, evidence)):
            return f"claims not supported by the cited chunks: {claims}"
        return None

    def _unsupported_claims(self, answer: str, evidence: list[str]) -> list[str]:
        """Second opinion from a small model on non-numeric facts (names, inclusions, medical claims)."""
        if not settings.CLAIM_CHECK:
            return []
        sources = "\n".join(f"<source>\n{e}\n</source>" for e in [*evidence, PLACIDWAY_FACTS])
        try:
            verdict = self.llm.complete_structured(model=settings.CHECK_MODEL, system=CLAIM_CHECK_SYSTEM, schema=ClaimCheck,
                                                   messages=[{"role": "user", "content": f"<sources>\n{sources}\n</sources>\n<answer>\n{answer}\n</answer>"}],
                                                   effort="medium")
        except Exception as e:
            # NOTE: fail open: numbers and citations are already verified in code at this point
            log.warning(f"claim check unavailable, skipping: {e}")
            return []
        return [c.claim for c in verdict.claims if not c.supported]

    @staticmethod
    def _disclaimer_shown(req: ChatRequest) -> bool:
        lines = set(DISCLAIMER.values())
        return any(m.role == "assistant" and any(d in m.content for d in lines) for m in req.history)

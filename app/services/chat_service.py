"""Grounded answer pipeline: route -> retrieve -> stream answer (checked per sentence) -> final guards."""
import asyncio
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass

from pydantic import ValidationError

from app.adapters.protocols import LLMPort, LLMRefusal
from app.core.config import settings
from app.core.constants import LEAD_INTENTS, NO_RETRIEVAL_INTENTS, PRICE_INTENTS
from app.core.logging import get_logger
from app.helpers.json_text import extract_json
from app.ingest.chunker import Chunk
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


@dataclass
class Outcome:
    """Result of the answer step (async generators can't return values)."""
    out: AnswerOut | None = None
    problem: str | None = None


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

    async def answer(self, req: ChatRequest) -> ChatResponse:
        """Non-streaming entry point: same pipeline, returns the final response."""
        async with aclosing(self.stream(req)) as events:
            async for event in events:
                if event["type"] == "final":
                    return event["response"]
        raise RuntimeError("pipeline ended without a final event")

    async def stream(self, req: ChatRequest) -> AsyncIterator[Event]:
        history = _alternate([m.model_dump() for m in req.history[-settings.HISTORY_TURNS * 2:]])
        route = await self._route(history, req.message)
        log.info(f"intent={route.intent} lang={route.language} need={route.need!r} queries="
                 f"{[route.standalone_query, *route.extra_queries]!r} assumption={route.assumption!r}")

        if route.intent in NO_RETRIEVAL_INTENTS:
            lead = route.intent in LEAD_INTENTS
            yield {"type": "final", "response": ChatResponse(
                answer=route.direct_reply or _pick(NOT_FOUND, route.language), answered=True, intent=route.intent,
                show_lead_form=lead, sources=[Source(title=SOURCE_CONTACT, url=settings.QUOTE_URL)] if lead else [])}
            return

        yield {"type": "status", "text": STATUS_SEARCHING}
        # NOTE: embedding + search is CPU work; keep it off the event loop
        queries = [route.standalone_query, *route.extra_queries[:2]]
        chunks = await asyncio.to_thread(self.index.search_many, queries, req.message)
        result = Outcome()
        async with aclosing(self._grounded_answer(req, history, route, chunks, result)) as events:
            async for event in events:
                yield event
        yield {"type": "final", "response": self._finish(req, route, chunks, result.out, result.problem)}

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
                                intent=route.intent, show_lead_form=True, sources=[*sources, quote],
                                followups=out.followups[:3])
        answer = out.answer
        if (out.medical_topic or route.intent == "medical_advice") and not self._disclaimer_shown(req):
            answer += "\n\n_" + _pick(DISCLAIMER, route.language) + "_"
        return ChatResponse(answer=answer, sources=sources, answered=True, intent=route.intent,
                            show_lead_form=route.intent in PRICE_INTENTS, followups=out.followups[:3])

    async def _route(self, history: list[dict], message: str) -> RouterOut:
        convo = "\n".join(f"{m['role']}: {m['content'][:1500]}" for m in history)
        prompt = f"<conversation>\n{convo}\n</conversation>\n<latest_user_message>\n{message}\n</latest_user_message>"
        return await self.llm.complete_structured(model=settings.ROUTER_MODEL, system=ROUTER_SYSTEM,
                                            messages=[{"role": "user", "content": prompt}], schema=RouterOut, effort="low")

    async def _grounded_answer(self, req: ChatRequest, history: list[dict], route: RouterOut, chunks: list[Chunk],
                               result: Outcome) -> AsyncIterator[Event]:
        """Stream the answer sentence by sentence, verify it, retry once with the reason. Fills `result`."""
        if not chunks:
            result.problem = "no chunks retrieved"
            return
        context = "\n".join(f'<chunk id="{c.id}" page="{c.page_title}" section="{c.heading}">\n{c.text}\n</chunk>' for c in chunks)
        system = ANSWER_SYSTEM.format(language=route.language) + (VOICE_STYLE if req.channel == "voice" else "")
        assumption = f"<assumption>{route.assumption}</assumption>\n" if route.assumption else ""
        user = (f"<context>\n{context}\n</context>\n<user_need>{route.need}</user_need>\n{assumption}"
                f"<question>\n{req.message}\n</question>")
        by_id = {c.id: c for c in chunks}
        # NOTE: numbers the user typed are allowed so "$50 is not correct" passes the check
        context_evidence = [c.embed_text for c in chunks] + [req.message]
        for _ in range(2):
            messages = [*history, {"role": "user", "content": user}]
            raw, shown, problem = "", False, None
            field, sentences = JsonFieldStream(), SentenceBuffer()
            stream = self.llm.stream_structured(model=settings.ANSWER_MODEL, system=system, messages=messages,
                                                schema=AnswerOut, effort="medium")
            try:
                async with aclosing(stream):
                    async for delta in stream:
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

            if not problem:
                for piece in sentences.flush():
                    if bad := unsupported_facts(piece, context_evidence):
                        problem = f"numbers not found in the context: {bad}"
                    else:
                        shown = True
                        yield {"type": "delta", "text": piece}
            out = None
            if not problem:
                try:
                    out = AnswerOut.model_validate_json(extract_json(raw))
                except ValidationError:
                    problem = "model output was not valid JSON"
            if not problem:
                yield {"type": "status", "text": STATUS_CHECKING}
                problem = await self._check(req, out, by_id)
            result.out, result.problem = out, problem
            if not problem:
                return

            log.warning(f"guard rejected answer: {problem}")
            if shown:
                yield {"type": "reset"}
            if problem.startswith("refusal"):
                result.out = None
                return
            user = f"{user}\n\n{RETRY_NOTE.format(problem=problem)}"

    async def _check(self, req: ChatRequest, out: AnswerOut, by_id: dict[str, Chunk]) -> str | None:
        """Final checks on the complete answer against the chunks it cites."""
        cited = valid_citations(out.cited_ids, set(by_id))
        evidence = [by_id[i].embed_text for i in cited]  # page title + heading + text
        bad = unsupported_facts(out.answer, evidence + [req.message])
        if not cited and (out.answerable or bad):
            return "no valid chunk ids cited"
        if bad:
            return f"numbers not found in the cited chunks: {bad}"
        # NOTE: the claim check sees everything the answer model saw; a fact from an uncited retrieved chunk is still grounded
        if cited and (claims := await self._unsupported_claims(out.answer, [c.embed_text for c in by_id.values()])):
            return f"claims not supported by the cited chunks: {claims}"
        return None

    async def _unsupported_claims(self, answer: str, evidence: list[str]) -> list[str]:
        """Second opinion from a small model on non-numeric facts (names, inclusions, medical claims)."""
        if not settings.CLAIM_CHECK:
            return []
        sources = "\n".join(f"<source>\n{e}\n</source>" for e in [*evidence, PLACIDWAY_FACTS])
        try:
            verdict = await self.llm.complete_structured(model=settings.CHECK_MODEL, system=CLAIM_CHECK_SYSTEM, schema=ClaimCheck,
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

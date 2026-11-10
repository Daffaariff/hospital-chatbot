"""Grounded answer pipeline: route -> retrieve -> answer -> guard."""
from app.adapters.protocols import LLMPort, LLMRefusal
from app.core.config import settings
from app.core.logging import get_logger
from app.ingest.chunker import Chunk
from app.prompts.system_prompts import ANSWER_SYSTEM, DISCLAIMER, NOT_FOUND, RETRY_NOTE, ROUTER_SYSTEM, VOICE_STYLE
from app.schemas.chat import AnswerOut, ChatRequest, ChatResponse, RouterOut, Source
from app.services.guards import unsupported_amounts, valid_citations
from app.services.index import KnowledgeIndex
from app.services.store import Store

log = get_logger("services.chat")
NO_RETRIEVAL = {"greeting", "booking", "quote_request", "out_of_scope"}
LEAD_INTENTS = {"booking", "quote_request"}


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
        history = _alternate([m.model_dump() for m in req.history[-settings.HISTORY_TURNS * 2:]])
        route = self._route(history, req.message)
        log.info(f"intent={route.intent} lang={route.language} query={route.standalone_query!r}")

        if route.intent in NO_RETRIEVAL:
            return ChatResponse(answer=route.direct_reply or _pick(NOT_FOUND, route.language), answered=True,
                                intent=route.intent, show_lead_form=route.intent in LEAD_INTENTS,
                                sources=[Source(title="Contact PlacidWay", url=settings.QUOTE_URL)] if route.intent in LEAD_INTENTS else [])

        chunks = self.index.search(route.standalone_query, req.message)
        out, problem = self._grounded_answer(req, history, route, chunks)
        by_id = {c.id: c for c in chunks}
        quote = Source(title="Request a free quote", url=settings.QUOTE_URL)
        if problem:
            self.store.log_unanswered(req.message, route.standalone_query, problem)
            return ChatResponse(answer=_pick(NOT_FOUND, route.language), answered=False, intent=route.intent,
                                show_lead_form=True, sources=[quote])

        cited = [by_id[i] for i in valid_citations(out.cited_ids, set(by_id))]
        if not out.answerable:
            # NOTE: a "not on our pages" reply may still point to the closest related page
            self.store.log_unanswered(req.message, route.standalone_query, "not in content")
            sources = list({c.url: Source(title=c.page_title, url=c.url) for c in cited}.values())
            return ChatResponse(answer=out.answer or _pick(NOT_FOUND, route.language), answered=False,
                                intent=route.intent, show_lead_form=True, sources=[*sources, quote])
        answer = out.answer
        if (out.medical_topic or route.intent == "medical_advice") and not self._disclaimer_shown(req):
            answer += "\n\n_" + _pick(DISCLAIMER, route.language) + "_"
        sources = list({c.url: Source(title=c.page_title, url=c.url) for c in cited}.values())
        return ChatResponse(answer=answer, sources=sources, answered=True, intent=route.intent,
                            show_lead_form=route.intent in {"price", "comparison"})

    def _route(self, history: list[dict], message: str) -> RouterOut:
        convo = "\n".join(f"{m['role']}: {m['content'][:1500]}" for m in history)
        prompt = f"<conversation>\n{convo}\n</conversation>\n<latest_user_message>\n{message}\n</latest_user_message>"
        return self.llm.complete_structured(model=settings.ROUTER_MODEL, system=ROUTER_SYSTEM,
                                            messages=[{"role": "user", "content": prompt}], schema=RouterOut, effort="low")

    def _grounded_answer(self, req: ChatRequest, history: list[dict], route: RouterOut,
                         chunks: list[Chunk]) -> tuple[AnswerOut | None, str | None]:
        """Ask the LLM, verify citations and amounts, retry once with the reason. Returns (answer, problem)."""
        if not chunks:
            return None, "no chunks retrieved"
        context = "\n".join(f'<chunk id="{c.id}" page="{c.page_title}" section="{c.heading}">\n{c.text}\n</chunk>' for c in chunks)
        system = ANSWER_SYSTEM.format(language=route.language) + (VOICE_STYLE if req.channel == "voice" else "")
        user = (f"<context>\n{context}\n</context>\n<search_query>{route.standalone_query}</search_query>\n"
                f"<question>\n{req.message}\n</question>")
        messages = [*history, {"role": "user", "content": user}]
        by_id = {c.id: c for c in chunks}
        problem = None
        for _ in range(2):
            try:
                out = self.llm.complete_structured(model=settings.ANSWER_MODEL, system=system,
                                                   messages=messages, schema=AnswerOut, effort="medium")
            except LLMRefusal as e:
                return None, f"refusal: {e}"
            cited = valid_citations(out.cited_ids, set(by_id))
            # NOTE: amounts the user typed are allowed so "$50 is not correct" passes the check
            bad = unsupported_amounts(out.answer, [f"{by_id[i].heading}\n{by_id[i].text}" for i in cited] + [req.message])
            if not cited and (out.answerable or bad):
                problem = "no valid chunk ids cited"
            elif bad:
                problem = f"amounts not found in the cited chunks: {sorted(bad)}"
            else:
                return out, None
            log.warning(f"guard rejected answer: {problem}")
            messages = [*messages, {"role": "assistant", "content": out.model_dump_json()},
                        {"role": "user", "content": RETRY_NOTE.format(problem=problem)}]
        return out, problem

    @staticmethod
    def _disclaimer_shown(req: ChatRequest) -> bool:
        lines = set(DISCLAIMER.values())
        return any(m.role == "assistant" and any(d in m.content for d in lines) for m in req.history)

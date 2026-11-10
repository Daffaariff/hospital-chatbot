"""OpenAI or any OpenAI-compatible API (OpenRouter, Ollama, vLLM) via base_url."""
from openai import OpenAI

from app.adapters.protocols import LLMRefusal, T
from app.core.config import settings


class OpenAIAdapter:
    """Implements LLMPort."""

    def __init__(self, api_key: str = settings.OPENAI_API_KEY, base_url: str = settings.OPENAI_BASE_URL):
        self.client = OpenAI(api_key=api_key or "none", base_url=base_url or None,
                             timeout=settings.LLM_TIMEOUT, max_retries=settings.LLM_MAX_RETRIES)

    def complete_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                            effort: str = "medium") -> T:
        resp = self.client.chat.completions.parse(
            model=model,
            messages=[{"role": "system", "content": system}, *messages],
            response_format=schema,
        )
        msg = resp.choices[0].message
        if msg.refusal:
            raise LLMRefusal(msg.refusal)
        return msg.parsed

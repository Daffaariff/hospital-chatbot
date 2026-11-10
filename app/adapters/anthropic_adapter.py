"""Claude via the official anthropic SDK."""
from collections.abc import Iterator

import anthropic

from app.adapters.protocols import LLMRefusal, T
from app.core.config import settings


class AnthropicAdapter:
    """Implements LLMPort."""

    def __init__(self, api_key: str = settings.ANTHROPIC_API_KEY):
        self.client = anthropic.Anthropic(api_key=api_key or None, timeout=settings.LLM_TIMEOUT,
                                          max_retries=settings.LLM_MAX_RETRIES)

    @staticmethod
    def _params(model: str, system: str, messages: list[dict], schema: type[T], effort: str) -> dict:
        return {"model": model, "max_tokens": 8000, "system": system, "messages": messages, "output_format": schema,
                "output_config": {"effort": effort}, "cache_control": {"type": "ephemeral"}}

    def complete_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                            effort: str = "medium") -> T:
        resp = self.client.beta.messages.parse(**self._params(model, system, messages, schema, effort))
        if resp.stop_reason == "refusal":
            raise LLMRefusal(str(resp.stop_details))
        return resp.parsed_output

    def stream_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                          effort: str = "medium") -> Iterator[str]:
        # NOTE: no server-side refusal fallback here: a mid-stream switch would splice two JSON objects together
        with self.client.beta.messages.stream(**self._params(model, system, messages, schema, effort)) as stream:
            yield from stream.text_stream
            final = stream.get_final_message()
        if final.stop_reason == "refusal":
            raise LLMRefusal(str(final.stop_details))

"""Claude via the official anthropic SDK (async client)."""
from collections.abc import AsyncIterator

import anthropic

from app.adapters.protocols import LLMRefusal, T
from app.core.config import settings


class AnthropicAdapter:
    """Implements LLMPort."""

    def __init__(self, api_key: str = settings.ANTHROPIC_API_KEY):
        self.client = anthropic.AsyncAnthropic(api_key=api_key or None, timeout=settings.LLM_TIMEOUT,
                                               max_retries=settings.LLM_MAX_RETRIES)

    @staticmethod
    def _params(model: str, system: str, messages: list[dict], schema: type[T], effort: str) -> dict:
        return {"model": model, "max_tokens": 8000, "system": system, "messages": messages, "output_format": schema,
                "output_config": {"effort": effort}, "cache_control": {"type": "ephemeral"}}

    async def complete_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                                  effort: str = "medium") -> T:
        resp = await self.client.beta.messages.parse(**self._params(model, system, messages, schema, effort))
        if resp.stop_reason == "refusal":
            raise LLMRefusal(str(resp.stop_details))
        return resp.parsed_output

    async def stream_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                                effort: str = "medium") -> AsyncIterator[str]:
        # NOTE: no server-side refusal fallback here: a mid-stream switch would splice two JSON objects together
        async with self.client.beta.messages.stream(**self._params(model, system, messages, schema, effort)) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
        if final.stop_reason == "refusal":
            raise LLMRefusal(str(final.stop_details))

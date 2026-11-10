"""OpenAI or any OpenAI-compatible API (OpenRouter, Ollama, vLLM) via base_url (async client)."""
import json
from collections.abc import AsyncIterator

import httpx
from openai import AsyncOpenAI

from app.adapters.protocols import LLMRefusal, T
from app.core.config import settings
from app.helpers.json_text import extract_json


class OpenAIAdapter:
    """Implements LLMPort. json_mode: "schema" (strict structured outputs) or "object" (schema in the prompt)."""

    def __init__(self, api_key: str = settings.OPENAI_API_KEY, base_url: str = settings.OPENAI_BASE_URL,
                 json_mode: str = settings.OPENAI_JSON_MODE, http_client: httpx.AsyncClient | None = None):
        self.client = AsyncOpenAI(api_key=api_key or "none", base_url=base_url or None, http_client=http_client,
                                  timeout=settings.LLM_TIMEOUT, max_retries=settings.LLM_MAX_RETRIES)
        self.json_mode = json_mode

    def _messages(self, system: str, messages: list[dict], schema: type[T]) -> list[dict]:
        if self.json_mode == "object":
            system += ("\n\nReply with one JSON object, and nothing else, that matches this JSON schema:\n"
                       + json.dumps(schema.model_json_schema()))
        return [{"role": "system", "content": system}, *messages]

    async def complete_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                                  effort: str = "medium") -> T:
        msgs = self._messages(system, messages, schema)
        if self.json_mode == "object":
            resp = await self.client.chat.completions.create(model=model, messages=msgs,
                                                             response_format={"type": "json_object"})
            return schema.model_validate_json(extract_json(resp.choices[0].message.content or ""))
        resp = await self.client.chat.completions.parse(model=model, messages=msgs, response_format=schema)
        msg = resp.choices[0].message
        if msg.refusal:
            raise LLMRefusal(msg.refusal)
        return msg.parsed

    async def stream_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                                effort: str = "medium") -> AsyncIterator[str]:
        msgs = self._messages(system, messages, schema)
        if self.json_mode == "object":
            stream = await self.client.chat.completions.create(model=model, messages=msgs, stream=True,
                                                               response_format={"type": "json_object"})
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return
        async with self.client.chat.completions.stream(model=model, messages=msgs, response_format=schema) as s:
            async for event in s:
                if event.type == "content.delta":
                    yield event.delta
            final = await s.get_final_completion()
        if final.choices[0].message.refusal:
            raise LLMRefusal(final.choices[0].message.refusal)

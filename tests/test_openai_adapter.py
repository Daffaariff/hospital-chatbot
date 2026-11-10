import asyncio
import json

import httpx

from app.adapters.openai_adapter import OpenAIAdapter
from app.schemas.chat import RouterOut

ROUTE = {"need": "adrenal cost", "standalone_query": "adrenal cost", "extra_queries": [], "assumption": "",
         "intent": "price", "language": "English", "direct_reply": ""}


def _completion(content: str) -> dict:
    return {"id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}]}


def _adapter(handler, mode):
    return OpenAIAdapter(api_key="k", base_url="https://llm.test/v1", json_mode=mode,
                         http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def test_schema_mode_sends_json_schema_and_parses():
    sent = {}

    def handler(req):
        sent.update(json.loads(req.content))
        return httpx.Response(200, json=_completion(json.dumps(ROUTE)))

    out = asyncio.run(_adapter(handler, "schema").complete_structured(model="m", system="s", messages=[{"role": "user", "content": "q"}], schema=RouterOut))
    assert out.intent == "price" and sent["response_format"]["type"] == "json_schema"


def test_object_mode_puts_schema_in_prompt_and_tolerates_fences():
    sent = {}

    def handler(req):
        sent.update(json.loads(req.content))
        return httpx.Response(200, json=_completion("```json\n" + json.dumps(ROUTE) + "\n```"))

    out = asyncio.run(_adapter(handler, "object").complete_structured(model="m", system="s", messages=[{"role": "user", "content": "q"}], schema=RouterOut))
    assert out.standalone_query == "adrenal cost"
    assert sent["response_format"] == {"type": "json_object"} and "standalone_query" in sent["messages"][0]["content"]


def test_object_mode_streams_raw_json():
    body = json.dumps(ROUTE)
    chunks = [body[i:i + 9] for i in range(0, len(body), 9)]
    sse = "".join("data: " + json.dumps({"id": "x", "object": "chat.completion.chunk", "created": 0, "model": "m",
                                         "choices": [{"index": 0, "delta": {"content": c}, "finish_reason": None}]}) + "\n\n"
                  for c in chunks) + "data: [DONE]\n\n"

    def handler(req):
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse.encode())

    async def collect():
        return "".join([d async for d in _adapter(handler, "object").stream_structured(model="m", system="s", messages=[], schema=RouterOut)])
    got = asyncio.run(collect())
    assert json.loads(got) == ROUTE

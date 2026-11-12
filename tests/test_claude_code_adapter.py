import asyncio

from app.adapters.claude_code_adapter import ClaudeCodeAdapter
from app.schemas.chat import ClaimCheck


def test_parses_structured_output_and_passes_history():
    seen = {}

    class Fake(ClaudeCodeAdapter):
        async def _run(self, args, prompt):
            seen["args"], seen["prompt"] = args, prompt
            return {"is_error": False, "stop_reason": "end_turn", "structured_output": {"claims": []}}

    out = asyncio.run(Fake().complete_structured(
        model="claude-haiku-5-5", system="sys", schema=ClaimCheck,
        messages=[{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"},
                  {"role": "user", "content": "q2"}]))
    assert out.claims == []
    assert seen["args"][seen["args"].index("--effort") + 1] == "medium"  # same effort the API path sends
    assert "--json-schema" in seen["args"] and "--tools" in seen["args"] and "--strict-mcp-config" in seen["args"]
    assert "<assistant>\na1\n</assistant>" in seen["prompt"] and seen["prompt"].endswith("q2")

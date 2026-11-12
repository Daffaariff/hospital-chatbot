"""Dev-only provider: routes LLM calls through the local `claude` CLI (Claude Code) instead of the paid API."""
import asyncio
import json
import tempfile
from collections.abc import AsyncIterator

from app.adapters.protocols import LLMRefusal, T

# NOTE: strip Claude Code's own context (MCP, skills, plugins, settings): ~162k tokens per call down to ~1k
_BASE_ARGS = ["-p", "--output-format", "json", "--tools", "", "--strict-mcp-config", "--mcp-config",
              '{"mcpServers":{}}', "--disable-slash-commands", "--setting-sources", "", "--no-session-persistence"]


class ClaudeCodeAdapter:
    """Implements LLMPort. Not for production: one CLI process per call, no token streaming."""

    def __init__(self, binary: str = "claude", timeout: float = 180.0):
        self.binary, self.timeout = binary, timeout
        self.workdir = tempfile.mkdtemp(prefix="claude-code-llm-")  # neutral cwd: no project CLAUDE.md

    @staticmethod
    def _prompt(messages: list[dict]) -> str:
        """The CLI takes one prompt; earlier turns are passed as a labelled transcript."""
        *history, last = messages
        convo = "\n".join(f"<{m['role']}>\n{m['content']}\n</{m['role']}>" for m in history)
        return (f"<earlier_conversation>\n{convo}\n</earlier_conversation>\n\n" if convo else "") + last["content"]

    async def _run(self, args: list[str], prompt: str) -> dict:
        proc = await asyncio.create_subprocess_exec(
            self.binary, *args, cwd=self.workdir, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(prompt.encode()), self.timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise TimeoutError(f"claude CLI timed out after {self.timeout}s")
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            raise RuntimeError(f"claude CLI returned no JSON: {(out or err)[:300]!r}")

    async def complete_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                                  effort: str = "medium") -> T:
        args = [*_BASE_ARGS, "--model", model, "--effort", effort, "--system-prompt", system,
                "--json-schema", json.dumps(schema.model_json_schema())]
        data = await self._run(args, self._prompt(messages))
        if data.get("is_error"):
            raise RuntimeError(f"claude CLI error: {str(data.get('result'))[:300]}")
        if data.get("stop_reason") == "refusal":
            raise LLMRefusal(str(data.get("result")))
        return schema.model_validate(data["structured_output"])

    async def stream_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                                effort: str = "medium") -> AsyncIterator[str]:
        # NOTE: no token streaming through the CLI; the whole object arrives at once and the pipeline still checks it
        out = await self.complete_structured(model=model, system=system, messages=messages, schema=schema, effort=effort)
        yield out.model_dump_json()

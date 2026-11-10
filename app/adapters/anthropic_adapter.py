"""Claude via the official anthropic SDK."""
import anthropic

from app.adapters.protocols import LLMRefusal, T
from app.core.config import settings

# NOTE: server-side refusal fallback only exists for these model families
_FALLBACK_MODELS = ("claude-opus-5", "claude-fable-5", "claude-sonnet-5-5")


class AnthropicAdapter:
    """Implements LLMPort."""

    def __init__(self, api_key: str = settings.ANTHROPIC_API_KEY):
        self.client = anthropic.Anthropic(api_key=api_key or None, timeout=settings.LLM_TIMEOUT,
                                          max_retries=settings.LLM_MAX_RETRIES)

    def complete_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                            effort: str = "medium") -> T:
        kwargs = {}
        if model.startswith(_FALLBACK_MODELS):
            kwargs = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        resp = self.client.beta.messages.parse(
            model=model,
            max_tokens=8000,
            system=system,
            messages=messages,
            output_format=schema,
            output_config={"effort": effort},
            cache_control={"type": "ephemeral"},
            **kwargs,
        )
        if resp.stop_reason == "refusal":
            raise LLMRefusal(str(resp.stop_details))
        return resp.parsed_output

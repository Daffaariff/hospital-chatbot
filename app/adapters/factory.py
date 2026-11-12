"""Pick the LLM adapter from LLM_PROVIDER."""
from functools import lru_cache

from app.adapters.limited import LimitedLLM
from app.adapters.protocols import LLMPort
from app.core.config import settings


@lru_cache
def get_llm() -> LLMPort:
    return LimitedLLM(_provider(), settings.LLM_MAX_CONCURRENCY)


def _provider() -> LLMPort:
    if settings.LLM_PROVIDER == "anthropic":
        from app.adapters.anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter()
    if settings.LLM_PROVIDER == "openai":
        claude = [m for m in (settings.ANSWER_MODEL, settings.ROUTER_MODEL, settings.CHECK_MODEL) if m.startswith("claude-")]
        if claude and not settings.OPENAI_BASE_URL:
            raise ValueError(f"LLM_PROVIDER=openai but {claude} are Claude model ids: set ANSWER_MODEL, ROUTER_MODEL and "
                             "CHECK_MODEL to OpenAI models (see .env.example)")
        from app.adapters.openai_adapter import OpenAIAdapter
        return OpenAIAdapter()
    if settings.LLM_PROVIDER == "claude_code":
        from app.adapters.claude_code_adapter import ClaudeCodeAdapter
        return ClaudeCodeAdapter()
    raise ValueError(f"unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")

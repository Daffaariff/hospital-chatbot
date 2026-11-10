"""Pick the LLM adapter from LLM_PROVIDER."""
from functools import lru_cache

from app.adapters.protocols import LLMPort
from app.core.config import settings


@lru_cache
def get_llm() -> LLMPort:
    if settings.LLM_PROVIDER == "anthropic":
        from app.adapters.anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter()
    if settings.LLM_PROVIDER == "openai":
        from app.adapters.openai_adapter import OpenAIAdapter
        return OpenAIAdapter()
    raise ValueError(f"unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")

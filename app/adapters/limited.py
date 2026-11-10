"""Caps concurrent LLM calls so a burst of users queues briefly instead of hitting provider rate limits."""
import asyncio
from collections.abc import AsyncIterator
from contextlib import aclosing

from app.adapters.protocols import LLMPort, T


class LimitedLLM:
    """Implements LLMPort by wrapping another adapter; a stream holds its slot until it finishes."""

    def __init__(self, inner: LLMPort, max_concurrency: int):
        self.inner = inner
        self.slots = asyncio.Semaphore(max_concurrency)

    async def complete_structured(self, **kwargs) -> T:
        async with self.slots:
            return await self.inner.complete_structured(**kwargs)

    async def stream_structured(self, **kwargs) -> AsyncIterator[str]:
        # NOTE: aclosing so cancelling this stream also closes the provider's HTTP stream
        async with self.slots, aclosing(self.inner.stream_structured(**kwargs)) as stream:
            async for delta in stream:
                yield delta

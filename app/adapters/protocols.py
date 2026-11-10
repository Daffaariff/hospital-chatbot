"""LLM port: every provider returns a validated pydantic object, or streams its raw JSON."""
from collections.abc import AsyncIterator
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMRefusal(Exception):
    """Provider declined to answer (safety refusal)."""


@runtime_checkable
class LLMPort(Protocol):
    async def complete_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                                  effort: str = "medium") -> T: ...

    def stream_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                          effort: str = "medium") -> AsyncIterator[str]:
        """Async-iterate raw JSON text deltas of a `schema` object; raise LLMRefusal at the end if declined."""
        ...

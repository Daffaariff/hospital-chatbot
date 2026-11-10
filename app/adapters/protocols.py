"""LLM port: every provider returns a validated pydantic object."""
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMRefusal(Exception):
    """Provider declined to answer (safety refusal)."""


@runtime_checkable
class LLMPort(Protocol):
    def complete_structured(self, *, model: str, system: str, messages: list[dict], schema: type[T],
                            effort: str = "medium") -> T: ...

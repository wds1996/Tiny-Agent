from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ToolCall:
    """A model request to invoke one named tool."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ModelResponse:
    """Normalized output returned by a model adapter."""

    final_answer: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class Model(Protocol):
    """Minimal interface the runtime needs from any LLM provider."""

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        ...

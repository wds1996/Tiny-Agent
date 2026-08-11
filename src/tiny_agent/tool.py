from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class Tool:
    """A callable capability exposed to the model."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]

    def schema(self) -> dict[str, Any]:
        """Return the provider-neutral function schema visible to the model."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def invoke(self, arguments: dict[str, Any]) -> Any:
        """Execute the underlying Python function with model-generated arguments."""
        return self.handler(**arguments)


class ToolRegistry:
    """Owns tool lookup, schema export, and execution."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return tool.invoke(arguments)

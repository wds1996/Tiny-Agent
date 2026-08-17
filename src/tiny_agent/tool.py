from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class Tool:
    """A callable capability exposed to the model.

    Handlers may be synchronous or asynchronous. The original synchronous
    ``invoke`` API remains for the Stage 01 runtime, while ``ainvoke`` is the
    safe path for remote/async capabilities such as MCP tools.
    """

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
        """Execute a synchronous handler.

        An async handler is rejected explicitly instead of leaking a coroutine
        object into the model transcript. Call :meth:`ainvoke` for async tools.
        """
        result = self.handler(**arguments)
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()
            raise RuntimeError(
                f"Tool {self.name!r} is asynchronous; use Tool.ainvoke() or "
                "ToolRegistry.aexecute()"
            )
        return result

    async def ainvoke(self, arguments: dict[str, Any]) -> Any:
        """Execute either a synchronous or asynchronous handler."""
        result = self.handler(**arguments)
        if inspect.isawaitable(result):
            return await result
        return result


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

    async def aexecute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool without assuming its handler is synchronous."""
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return await tool.ainvoke(arguments)

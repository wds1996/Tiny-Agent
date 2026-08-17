from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .tool import Tool, ToolRegistry


class MCPToolError(RuntimeError):
    """A model-visible MCP tool failure after protocol execution succeeds."""


@dataclass(slots=True, frozen=True)
class MCPToolBinding:
    """Record how a remote MCP tool is exposed inside Tiny-Agent."""

    remote_name: str
    local_name: str


class MCPToolBridge:
    """Adapt tools discovered from a connected MCP v2 ``Client``.

    The bridge intentionally preserves MCP Resources and Prompts as separate
    primitives. Only MCP Tools are normalized into Tiny-Agent ``Tool`` objects.
    This avoids the common anti-pattern of pretending every piece of context is
    an executable function.
    """

    def __init__(self, client: Any, *, namespace: str | None = None) -> None:
        self.client = client
        self.namespace = namespace.strip() if namespace else None
        self._bindings: dict[str, MCPToolBinding] = {}

    @property
    def bindings(self) -> tuple[MCPToolBinding, ...]:
        return tuple(self._bindings.values())

    async def discover_tools(self) -> list[Tool]:
        """Discover the current server tool catalog and build local adapters."""
        response = await self.client.list_tools()
        tools: list[Tool] = []
        self._bindings.clear()

        for remote in response.tools:
            remote_name = remote.name
            local_name = self._local_name(remote_name)
            self._bindings[local_name] = MCPToolBinding(
                remote_name=remote_name,
                local_name=local_name,
            )

            tools.append(
                Tool(
                    name=local_name,
                    description=remote.description
                    or remote.title
                    or f"MCP tool {remote_name}",
                    parameters=dict(remote.input_schema),
                    handler=self._make_handler(remote_name),
                )
            )

        return tools

    async def populate_registry(self, registry: ToolRegistry) -> list[Tool]:
        """Discover MCP tools and register them in an existing registry."""
        tools = await self.discover_tools()
        for tool in tools:
            registry.register(tool)
        return tools

    def _make_handler(self, remote_name: str) -> Callable[..., Any]:
        async def handler(**arguments: Any) -> Any:
            return await self._call_remote_tool(remote_name, arguments)

        return handler

    async def _call_remote_tool(
        self,
        remote_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        result = await self.client.call_tool(remote_name, arguments)

        if result.is_error:
            raise MCPToolError(self._content_to_text(result.content))

        structured = getattr(result, "structured_content", None)
        if structured is not None:
            return structured

        return self._content_to_text(result.content)

    def _local_name(self, remote_name: str) -> str:
        if not self.namespace:
            return remote_name
        return f"{self.namespace}__{remote_name}"

    @staticmethod
    def _content_to_text(content: list[Any]) -> str:
        """Render MCP content blocks without assuming every block is text."""
        rendered: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                rendered.append(text)
                continue

            model_dump = getattr(block, "model_dump", None)
            if callable(model_dump):
                rendered.append(str(model_dump(mode="json")))
            else:
                rendered.append(str(block))
        return "\n".join(rendered)

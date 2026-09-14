from __future__ import annotations

import asyncio
from dataclasses import dataclass
import inspect
from typing import Any, Awaitable, Callable, Protocol


ToolHandler = Callable[..., Any | Awaitable[Any]]
DEFAULT_ALLOWED_TOOLS = frozenset(
    {"get_order_summary", "get_shipment_status", "get_invoice_summary"}
)


class MCPClientLike(Protocol):
    async def list_tools(self) -> Any: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    source: str

    async def ainvoke(self, arguments: dict[str, Any]) -> Any:
        if not isinstance(arguments, dict):
            raise TypeError("tool arguments must be a dictionary")
        result = self.handler(**arguments)
        if inspect.isawaitable(result):
            return await result
        return result


class AsyncToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self._tools.values()
        ]

    async def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            tool = self._tools[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc
        return await tool.ainvoke(arguments)


class MCPToolBridge:
    def __init__(
        self,
        client: MCPClientLike,
        *,
        namespace: str,
        allowed_remote_tools: set[str] | frozenset[str],
    ) -> None:
        normalized = namespace.strip()
        if not normalized:
            raise ValueError("namespace must not be blank")
        allowed = frozenset(name.strip() for name in allowed_remote_tools if name.strip())
        if not allowed:
            raise ValueError("allowed_remote_tools must not be empty")
        self._client = client
        self._namespace = normalized
        self._allowed = allowed

    async def populate(self, registry: AsyncToolRegistry) -> None:
        catalog = await self._client.list_tools()
        discovered = {remote.name: remote for remote in catalog.tools}
        missing = self._allowed - discovered.keys()
        if missing:
            raise RuntimeError(f"allowed MCP tools were not discovered: {sorted(missing)}")

        for remote_name in sorted(self._allowed):
            remote = discovered[remote_name]
            local_name = f"{self._namespace}__{remote_name}"

            async def call_remote(
                _remote_name: str = remote_name,
                **arguments: Any,
            ) -> Any:
                result = await self._client.call_tool(_remote_name, arguments)
                if result.is_error:
                    raise RuntimeError(f"remote MCP tool failed: {_remote_name}")
                if result.structured_content is not None:
                    return result.structured_content
                return [block.model_dump(mode="json") for block in result.content]

            registry.register(
                Tool(
                    name=local_name,
                    description=remote.description or f"MCP tool {remote_name}",
                    parameters=dict(remote.input_schema),
                    handler=call_remote,
                    source=f"mcp:{self._namespace}:{remote_name}",
                )
            )


async def main() -> None:
    try:
        from mcp import Client
    except ImportError as exc:
        raise RuntimeError(
            "Install Stage 05 dependencies first:\n"
            "python -m pip install -r stages/05-mcp/code/requirements.txt"
        ) from exc
    from mcp_server import mcp

    registry = AsyncToolRegistry()
    async with Client(mcp) as client:
        bridge = MCPToolBridge(
            client,
            namespace="support",
            allowed_remote_tools=DEFAULT_ALLOWED_TOOLS,
        )
        await bridge.populate(registry)
        print("model-visible tools:", [schema["name"] for schema in registry.schemas()])
        result = await registry.execute(
            "support__get_order_summary", {"order_id": "ACME-1007"}
        )
        print("bridged result:", result)


if __name__ == "__main__":
    asyncio.run(main())

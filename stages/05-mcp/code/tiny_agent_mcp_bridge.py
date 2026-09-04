from __future__ import annotations

import asyncio
from dataclasses import dataclass
import inspect
from typing import Any, Awaitable, Callable

from mcp import Client

from mcp_server import mcp


ToolHandler = Callable[..., Any | Awaitable[Any]]


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    async def ainvoke(self, arguments: dict[str, Any]) -> Any:
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
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return await self._tools[name].ainvoke(arguments)


class MCPToolBridge:
    def __init__(self, client: Client, *, namespace: str) -> None:
        normalized = namespace.strip()
        if not normalized:
            raise ValueError("namespace must not be blank")
        self._client = client
        self._namespace = normalized

    async def populate(self, registry: AsyncToolRegistry) -> None:
        catalog = await self._client.list_tools()
        for remote in catalog.tools:
            remote_name = remote.name
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
                )
            )


async def main() -> None:
    registry = AsyncToolRegistry()

    async with Client(mcp) as client:
        bridge = MCPToolBridge(client, namespace="handbook")
        await bridge.populate(registry)

        print("local tool names:", [item["name"] for item in registry.schemas()])
        result = await registry.execute("handbook__add", {"a": 19, "b": 23})
        print("bridged result:", result)


if __name__ == "__main__":
    asyncio.run(main())

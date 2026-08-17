"""Discover MCP tools and expose them through Tiny-Agent's ToolRegistry."""

from __future__ import annotations

import asyncio

from mcp import Client

from tiny_agent import ToolRegistry
from tiny_agent.mcp_bridge import MCPToolBridge

from mcp_server import mcp


async def main() -> None:
    registry = ToolRegistry()

    async with Client(mcp) as client:
        bridge = MCPToolBridge(client, namespace="demo")
        tools = await bridge.populate_registry(registry)

        print("Tiny-Agent schemas:")
        for schema in registry.schemas():
            print(schema)

        print("bindings:", bridge.bindings)
        print("registered tools:", [tool.name for tool in tools])

        result = await registry.aexecute(
            "demo__add",
            {"a": 20, "b": 22},
        )
        print("Tiny-Agent -> MCP result:", result)


if __name__ == "__main__":
    asyncio.run(main())

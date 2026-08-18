import asyncio

import pytest

from mcp import Client
from mcp.server import MCPServer

from tiny_agent import MCPToolBridge, MCPToolError, ToolRegistry


def build_server() -> MCPServer:
    server = MCPServer("Tiny-Agent MCP Test")

    @server.tool()
    def add(a: int, b: int) -> dict[str, int]:
        """Add two integers."""
        return {"result": a + b}

    @server.tool()
    def fail(reason: str) -> str:
        """Always fail so error propagation can be tested."""
        raise ValueError(reason)

    @server.resource("test://about")
    def about() -> str:
        return "Tiny-Agent MCP test resource"

    @server.prompt()
    def explain(topic: str) -> str:
        return f"Explain {topic} to a beginner."

    return server


def test_mcp_v2_client_discovers_tools_resources_and_prompts() -> None:
    async def scenario() -> None:
        async with Client(build_server()) as client:
            assert client.protocol_version == "2026-07-28"

            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} == {"add", "fail"}

            resources = await client.list_resources()
            assert [str(resource.uri) for resource in resources.resources] == [
                "test://about"
            ]

            prompts = await client.list_prompts()
            assert [prompt.name for prompt in prompts.prompts] == ["explain"]

            prompt = await client.get_prompt("explain", {"topic": "MCP"})
            assert len(prompt.messages) == 1

    asyncio.run(scenario())


def test_mcp_v2_tool_call_returns_structured_content() -> None:
    async def scenario() -> None:
        async with Client(build_server()) as client:
            result = await client.call_tool("add", {"a": 20, "b": 22})
            assert result.is_error is False
            assert result.structured_content == {"result": 42}

    asyncio.run(scenario())


def test_bridge_namespaces_and_executes_remote_tool() -> None:
    async def scenario() -> None:
        registry = ToolRegistry()

        async with Client(build_server()) as client:
            bridge = MCPToolBridge(client, namespace="math")
            tools = await bridge.populate_registry(registry)

            assert {tool.name for tool in tools} == {"math__add", "math__fail"}
            assert {binding.remote_name for binding in bridge.bindings} == {
                "add",
                "fail",
            }

            schemas = {schema["name"]: schema for schema in registry.schemas()}
            assert "math__add" in schemas
            assert schemas["math__add"]["parameters"]["type"] == "object"

            result = await registry.aexecute("math__add", {"a": 3, "b": 4})
            assert result == {"result": 7}

    asyncio.run(scenario())


def test_bridge_converts_mcp_tool_error_to_explicit_exception() -> None:
    async def scenario() -> None:
        registry = ToolRegistry()

        async with Client(build_server()) as client:
            bridge = MCPToolBridge(client, namespace="remote")
            await bridge.populate_registry(registry)

            with pytest.raises(MCPToolError):
                await registry.aexecute("remote__fail", {"reason": "boom"})

    asyncio.run(scenario())

import asyncio

import mcp.types as types
import pytest
from mcp import Client
from mcp.server import MCPServer

from tiny_agent import MCPToolBridge, MCPToolError, ToolRegistry


POLICIES = {
    "refunds": "Refunds to the original payment method are available within 30 days.",
    "shipping": "Standard shipping takes 3-5 business days after dispatch.",
}


def build_server() -> MCPServer:
    server = MCPServer("Tiny-Agent MCP Test")

    @server.tool()
    def add(a: int, b: int) -> dict[str, int]:
        """Add two integers."""
        return {"result": a + b}

    @server.tool()
    def policy(topic: str) -> dict[str, str]:
        """Return one policy or fail explicitly."""
        if topic not in POLICIES:
            raise ValueError(f"unknown policy: {topic}")
        return {"topic": topic, "policy": POLICIES[topic]}

    @server.resource("test://about")
    def about() -> str:
        return "Tiny-Agent MCP test resource"

    @server.resource("test://policy/{topic}")
    def policy_resource(topic: str) -> str:
        if topic not in POLICIES:
            raise ValueError(f"unknown policy: {topic}")
        return POLICIES[topic]

    @server.prompt()
    def explain(topic: str) -> str:
        return f"Explain {topic} to a beginner."

    return server


def test_mcp_v2_client_discovers_current_protocol_and_capabilities() -> None:
    async def scenario() -> None:
        async with Client(build_server()) as client:
            assert client.protocol_version == "2026-07-28"
            assert client.server_capabilities.tools is not None
            assert client.server_capabilities.resources is not None
            assert client.server_capabilities.prompts is not None

    asyncio.run(scenario())


def test_mcp_primitives_remain_distinct_and_resource_template_is_readable() -> None:
    async def scenario() -> None:
        async with Client(build_server()) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} == {"add", "policy"}

            resources = await client.list_resources()
            assert [str(resource.uri) for resource in resources.resources] == [
                "test://about"
            ]

            templates = await client.list_resource_templates()
            assert [template.uri_template for template in templates.resource_templates] == [
                "test://policy/{topic}"
            ]

            resource = await client.read_resource("test://policy/refunds")
            assert isinstance(resource.contents[0], types.TextResourceContents)
            assert "30 days" in resource.contents[0].text

            prompts = await client.list_prompts()
            assert [prompt.name for prompt in prompts.prompts] == ["explain"]
            prompt = await client.get_prompt("explain", {"topic": "MCP"})
            assert isinstance(prompt.messages[0].content, types.TextContent)
            assert "MCP" in prompt.messages[0].content.text

    asyncio.run(scenario())


def test_mcp_tool_result_distinguishes_success_and_tool_error() -> None:
    async def scenario() -> None:
        async with Client(build_server()) as client:
            success = await client.call_tool("add", {"a": 20, "b": 22})
            assert success.is_error is False
            assert success.structured_content == {"result": 42}

            failure = await client.call_tool("policy", {"topic": "missing"})
            assert failure.is_error is True
            assert failure.content

    asyncio.run(scenario())


def test_bridge_namespaces_and_executes_remote_tool() -> None:
    async def scenario() -> None:
        registry = ToolRegistry()

        async with Client(build_server()) as client:
            bridge = MCPToolBridge(client, namespace="remote")
            tools = await bridge.populate_registry(registry)

            assert {tool.name for tool in tools} == {"remote__add", "remote__policy"}
            schemas = {schema["name"]: schema for schema in registry.schemas()}
            assert schemas["remote__add"]["parameters"]["type"] == "object"

            result = await registry.aexecute("remote__add", {"a": 3, "b": 4})
            assert result == {"result": 7}

    asyncio.run(scenario())


def test_bridge_preserves_remote_tool_error_as_explicit_failure() -> None:
    async def scenario() -> None:
        registry = ToolRegistry()

        async with Client(build_server()) as client:
            bridge = MCPToolBridge(client, namespace="remote")
            await bridge.populate_registry(registry)

            with pytest.raises(MCPToolError):
                await registry.aexecute("remote__policy", {"topic": "missing"})

    asyncio.run(scenario())

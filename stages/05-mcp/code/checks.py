from __future__ import annotations

import asyncio
import unittest

from mcp import Client
import mcp.types as types

from mcp_server import mcp
from tiny_agent_mcp_bridge import AsyncToolRegistry, MCPToolBridge


class Stage05Checks(unittest.TestCase):
    def test_current_protocol_and_capabilities_are_discovered(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                self.assertEqual(client.protocol_version, "2026-07-28")
                self.assertIsNotNone(client.server_capabilities.tools)
                self.assertIsNotNone(client.server_capabilities.resources)
                self.assertIsNotNone(client.server_capabilities.prompts)

        asyncio.run(scenario())

    def test_tools_resources_and_prompts_stay_distinct(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                tools = await client.list_tools()
                resources = await client.list_resources()
                templates = await client.list_resource_templates()
                prompts = await client.list_prompts()

                self.assertEqual({item.name for item in tools.tools}, {"add", "lookup_policy"})
                self.assertEqual([str(item.uri) for item in resources.resources], ["tiny-agent://about"])
                self.assertEqual(
                    [item.uri_template for item in templates.resource_templates],
                    ["tiny-agent://handbook/{topic}"],
                )
                self.assertEqual([item.name for item in prompts.prompts], ["explain_mcp"])

        asyncio.run(scenario())

    def test_tool_returns_structured_content(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                result = await client.call_tool("add", {"a": 20, "b": 22})
                self.assertFalse(result.is_error)
                self.assertEqual(result.structured_content, {"result": 42})

        asyncio.run(scenario())

    def test_tool_failure_is_a_protocol_result(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                result = await client.call_tool("lookup_policy", {"topic": "missing"})
                self.assertTrue(result.is_error)
                self.assertTrue(result.content)

        asyncio.run(scenario())

    def test_resource_template_can_be_read(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                result = await client.read_resource("tiny-agent://handbook/refunds")
                first = result.contents[0]
                self.assertIsInstance(first, types.TextResourceContents)
                assert isinstance(first, types.TextResourceContents)
                self.assertIn("30 days", first.text)

        asyncio.run(scenario())

    def test_prompt_renders_model_facing_text(self) -> None:
        async def scenario() -> None:
            async with Client(mcp) as client:
                result = await client.get_prompt(
                    "explain_mcp",
                    {"topic": "MCP Resources", "audience": "beginner"},
                )
                message = result.messages[0]
                self.assertIsInstance(message.content, types.TextContent)
                assert isinstance(message.content, types.TextContent)
                self.assertIn("MCP Resources", message.content.text)

        asyncio.run(scenario())

    def test_bridge_namespaces_remote_tools(self) -> None:
        async def scenario() -> None:
            registry = AsyncToolRegistry()
            async with Client(mcp) as client:
                await MCPToolBridge(client, namespace="demo").populate(registry)
                names = {schema["name"] for schema in registry.schemas()}
                self.assertEqual(names, {"demo__add", "demo__lookup_policy"})
                result = await registry.execute("demo__add", {"a": 3, "b": 4})
                self.assertEqual(result, {"result": 7})

        asyncio.run(scenario())

    def test_bridge_preserves_remote_failure(self) -> None:
        async def scenario() -> None:
            registry = AsyncToolRegistry()
            async with Client(mcp) as client:
                await MCPToolBridge(client, namespace="demo").populate(registry)
                with self.assertRaisesRegex(RuntimeError, "remote MCP tool failed"):
                    await registry.execute("demo__lookup_policy", {"topic": "missing"})

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main(verbosity=2)

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import importlib.util
from types import SimpleNamespace
import unittest

from support_data import (
    create_support_case,
    get_invoice_summary,
    get_order_summary,
    get_shipment_status,
    read_support_guide,
)
from tiny_agent_mcp_bridge import AsyncToolRegistry, MCPToolBridge


MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None


@dataclass
class FakeRemoteTool:
    name: str
    description: str
    input_schema: dict


class FakeMCPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.tools = [
            FakeRemoteTool("get_order_summary", "read order", {"type": "object"}),
            FakeRemoteTool("get_shipment_status", "read shipment", {"type": "object"}),
            FakeRemoteTool("get_invoice_summary", "read invoice", {"type": "object"}),
            FakeRemoteTool("create_support_case", "write support case", {"type": "object"}),
        ]

    async def list_tools(self):
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, dict(arguments)))
        if name == "get_order_summary":
            return SimpleNamespace(
                is_error=False,
                structured_content=get_order_summary(arguments["order_id"]),
                content=[],
            )
        return SimpleNamespace(is_error=True, structured_content=None, content=[])


class Stage05OfflineChecks(unittest.TestCase):
    def test_teaching_order_services_share_one_record(self) -> None:
        order = get_order_summary("acme-1007")
        shipment = get_shipment_status("ACME-1007")
        invoice = get_invoice_summary("ACME-1007")
        self.assertEqual(order["placed_on"], "2026-08-03")
        self.assertEqual(shipment["tracking_number"], "TEACH-7788")
        self.assertEqual(invoice["amount_paid"], order["amount_paid"])

    def test_unknown_order_is_rejected(self) -> None:
        with self.assertRaises(LookupError):
            get_order_summary("ACME-9999")

    def test_support_case_is_an_explicit_side_effect(self) -> None:
        case = create_support_case("ACME-1007", "Customer requests policy review")
        self.assertEqual(case["status"], "opened")
        self.assertTrue(case["case_id"].startswith("CASE-"))

    def test_support_guide_is_read_only_data(self) -> None:
        text = read_support_guide("refund-evidence")
        self.assertIn("verify the order record", text)

    def test_bridge_exposes_only_allowlisted_tools(self) -> None:
        async def scenario() -> None:
            registry = AsyncToolRegistry()
            client = FakeMCPClient()
            bridge = MCPToolBridge(
                client,
                namespace="support",
                allowed_remote_tools={"get_order_summary", "get_shipment_status"},
            )
            await bridge.populate(registry)
            names = {item["name"] for item in registry.schemas()}
            self.assertEqual(
                names,
                {"support__get_order_summary", "support__get_shipment_status"},
            )
            self.assertNotIn("support__create_support_case", names)

        asyncio.run(scenario())

    def test_bridge_preserves_namespace_and_remote_result(self) -> None:
        async def scenario() -> None:
            registry = AsyncToolRegistry()
            client = FakeMCPClient()
            await MCPToolBridge(
                client,
                namespace="support",
                allowed_remote_tools={"get_order_summary"},
            ).populate(registry)
            result = await registry.execute(
                "support__get_order_summary", {"order_id": "ACME-1007"}
            )
            self.assertEqual(result["order_id"], "ACME-1007")
            self.assertEqual(client.calls, [("get_order_summary", {"order_id": "ACME-1007"})])

        asyncio.run(scenario())

    def test_bridge_fails_closed_when_allowlisted_tool_is_missing(self) -> None:
        async def scenario() -> None:
            registry = AsyncToolRegistry()
            with self.assertRaisesRegex(RuntimeError, "not discovered"):
                await MCPToolBridge(
                    FakeMCPClient(),
                    namespace="support",
                    allowed_remote_tools={"missing_tool"},
                ).populate(registry)
            self.assertEqual(registry.schemas(), [])

        asyncio.run(scenario())

    def test_registry_rejects_unknown_local_tool(self) -> None:
        async def scenario() -> None:
            with self.assertRaises(KeyError):
                await AsyncToolRegistry().execute("support__missing", {})

        asyncio.run(scenario())

    def test_live_adapter_round_trip_uses_registry_result(self) -> None:
        async def scenario() -> None:
            from unittest.mock import patch
            import deepseek_mcp_agent
            from tiny_agent_mcp_bridge import Tool

            class FakeItem:
                type = "function_call"
                call_id = "call-1"
                name = "support__get_order_summary"
                arguments = '{"order_id":"ACME-1007"}'

                def model_dump(self, **_: object) -> dict[str, object]:
                    return {
                        "type": self.type,
                        "call_id": self.call_id,
                        "name": self.name,
                        "arguments": self.arguments,
                    }

            class FakeResponses:
                def __init__(self) -> None:
                    self.requests: list[dict[str, object]] = []

                def create(self, **kwargs: object) -> object:
                    self.requests.append(kwargs)
                    if len(self.requests) == 1:
                        return SimpleNamespace(
                            status="completed", output=[FakeItem()], output_text=""
                        )
                    return SimpleNamespace(
                        status="completed", output=[], output_text="verified"
                    )

            responses = FakeResponses()
            registry = AsyncToolRegistry()
            registry.register(
                Tool(
                    name="support__get_order_summary",
                    description="read order",
                    parameters={"type": "object"},
                    handler=lambda order_id: get_order_summary(order_id),
                    source="test",
                )
            )
            fake_client = SimpleNamespace(responses=responses)
            with patch.object(deepseek_mcp_agent, "create_model_client", return_value=fake_client), patch.dict(
                "os.environ", {"DEEPSEEK_MODEL": "test-model"}, clear=False
            ):
                answer = await deepseek_mcp_agent.run_agent(registry)

            self.assertEqual(answer, "verified")
            second_input = responses.requests[1]["input"]
            self.assertEqual(second_input[-1]["type"], "function_call_output")
            self.assertEqual(second_input[-1]["call_id"], "call-1")
            self.assertIn("ACME-1007", second_input[-1]["output"])

        asyncio.run(scenario())

    def test_live_adapter_cannot_execute_unregistered_remote_name(self) -> None:
        async def scenario() -> None:
            from unittest.mock import patch
            import deepseek_mcp_agent

            class FakeItem:
                type = "function_call"
                call_id = "call-write"
                name = "support__create_support_case"
                arguments = '{"order_id":"ACME-1007","reason":"open a case"}'

                def model_dump(self, **_: object) -> dict[str, object]:
                    return {
                        "type": self.type,
                        "call_id": self.call_id,
                        "name": self.name,
                        "arguments": self.arguments,
                    }

            fake_responses = SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    status="completed", output=[FakeItem()], output_text=""
                )
            )
            with patch.object(
                deepseek_mcp_agent,
                "create_model_client",
                return_value=SimpleNamespace(responses=fake_responses),
            ), patch.dict("os.environ", {"DEEPSEEK_MODEL": "test-model"}, clear=False):
                with self.assertRaises(KeyError):
                    await deepseek_mcp_agent.run_agent(AsyncToolRegistry(), max_model_turns=1)

        asyncio.run(scenario())


@unittest.skipUnless(MCP_AVAILABLE, "mcp SDK is not installed")
class Stage05MCPIntegrationChecks(unittest.TestCase):
    def test_discovery_keeps_primitives_distinct(self) -> None:
        async def scenario() -> None:
            from mcp import Client
            from mcp_server import mcp

            async with Client(mcp) as client:
                tools = await client.list_tools()
                resources = await client.list_resources()
                templates = await client.list_resource_templates()
                prompts = await client.list_prompts()
                self.assertEqual(
                    {tool.name for tool in tools.tools},
                    {
                        "get_order_summary",
                        "get_shipment_status",
                        "get_invoice_summary",
                        "create_support_case",
                    },
                )
                self.assertEqual([str(item.uri) for item in resources.resources], ["acme-support://about"])
                self.assertEqual([item.uri_template for item in templates.resource_templates], ["acme-support://guide/{topic}"])
                self.assertEqual([item.name for item in prompts.prompts], ["prepare_case_summary"])

        asyncio.run(scenario())

    def test_read_tools_return_structured_results(self) -> None:
        async def scenario() -> None:
            from mcp import Client
            from mcp_server import mcp

            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_order_summary", {"order_id": "ACME-1007"}
                )
                self.assertFalse(result.is_error)
                self.assertEqual(result.structured_content["placed_on"], "2026-08-03")

        asyncio.run(scenario())

    def test_business_failure_is_tool_error_result(self) -> None:
        async def scenario() -> None:
            from mcp import Client
            from mcp_server import mcp

            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_order_summary", {"order_id": "ACME-9999"}
                )
                self.assertTrue(result.is_error)

        asyncio.run(scenario())

    def test_bridge_with_real_client_does_not_expose_write_tool(self) -> None:
        async def scenario() -> None:
            from mcp import Client
            from mcp_server import mcp

            registry = AsyncToolRegistry()
            async with Client(mcp) as client:
                await MCPToolBridge(
                    client,
                    namespace="support",
                    allowed_remote_tools={
                        "get_order_summary",
                        "get_shipment_status",
                        "get_invoice_summary",
                    },
                ).populate(registry)
                names = {item["name"] for item in registry.schemas()}
                self.assertNotIn("support__create_support_case", names)
                order = await registry.execute(
                    "support__get_order_summary", {"order_id": "ACME-1007"}
                )
                self.assertEqual(order["order_id"], "ACME-1007")

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main(verbosity=2)

from __future__ import annotations

import asyncio

from mcp import Client
import mcp.types as types

from mcp_server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        prompts = await client.list_prompts()

        print("protocol:", client.protocol_version)
        print("tools:", [tool.name for tool in tools.tools])
        print("resources:", [str(item.uri) for item in resources.resources])
        print("resource templates:", [item.uri_template for item in templates.resource_templates])
        print("prompts:", [item.name for item in prompts.prompts])

        order = await client.call_tool("get_order_summary", {"order_id": "ACME-1007"})
        shipment = await client.call_tool("get_shipment_status", {"order_id": "ACME-1007"})
        print("order:", order.structured_content)
        print("shipment:", shipment.structured_content)

        guide = await client.read_resource("acme-support://guide/refund-evidence")
        first_resource = guide.contents[0]
        if isinstance(first_resource, types.TextResourceContents):
            print("guide:", first_resource.text)

        prompt = await client.get_prompt(
            "prepare_case_summary",
            {"order_id": "ACME-1007", "audience": "customer"},
        )
        first_message = prompt.messages[0]
        if isinstance(first_message.content, types.TextContent):
            print("prompt:", first_message.content.text)


if __name__ == "__main__":
    asyncio.run(main())

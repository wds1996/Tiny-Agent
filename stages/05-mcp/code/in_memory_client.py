"""Explore an MCP server without a subprocess or network socket."""

from __future__ import annotations

import asyncio

from mcp import Client
from mcp.types import TextContent, TextResourceContents

from mcp_server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        print("protocol:", client.protocol_version)
        print("server:", client.server_info)
        print("capabilities:", client.server_capabilities)

        tools = await client.list_tools()
        print("tools:", [tool.name for tool in tools.tools])
        for tool in tools.tools:
            print(f"  {tool.name} input schema = {tool.input_schema}")

        add_result = await client.call_tool("add", {"a": 20, "b": 22})
        print("add structured result:", add_result.structured_content)

        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        print("resources:", [str(resource.uri) for resource in resources.resources])
        print("resource templates:", [template.uri_template for template in templates.resource_templates])

        about = await client.read_resource("tiny-agent://about")
        if about.contents and isinstance(about.contents[0], TextResourceContents):
            print("about resource:", about.contents[0].text)

        prompts = await client.list_prompts()
        print("prompts:", [prompt.name for prompt in prompts.prompts])
        prompt = await client.get_prompt(
            "explain_stage",
            {"stage": "5", "audience": "beginner"},
        )
        for message in prompt.messages:
            if isinstance(message.content, TextContent):
                print("rendered prompt:", message.content.text)


if __name__ == "__main__":
    asyncio.run(main())

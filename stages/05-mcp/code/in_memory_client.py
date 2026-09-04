from __future__ import annotations

import asyncio

from mcp import Client
import mcp.types as types

from mcp_server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        print("protocol:", client.protocol_version)

        tools = await client.list_tools()
        print("tools:", [tool.name for tool in tools.tools])

        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        print("resources:", [str(resource.uri) for resource in resources.resources])
        print("resource templates:", [template.uri_template for template in templates.resource_templates])

        prompts = await client.list_prompts()
        print("prompts:", [prompt.name for prompt in prompts.prompts])

        tool_result = await client.call_tool("add", {"a": 20, "b": 22})
        print("structured tool result:", tool_result.structured_content)

        resource_result = await client.read_resource("tiny-agent://handbook/refunds")
        first_resource = resource_result.contents[0]
        if isinstance(first_resource, types.TextResourceContents):
            print("resource text:", first_resource.text)

        prompt_result = await client.get_prompt(
            "explain_mcp",
            {"topic": "Tools versus Resources", "audience": "beginner"},
        )
        first_message = prompt_result.messages[0]
        if isinstance(first_message.content, types.TextContent):
            print("prompt text:", first_message.content.text)


if __name__ == "__main__":
    asyncio.run(main())

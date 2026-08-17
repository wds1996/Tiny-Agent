"""Connect to the Stage 05 demo server over Streamable HTTP.

Start the server first:
    python stages/05-mcp/code/streamable_http_server.py

Then run this file in another terminal.
"""

from __future__ import annotations

import asyncio

from mcp import Client


async def main() -> None:
    async with Client("http://127.0.0.1:8000/mcp") as client:
        print("protocol:", client.protocol_version)
        print("server:", client.server_info)

        tools = await client.list_tools()
        print("tools:", [tool.name for tool in tools.tools])

        result = await client.call_tool("add", {"a": 7, "b": 8})
        print("add result:", result.structured_content)


if __name__ == "__main__":
    asyncio.run(main())

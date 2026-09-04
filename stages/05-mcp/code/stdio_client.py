from __future__ import annotations

import asyncio
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    server_path = Path(__file__).with_name("mcp_server.py")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
    )

    transport = stdio_client(parameters)
    async with Client(transport) as client:
        print("protocol:", client.protocol_version)
        tools = await client.list_tools()
        print("tools:", [tool.name for tool in tools.tools])
        result = await client.call_tool("add", {"a": 6, "b": 7})
        print("result:", result.structured_content)


if __name__ == "__main__":
    asyncio.run(main())

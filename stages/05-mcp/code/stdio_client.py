"""Launch the Stage 05 server as a subprocess and connect over stdio."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    server_file = Path(__file__).with_name("mcp_server.py").resolve()
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_file)],
    )

    transport = stdio_client(params)
    async with Client(transport) as client:
        print("negotiated protocol:", client.protocol_version)
        tools = await client.list_tools()
        print("discovered tools:", [tool.name for tool in tools.tools])

        result = await client.call_tool("stage_summary", {"stage": 5})
        print("result:", result.structured_content)


if __name__ == "__main__":
    asyncio.run(main())

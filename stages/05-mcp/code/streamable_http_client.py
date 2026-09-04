from __future__ import annotations

import asyncio

from mcp import Client


async def main() -> None:
    async with Client("http://127.0.0.1:8000/mcp") as client:
        print("protocol:", client.protocol_version)
        result = await client.call_tool("lookup_policy", {"topic": "shipping"})
        print("result:", result.structured_content)


if __name__ == "__main__":
    asyncio.run(main())

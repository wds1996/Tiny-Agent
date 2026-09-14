from __future__ import annotations

import asyncio

from mcp import Client


async def main() -> None:
    async with Client("http://127.0.0.1:8765/mcp") as client:
        result = await client.call_tool(
            "get_shipment_status", {"order_id": "ACME-1007"}
        )
        print("shipment:", result.structured_content)


if __name__ == "__main__":
    asyncio.run(main())

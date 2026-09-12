"""SDK 2.x stdio connection. The protocol is real; transport is local, not HTTP."""
from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import os
from pathlib import Path
import sys
from domain import BoundaryError

READ_TOOLS=frozenset({'list_orders','get_order','get_shipment','get_invoice','get_product','get_ticket'})
HOST_TOOLS=READ_TOOLS|{'create_ticket','execute_refund'}


class MCPBridge:
    def __init__(self, client):
        self.client=client

    async def discover(self) -> dict:
        result=await asyncio.wait_for(self.client.list_tools(),10)
        tools={t.name:t for t in result.tools}
        if not HOST_TOOLS <= tools.keys():
            raise BoundaryError('commerce_capabilities_missing')
        return tools

    async def call(self,name:str,arguments:dict)->dict:
        if name not in HOST_TOOLS: raise BoundaryError('mcp_tool_not_allowed')
        result=await asyncio.wait_for(self.client.call_tool(name,arguments),15)
        if result.is_error: raise BoundaryError('commerce_call_failed')
        value=result.structured_content
        if not isinstance(value,dict): raise BoundaryError('invalid_commerce_result')
        return value


@asynccontextmanager
async def connect(root:Path, profile_name:str):
    try:
        from mcp import Client, StdioServerParameters
    except ImportError as exc:
        raise RuntimeError('Install code/requirements.txt; MCP 2.x is required. No direct-call fallback is used.') from exc
    # Explicit minimal environment; never forward a DeepSeek key into the service.
    env={'PYTHONIOENCODING':'utf-8'}
    if os.name=='nt' and 'SYSTEMROOT' in os.environ: env['SYSTEMROOT']=os.environ['SYSTEMROOT']
    params=StdioServerParameters(command=sys.executable,
        args=[str(Path(__file__).with_name('mcp_server.py')),'--state-dir',str(root.resolve()),'--profile',profile_name],env=env)
    async with Client(params) as client:
        bridge=MCPBridge(client)
        await bridge.discover()
        yield bridge

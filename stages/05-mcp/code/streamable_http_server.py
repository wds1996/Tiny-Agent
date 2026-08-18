"""Serve the same Stage 05 capabilities over Streamable HTTP.

Run:
    python stages/05-mcp/code/streamable_http_server.py

Then connect with ``streamable_http_client.py``.
"""

from __future__ import annotations

from mcp_server import mcp


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8000,
        stateless_http=True,
        json_response=True,
    )

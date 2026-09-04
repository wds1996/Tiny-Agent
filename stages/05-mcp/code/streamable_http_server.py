from __future__ import annotations

from mcp_server import mcp


if __name__ == "__main__":
    mcp.run("streamable-http", host="127.0.0.1", port=8000)

"""Inspect a conceptual MCP 2026 wire exchange using only the stdlib.

This file is deliberately *not* an MCP implementation. It exists to make the
JSON-RPC request visible before the official SDK hides transport details.
"""

from __future__ import annotations

import json


request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "add",
        "arguments": {"a": 2, "b": 3},
        "_meta": {
            "io.modelcontextprotocol/clientInfo": {
                "name": "tiny-agent-wire-walkthrough",
                "version": "0.1.0",
            }
        },
    },
}

http_headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2026-07-28",
    "Mcp-Method": "tools/call",
    "Mcp-Name": "add",
}

response = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "content": [{"type": "text", "text": '{"result": 5}'}],
        "structuredContent": {"result": 5},
        "isError": False,
    },
}


print("=== HTTP routing/protocol metadata ===")
print(json.dumps(http_headers, indent=2))

print("\n=== JSON-RPC request body ===")
print(json.dumps(request, indent=2))

print("\n=== Conceptual successful response ===")
print(json.dumps(response, indent=2))

print(
    "\nImportant: use the official MCP SDK for real clients/servers. "
    "This walkthrough intentionally omits validation, negotiation, auth, "
    "streaming, cancellation, errors, and compatibility behavior."
)

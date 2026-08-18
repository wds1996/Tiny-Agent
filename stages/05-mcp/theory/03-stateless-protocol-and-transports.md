# 03 — MCP 2026: Stateless Core, Discovery, and Transports

This chapter is important because many MCP tutorials on the internet still teach the older lifecycle.

Tiny-Agent Stage 05 targets the **2026-07-28 MCP protocol revision** and the Python SDK v2 behavior.

The key migration idea is:

```text
older MCP
connect -> initialize -> session -> requests

2026 MCP
self-describing request -> response
```

The protocol became much more stateless at its core.

---

## 1. MCP still uses JSON-RPC messages

A conceptual request looks like:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "add",
    "arguments": {
      "a": 2,
      "b": 3
    }
  }
}
```

and a response is correlated by the same request id:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "structuredContent": {
      "result": 5
    }
  }
}
```

The official SDK should construct, validate, negotiate, and transport real MCP messages for you.

Our `protocol_message_walkthrough.py` is only a teaching microscope, not a home-made MCP implementation.

---

## 2. The old lifecycle: initialize and session

Earlier MCP revisions commonly taught:

```text
Client
  |
  | initialize
  v
Server
  |
  | initialize result
  v
Client
  |
  | initialized
  v
----- session begins -----
```

Over Streamable HTTP, a session identifier could tie subsequent requests to session state.

That architecture is why older Python examples often contain concepts such as:

```python
ClientSession(...)
await session.initialize()
```

and why old deployment discussions talk about session affinity/stickiness.

Those examples are historically valid for their protocol era.

They are not the best starting point for new 2026 code.

---

## 3. The 2026-07-28 core: no required initialize handshake

In the 2026 revision, a modern request carries the information needed to interpret it rather than depending on a previously initialized session.

The high-level idea is:

```text
request
├── protocol version
├── client identity/info
├── client capabilities
└── actual method + params
```

The result is a protocol core that can handle a request without requiring the old connection-wide initialize/initialized sequence.

A useful analogy:

### Older session-oriented style

You check into a hotel once, receive a wristband, and every later service knows you through the wristband.

### 2026 stateless style

Every courier package arrives with the routing and sender information necessary to process that package.

The second model is friendlier to ordinary horizontal HTTP scaling because a request does not inherently belong to one sticky worker.

---

## 4. `server/discover`

If the client wants server identity/capability information, the 2026 protocol provides discovery as an ordinary request rather than a mandatory opening handshake.

Conceptually:

```text
Client
  |
  | server/discover
  v
Server
  |
  | capabilities / server info
  v
Client
```

The important word is **ordinary**.

Discovery is useful, but the protocol does not require every request to be preceded by a session-opening ceremony.

---

## 5. Why the Python SDK `Client` still feels pleasantly simple

With the current high-level client:

```python
async with Client(server) as client:
    print(client.protocol_version)
    print(client.server_capabilities)
```

Entering the context handles connection and version compatibility for you.

For a modern v2 server, the client can use current discovery behavior.

For an older server, the SDK can fall back to the classic handshake.

This is an important design lesson:

> A high-level SDK can hide compatibility machinery without hiding the protocol model from the learner.

You should understand why old `initialize()` tutorials exist, while writing new application code against the current `Client` abstraction.

---

## 6. Stateless protocol does not mean your application has no state

This is a classic terminology trap.

Suppose a long-running task needs state:

```text
job id
cursor
transaction handle
workflow id
```

A stateless protocol request can still explicitly carry a handle:

```json
{
  "job_id": "job-123"
}
```

The difference is between:

```text
implicit connection/session state
```

and:

```text
explicit application state referenced by requests
```

So do not conclude:

```text
MCP 2026 is stateless
therefore stateful applications are impossible
```

That would be like saying HTTP is stateless, therefore shopping carts cannot exist.

---

# Part II — Transports

The protocol messages need a way to travel.

For Stage 05, learn two transports:

```text
stdio
Streamable HTTP
```

---

## 7. stdio: excellent for local subprocess servers

A host can launch an MCP server as a child process:

```text
Host process
     |
     | spawn
     v
MCP server process

stdin  <---- requests
stdout ----> responses
```

Python client setup:

```python
params = StdioServerParameters(
    command=sys.executable,
    args=["mcp_server.py"],
)

transport = stdio_client(params)

async with Client(transport) as client:
    tools = await client.list_tools()
```

This is a strong local-development model because:

```text
no TCP port required
process lifetime can be owned by host
simple local packaging
clear process boundary
```

---

## 8. The stdout rule

With stdio, stdout is the protocol channel.

So this is dangerous inside the server:

```python
print("hello debug world")
```

because random debug output can corrupt the protocol stream.

Use logging to stderr or the SDK's appropriate logging facilities instead.

A memorable rule:

> In a stdio MCP server, stdout is not your diary. It is the wire.

---

## 9. Streamable HTTP: the remote/service boundary

For a remotely reachable MCP service:

```python
async with Client(
    "http://127.0.0.1:8000/mcp"
) as client:
    ...
```

The server can expose the same MCP capabilities over HTTP.

Our demo runs:

```python
mcp.run(
    transport="streamable-http",
    host="127.0.0.1",
    port=8000,
    stateless_http=True,
    json_response=True,
)
```

There is an important version nuance:

- modern 2026-07-28 traffic is already handled using the new stateless request model;
- SDK options such as `stateless_http=True` mainly affect compatibility behavior for older, session-era clients;
- `json_response=True` asks the HTTP server to prefer direct JSON responses where appropriate.

Do not learn those flags as "the definition of MCP 2026 statelessness." The protocol revision is the deeper concept.

---

## 10. HTTP routing metadata

The 2026 HTTP protocol adds standardized routing metadata such as:

```text
MCP-Protocol-Version
Mcp-Method
Mcp-Name
```

For example, a gateway receiving a tool call can identify the MCP method/name without deeply parsing arbitrary application content first.

Our wire walkthrough prints a conceptual example:

```python
http_headers = {
    "MCP-Protocol-Version": "2026-07-28",
    "Mcp-Method": "tools/call",
    "Mcp-Name": "add",
}
```

Do not manually recreate HTTP protocol behavior in production; let the SDK do conformance work.

The code block exists so the abstraction stops feeling magical.

---

## 11. What about old HTTP+SSE tutorials?

You may find tutorials centered on a dedicated legacy SSE transport.

Treat them as historical material.

For new Stage 05 work, prefer:

```text
local -> stdio
remote -> Streamable HTTP
```

The current protocol still uses streaming where a method needs a stream, but that is different from choosing the old standalone SSE transport as the architecture for a new server.

---

## 12. Why transports should not leak into Agent logic

Bad architecture:

```python
if tool_is_stdio:
    agent_logic_a()
elif tool_is_http:
    agent_logic_b()
```

Better:

```text
Transport
   ↓
MCP Client
   ↓
MCPToolBridge
   ↓
Tiny-Agent Tool
   ↓
Agent logic
```

The Agent should care about capability semantics, not whether bytes arrived through a subprocess pipe or HTTP connection.

---

## 13. Version migration cheat sheet

When reading external tutorials, translate mentally:

```text
FastMCP (older Python SDK v1 high-level name)
    -> MCPServer in SDK v2

manual ClientSession + initialize()
    -> high-level Client context in SDK v2

mandatory session-centric mental model
    -> 2026 self-describing/stateless core

legacy standalone SSE transport
    -> prefer stdio or Streamable HTTP for new work
```

Do not label old code "wrong." It may simply target an older protocol/SDK revision.

Your job is to identify the version before copying it.

---

## Completion check

You should be able to explain:

1. Why older MCP examples contain `initialize()`.
2. What changed in the 2026-07-28 stateless core.
3. Why `server/discover` is not the old mandatory initialization handshake.
4. Why protocol statelessness does not forbid application state.
5. When stdio is appropriate.
6. When Streamable HTTP is appropriate.
7. Why Agent logic should not depend directly on transport type.
8. Why a modern tutorial should not default to the legacy SSE transport.

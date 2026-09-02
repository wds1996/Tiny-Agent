# 03 — MCP 2026: Stateless Core, Discovery, Transports, and Extensions

This chapter matters because a large amount of MCP material still teaches the older session-oriented lifecycle. Tiny-Agent targets the **2026-07-28 MCP protocol revision** and Python SDK v2.

The migration idea is:

```text
older MCP
connect -> initialize -> session -> requests

MCP 2026
self-describing request -> response
+ optional discovery
+ explicit extensions for additional workflows
```

The protocol became simpler at its core while moving richer behavior into explicit request flows and extensions.

---

## 1. MCP still uses JSON-RPC semantics

Conceptual Tool call:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "add",
    "arguments": {"a": 2, "b": 3}
  }
}
```

Conceptual response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "structuredContent": {"result": 5}
  }
}
```

Use the official SDK for real encoding, negotiation, validation, and transport. `protocol_message_walkthrough.py` is a teaching microscope, not a home-made protocol stack.

---

## 2. Why the old lifecycle had `initialize()`

Earlier MCP revisions commonly taught:

```text
Client -- initialize --> Server
Client <-- result ----- Server
Client -- initialized -> Server
          session
```

Over HTTP, subsequent requests could be tied to session state. That is why old examples contain:

```python
ClientSession(...)
await session.initialize()
```

and deployment guides discuss sticky sessions.

Those examples are not nonsense; they target an older protocol generation. Version archaeology is part of modern Agent engineering.

---

## 3. 2026 stateless core

Modern requests carry enough information to be interpreted without the old mandatory connection-wide handshake.

High-level shape:

```text
request
├── protocol version
├── client information/capabilities
├── method/name routing metadata
└── method parameters
```

Analogy:

- old style: hotel check-in, then use a session wristband;
- 2026 style: each courier package contains the routing/sender information needed to process that package.

The second is friendlier to ordinary horizontal HTTP scaling because a request does not inherently belong to one sticky worker.

---

## 4. `server/discover` is optional discovery, not mandatory ceremony

A client may ask for server identity/capability information through an ordinary discovery request.

```text
Client -> server/discover -> Server
Client <- capabilities ---- Server
```

Discovery is useful when the client wants a catalog up front. It is not a protocol-level session opening ritual.

The SDK's high-level `Client` keeps compatibility machinery out of application code:

```python
async with Client(server) as client:
    print(client.protocol_version)
    print(client.server_capabilities)
```

The learner should understand why old `initialize()` code exists without manually reproducing negotiation in every new application.

---

## 5. Stateless protocol != stateless application

A long-running operation may still need:

```text
job_id
cursor
transaction/workflow handle
artifact id
```

The state is referenced explicitly:

```json
{"job_id": "job-123"}
```

rather than hidden in a transport session.

Saying "MCP is stateless, therefore stateful applications are impossible" is like saying HTTP is stateless, therefore shopping carts are forbidden by physics.

---

# Part II — Transports

## 6. stdio: local subprocess boundary

```text
Host process
    | spawn
    v
MCP server process

stdin  <---- requests
stdout ----> responses
```

Example shape:

```python
params = StdioServerParameters(
    command=sys.executable,
    args=["mcp_server.py"],
)

transport = stdio_client(params)
async with Client(transport) as client:
    tools = await client.list_tools()
```

Advantages:

- no TCP port;
- host can own process lifetime;
- simple local packaging;
- clear process boundary.

### The stdout rule

In stdio, stdout is the protocol wire.

```python
print("debug: hello")  # dangerous on protocol stdout
```

Use stderr/logging instead.

> stdout is not your diary. It is the wire.

---

## 7. Streamable HTTP: remote/service boundary

Client:

```python
async with Client("http://127.0.0.1:8000/mcp") as client:
    tools = await client.list_tools()
```

Tiny-Agent's demo server uses the SDK's Streamable HTTP runner. The core idea is:

```text
local integration  -> stdio
remote service     -> Streamable HTTP
```

Do not define "2026 stateless MCP" by one SDK flag. The protocol revision is the deeper semantic change; SDK flags also exist for compatibility behavior.

---

## 8. Header-based routing

Modern HTTP requests expose routing metadata including concepts such as:

```text
MCP-Protocol-Version
Mcp-Method
Mcp-Name
```

A gateway can therefore route or apply policy using standardized method/tool identity without deeply interpreting arbitrary Tool arguments first.

Conceptual teaching example:

```python
headers = {
    "MCP-Protocol-Version": "2026-07-28",
    "Mcp-Method": "tools/call",
    "Mcp-Name": "search_papers",
}
```

Let the official SDK implement the actual wire protocol.

---

## 9. Legacy HTTP+SSE

The old standalone HTTP+SSE transport is legacy/deprecated architecture for new work. Learn it when maintaining older systems, but start new Stage 05 designs with stdio or Streamable HTTP.

Streaming still exists where a method needs it. That is different from making a dedicated legacy SSE transport the default server architecture.

---

# Part III — Why extensions exist

The 2026 core deliberately stays small. Richer optional capabilities can evolve through a negotiated **extensions framework**.

Conceptually:

```text
small stable core
      +
negotiated extension IDs
      +
versioned extension behavior
```

This is healthier than forcing every experiment into the core protocol forever.

Extension advertisement is still not authorization. "Both endpoints understand this feature" does not mean "this caller may use it."

---

## 10. Tasks extension: long-running remote Tool work

Some Tools cannot reasonably finish inside one short request.

Conceptual lifecycle:

```text
client advertises Tasks support
        ↓
tools/call
        ↓
server decides to create a task
        ↓
returns task handle
        ↓
client: tasks/get / tasks/update / tasks/cancel
        ↓
terminal result
```

The key abstraction is a **remote capability task handle**, not a hidden connection session.

Do not confuse four different IDs:

```text
MCP task id        -> remote capability execution
service run_id     -> your deployed Agent job
thread/checkpoint  -> Agent orchestration state
TaskLedger item    -> sub-work in Tiny-Agent long-horizon harness
```

One research run may contain all four.

A useful systems question is: *who owns cancellation at each layer?*

---

## 11. MRTR: Multi Round-Trip Requests

Older server-initiated requests assumed a held-open bidirectional interaction. MCP 2026 restructures flows such as elicitation/sampling around explicit multi-round request/response semantics.

Conceptually:

```text
client -> original operation
server -> input_required + requested information
client -> retry/continue with inputResponses
server -> result
```

This preserves interactive workflows without making a permanent session the hidden source of truth.

Think of it as a form asking you for one missing field, not a server reaching through the screen and borrowing your keyboard.

Hosts still decide whether requested user/model interaction is allowed.

---

## 12. MCP Apps

MCP Apps allow a server to associate interactive UI with capabilities. A Host may render that UI in a sandboxed boundary and route actions back through governed MCP interactions.

Critical invariant:

```text
rendered UI
!= authority
```

A button labeled "Delete everything" has not acquired permission merely because it is visually convincing.

The Host still owns consent, authentication, authorization, and execution boundaries.

---

## 13. Cacheable catalogs and deterministic ordering

Capability list responses can be stable/cacheable so clients do not repeatedly rebuild large Tool catalogs and destabilize upstream prompt caches.

This links directly to Stage 06A context engineering:

```text
server owns many capabilities
-> client caches/discovers catalog
-> Host selects relevant subset
-> only needed Tool schemas enter model context
```

Protocol discovery and model context are separate layers.

---

## 14. Authorization hardening

MCP's protocol-level authorization direction aligns more closely with standard OAuth/OIDC deployment practices. But keep three questions separate:

```text
discovery:       what exists?
authentication: who is the caller?
authorization:  may this caller perform this action?
```

A Tool appearing in `tools/list` answers only the first question.

Stage 07 and Stage 10 own the broader runtime/service policy story.

---

## 15. Transport must not leak into Agent logic

Bad:

```python
if tool_is_stdio:
    agent_logic_a()
elif tool_is_http:
    agent_logic_b()
```

Better:

```text
stdio / HTTP
    ↓
MCP Client
    ↓
MCPToolBridge
    ↓
Tiny-Agent Tool
    ↓
Agent/Workflow logic
```

The Agent cares about capability semantics; the adapter cares how protocol bytes travel.

---

## 16. Version migration cheat sheet

When reading older material:

```text
FastMCP (older v1 high-level API)
    -> MCPServer in SDK v2

manual ClientSession + initialize()
    -> high-level Client context for current code

session-centric transport state
    -> 2026 self-describing/stateless core

legacy standalone SSE
    -> stdio / Streamable HTTP for new designs
```

Do not combine snippets from three generations and then accuse Python of betrayal.

---

## 17. Worked architecture: long-running data analysis

Suppose an Agent needs an external MCP Tool to process a large dataset.

```text
Authenticated Agent service
        ↓
Agent run_id = run-42
        ↓
MCP tools/call(process_dataset)
        ↓
MCP task_id = mcp-task-7
        ↓
remote worker progresses
        ↓
Tiny-Agent persists run/task mapping
        ↓
client disconnects / web worker restarts
        ↓
new worker loads run-42
        ↓
checks mcp-task-7
        ↓
result artifact
```

The MCP task solves remote capability execution. Your service still owns user/tenant identity, run durability, policy, artifact access, and final Agent state.

---

## Completion check

You should be able to explain:

1. why older MCP examples contain `initialize()`;
2. what the 2026 stateless core changes;
3. why `server/discover` is not the old mandatory handshake;
4. why stateless transport does not forbid application state;
5. stdio vs Streamable HTTP;
6. why old standalone SSE is legacy for new work;
7. what Extensions solve;
8. Tasks vs Agent run/checkpoint/TaskLedger;
9. how MRTR enables interactive multi-round flows;
10. why MCP Apps UI does not grant authority;
11. why discovery, authentication, and authorization remain separate;
12. why Agent logic should remain transport-independent.

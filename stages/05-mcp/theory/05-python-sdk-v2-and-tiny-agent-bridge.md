# 05 — Python SDK v2 and the Tiny-Agent Bridge

Now that the protocol model is clear, we can finally enjoy the framework convenience.

The order matters:

```text
Why MCP exists
    ↓
Tools / Resources / Prompts
    ↓
stateless protocol + transports
    ↓
security boundary
    ↓
Python SDK v2
```

If you begin at the last line, MCP can look like a collection of decorators.

If you understand the first four, the decorators become obvious conveniences.

---

## 1. Current Python SDK high-level server: `MCPServer`

Stage 05 targets Python SDK v2:

```python
from mcp.server import MCPServer

mcp = MCPServer(
    "Tiny-Agent Stage 05 Demo"
)
```

Then register primitives:

```python
@mcp.tool()
def add(a: int, b: int) -> dict[str, int]:
    return {"result": a + b}

@mcp.resource("tiny-agent://about")
def about() -> str:
    return "Tiny-Agent ..."

@mcp.prompt()
def explain_stage(stage: str) -> str:
    return f"Explain Stage {stage}."
```

The SDK handles protocol schemas and server plumbing around the Python functions.

---

## 2. Why you may see `FastMCP` online

Older Python SDK v1 tutorials commonly use:

```python
from mcp.server.fastmcp import FastMCP
```

That was the high-level v1 API.

In v2, the current high-level server is named:

```python
MCPServer
```

This is not merely a cosmetic rename: v2 also aligns with the 2026 protocol architecture and a new high-level client.

When copying a tutorial, identify its SDK generation first.

A surprisingly large percentage of "why does this import fail?" debugging is actually archaeology.

---

## 3. Current high-level client: `Client`

The v2 client is intentionally ergonomic:

```python
from mcp import Client

async with Client(server) as client:
    tools = await client.list_tools()
```

Inside the context, useful connection facts are already available:

```python
client.protocol_version
client.server_info
client.server_capabilities
client.instructions
```

You normally do not manually call:

```python
await session.initialize()
```

The high-level client handles current-version discovery/negotiation and compatibility with older servers.

---

## 4. One client interface, several transports

### In-process

```python
async with Client(mcp) as client:
    ...
```

Great for:

```text
unit tests
teaching
deterministic integration tests
```

No subprocess, no port, minimal moving parts.

### stdio

```python
params = StdioServerParameters(
    command=sys.executable,
    args=["mcp_server.py"],
)

transport = stdio_client(params)

async with Client(transport) as client:
    ...
```

Great for local external processes.

### Streamable HTTP

```python
async with Client(
    "http://127.0.0.1:8000/mcp"
) as client:
    ...
```

Appropriate for a service boundary.

The Agent-facing code should not need a different Tool abstraction for each transport.

---

## 5. Why MCP made Tiny-Agent's sync-only Tool layer insufficient

Before Stage 05:

```python
Tool.invoke(...)
ToolRegistry.execute(...)
```

assumed a handler returned immediately.

But an MCP call naturally looks like:

```python
result = await client.call_tool(...)
```

A tempting bad solution is:

```python
def handler(...):
    return asyncio.run(
        client.call_tool(...)
    )
```

This explodes when an event loop is already running, which is common in:

```text
web servers
notebooks
async Agent runtimes
LangGraph applications
MCP clients themselves
```

Nested event-loop hacks are a reliable way to turn a tutorial into a future Stack Overflow question.

---

## 6. Tiny-Agent's backward-compatible async Tool path

Stage 05 adds:

```python
await tool.ainvoke(arguments)
```

and:

```python
await registry.aexecute(
    name,
    arguments,
)
```

The async path supports both synchronous and asynchronous handlers:

```python
async def ainvoke(self, arguments):
    result = self.handler(**arguments)

    if inspect.isawaitable(result):
        return await result

    return result
```

The old sync path remains available for Stage 01 code.

If it accidentally receives an async handler, it fails explicitly rather than returning a coroutine object:

```text
Tool 'remote' is asynchronous;
use Tool.ainvoke() or ToolRegistry.aexecute()
```

That is a much better failure mode than sending this to the model:

```text
<coroutine object handler at 0x...>
```

---

## 7. The MCPToolBridge

The bridge's responsibility is deliberately narrow:

```text
MCP Tool description/schema
        ↓
Tiny-Agent Tool description/schema

Tiny-Agent Tool invocation
        ↓
MCP client.call_tool(...)
        ↓
normalized result/error
```

Usage:

```python
registry = ToolRegistry()

async with Client(mcp) as client:
    bridge = MCPToolBridge(
        client,
        namespace="demo",
    )

    await bridge.populate_registry(
        registry
    )
```

If the server exposes:

```text
add
stage_summary
```

Tiny-Agent sees:

```text
demo__add
demo__stage_summary
```

---

## 8. Why namespace at the bridge?

A real host may connect to many MCP servers:

```text
github -> search
notion -> search
jira   -> search
```

A flat ToolRegistry cannot safely register three tools named `search`.

So the host can define origin-aware names:

```text
github__search
notion__search
jira__search
```

This is a small but useful example of a larger principle:

> Remote protocol names do not have to become your application's internal names unchanged.

Adapters are allowed to normalize boundaries.

---

## 9. How discovery becomes a Tiny-Agent Tool

Conceptually:

```python
tools = await client.list_tools()

for remote in tools.tools:
    local = Tool(
        name=namespace(remote.name),
        description=remote.description,
        parameters=dict(
            remote.input_schema
        ),
        handler=async_remote_handler,
    )
```

Now the existing Tiny-Agent model/provider layer can receive ordinary schemas:

```python
registry.schemas()
```

The LLM does not need to know how the tool was discovered.

From its perspective:

```text
local Python Tool
MCP remote Tool
```

can share one normalized interface.

That is exactly what adapters are for.

---

## 10. Structured result vs text result

An MCP tool may return structured content:

```python
{
    "result": 42
}
```

The bridge prefers:

```python
result.structured_content
```

when available.

Otherwise it renders MCP content blocks into text.

This preserves useful machine-readable data instead of prematurely flattening everything into prose.

The same engineering rule appears repeatedly:

> Delay information loss until you actually need a lower-fidelity representation.

---

## 11. Why Resources and Prompts do not go through the bridge

The bridge only maps executable capabilities:

```text
MCP Tool -> Tiny-Agent Tool
```

It does not register:

```text
Resource as fake Tool
Prompt as fake Tool
```

A future host integration can separately expose APIs like:

```python
await context_provider.read_resource(...)
await prompt_catalog.get_prompt(...)
```

That preserves the protocol's semantics and avoids turning `ToolRegistry` into an everything-registry.

---

## 12. Where would AgentRuntime fit?

The existing Stage 01 `AgentRuntime` is synchronous.

Therefore the clean long-term architecture is not:

```text
force async MCP into sync runtime
```

but:

```text
sync teaching runtime        -> stays simple
async-capable tool boundary  -> introduced now
future async production runtime/orchestration
                             -> can await remote capabilities naturally
```

Stage 05 prepares the abstraction boundary without rewriting earlier learning snapshots.

This is exactly why the project keeps:

```text
stages/
```

and:

```text
src/tiny_agent/
```

as separate concepts.

---

## 13. Migration traps to recognize

When reading an MCP tutorial, check for these clues:

| You see | Likely meaning |
|---|---|
| `FastMCP` | Python SDK v1-era high-level server |
| `ClientSession` + `initialize()` | classic handshake-era client style |
| standalone SSE transport | legacy transport architecture |
| `MCPServer` + `Client` | Python SDK v2 high-level API |
| `protocol_version == "2026-07-28"` | current protocol revision |

Older examples remain useful for understanding history and compatibility.

Do not mix their lifecycle assumptions into new v2 code accidentally.

---

## Completion check

You should now be able to answer:

1. Why does SDK v2 use `MCPServer` and `Client` in our examples?
2. Why is `Client(mcp)` useful for tests?
3. Why was an async Tool execution path needed?
4. Why is `asyncio.run()` inside each remote Tool handler a poor architecture?
5. What exactly does `MCPToolBridge` translate?
6. Why does it namespace remote tool names?
7. Why are Resources and Prompts deliberately not inserted into `ToolRegistry`?
8. How can old Stage 01 synchronous teaching code coexist with new async remote capabilities?

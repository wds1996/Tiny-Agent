# Stage 05 — MCP: Standardized Capabilities Across Boundaries

Stage 05 teaches **Model Context Protocol (MCP)** as an interoperability protocol for connecting AI applications to external capabilities and context.

This stage targets the **MCP 2026-07-28 protocol revision** and the **official Python SDK v2**.

That version note matters. A large amount of existing MCP material still teaches the older session/initialize lifecycle and Python SDK v1 APIs.

The learning order is deliberate:

```text
local hard-coded ToolRegistry
        ↓
why a standard protocol is useful
        ↓
MCP Host / Client / Server mental model
        ↓
Tools / Resources / Prompts
        ↓
JSON-RPC wire shape
        ↓
2025-era session model vs 2026 stateless core
        ↓
in-process MCPServer + Client
        ↓
stdio local process boundary
        ↓
Streamable HTTP service boundary
        ↓
Tiny-Agent MCP Tool bridge
        ↓
trust / authorization / security boundaries
```

The goal is **not** to memorize MCP decorators.

The goal is to understand what MCP standardizes, what it deliberately does not own, and how it fits into the Agent architecture we built in Stages 00–04.

---

# Prerequisites

Complete Stage 00–04, or already understand:

- message-based LLM interaction;
- Structured Output / Function Calling;
- provider-neutral Tool schemas;
- ReAct Agent runtime;
- Workflow vs Agent control ownership;
- explicit state/orchestration;
- RAG and external evidence boundaries;
- basic async Python concepts (`async`, `await`, async context managers).

You do **not** need prior MCP experience.

---

# The central lesson

Keep this sentence visible throughout the stage:

> **Function Calling standardizes how a model proposes a structured action inside an application; MCP standardizes how an application discovers and invokes capabilities/context across an external protocol boundary.**

They solve different layers and work well together.

Tiny-Agent uses:

```text
MCP Server
    ↓ discover Tools
MCP Client
    ↓
MCPToolBridge
    ↓ normalize
Tiny-Agent ToolRegistry
    ↓ schemas
Model / Function Calling
    ↓ proposal
Tiny-Agent runtime / policy
    ↓ authorized execution
MCP Client.call_tool(...)
```

MCP does not replace the Agent runtime.

It gives the runtime a standardized capability source.

---

# Learning objectives

After this stage, you should be able to:

1. explain what problem MCP solves;
2. distinguish MCP from Function Calling;
3. distinguish MCP from an Agent framework;
4. explain Host, Client, and Server responsibilities;
5. explain Tools, Resources, and Prompts without flattening them into one abstraction;
6. discover MCP capabilities from a client;
7. call a Tool and interpret `structured_content`, `content`, and `is_error`;
8. read fixed Resources and understand resource templates;
9. list and render Prompts;
10. explain why the 2026-07-28 MCP core no longer requires the old `initialize/initialized` session handshake;
11. explain what `server/discover` does;
12. distinguish protocol statelessness from application state;
13. explain stdio vs Streamable HTTP;
14. recognize legacy standalone SSE tutorials as older architecture;
15. build an MCP server with the current Python SDK v2 `MCPServer` API;
16. consume it with the v2 `Client` API;
17. explain why remote tool execution is naturally async;
18. use Tiny-Agent's `ToolRegistry.aexecute()` path;
19. adapt discovered MCP Tools into Tiny-Agent Tools;
20. namespace tools from multiple external servers;
21. explain why capability discovery is not authorization;
22. treat remote Resources, Prompts, and Tool results as untrusted external data;
23. explain why server annotations are hints rather than security guarantees;
24. identify migration traps in v1 / pre-2026 tutorials.

---

# Part A — MCP mental model

Read:

1. [`theory/01-mcp-mental-model.md`](theory/01-mcp-mental-model.md)
2. [`theory/02-tools-resources-prompts.md`](theory/02-tools-resources-prompts.md)
3. [`code/protocol_message_walkthrough.py`](code/protocol_message_walkthrough.py)

At this point you should understand:

```text
Function Calling
    !=
MCP

MCP
    !=
Agent
```

and:

```text
Tool      = executable capability
Resource  = readable context/data
Prompt    = reusable model-facing template
```

Do not continue until those distinctions feel natural.

---

# Part B — Current MCP protocol model

Read:

4. [`theory/03-stateless-protocol-and-transports.md`](theory/03-stateless-protocol-and-transports.md)

This chapter deliberately replaces the old roadmap item:

```text
03-client-server-lifecycle.md
```

because the current protocol architecture changed substantially.

The comparison to remember is:

```text
classic / older MCP
connect
  -> initialize
  -> initialized
  -> session-oriented requests

MCP 2026-07-28
self-describing request
  -> response

optional server/discover
  -> ordinary capability discovery request
```

The official Python SDK v2 `Client` handles current discovery/version compatibility and can fall back when talking to older servers.

---

# Part C — Build one server, inspect all three primitives

Read/run:

5. [`code/mcp_server.py`](code/mcp_server.py)
6. [`code/in_memory_client.py`](code/in_memory_client.py)

The demo server intentionally stays small:

```text
Tools
├── add
└── stage_summary

Resources
├── tiny-agent://about
└── tiny-agent://stage/{stage}

Prompt
└── explain_stage
```

Why so small?

Because a tutorial that exposes 37 tools before explaining the difference between Tool and Resource has optimized for screenshot density, not learning.

The in-memory client uses:

```python
async with Client(mcp) as client:
    ...
```

This is ideal for learning and tests because there is no network or subprocess hiding the protocol concepts.

---

# Part D — stdio process boundary

Run:

7. [`code/stdio_client.py`](code/stdio_client.py)

It launches `mcp_server.py` as a subprocess and connects through stdio.

Mental model:

```text
Tiny-Agent / Host process
        |
        | spawn
        v
MCP server process

stdin  <--- protocol request
stdout ---> protocol response
```

Important rule:

> **stdout is the protocol wire.**

Do not casually `print()` debug messages from a stdio server to stdout.

Use stderr/logging instead.

---

# Part E — Streamable HTTP service boundary

Start the server:

```bash
python stages/05-mcp/code/streamable_http_server.py
```

In another terminal:

```bash
python stages/05-mcp/code/streamable_http_client.py
```

Read:

8. [`code/streamable_http_server.py`](code/streamable_http_server.py)
9. [`code/streamable_http_client.py`](code/streamable_http_client.py)

Use this mental model:

```text
local integration
    -> stdio

remote/service integration
    -> Streamable HTTP
```

Do not start new Stage 05 architecture from old standalone SSE tutorials.

---

# Part F — Integrate MCP Tools into Tiny-Agent

Read:

10. [`theory/05-python-sdk-v2-and-tiny-agent-bridge.md`](theory/05-python-sdk-v2-and-tiny-agent-bridge.md)
11. [`../../src/tiny_agent/mcp_bridge.py`](../../src/tiny_agent/mcp_bridge.py)
12. [`code/tiny_agent_mcp_bridge.py`](code/tiny_agent_mcp_bridge.py)
13. [`../../src/tiny_agent/tool.py`](../../src/tiny_agent/tool.py)
14. [`../../tests/test_async_tools.py`](../../tests/test_async_tools.py)
15. [`../../tests/test_stage05_mcp.py`](../../tests/test_stage05_mcp.py)

Stage 05 adds a backward-compatible async capability path:

```python
await tool.ainvoke(...)
await registry.aexecute(...)
```

This is required because a remote MCP call naturally uses:

```python
await client.call_tool(...)
```

We deliberately do **not** hide async calls inside repeated `asyncio.run()` wrappers.

---

# Part G — Security and trust boundaries

Read last:

16. [`theory/04-mcp-security-boundaries.md`](theory/04-mcp-security-boundaries.md)
17. [`exercises/review-questions.md`](exercises/review-questions.md)

This order is intentional: first understand what the protocol can do, then reason about what the host should allow it to do.

The security invariant is:

```text
Server advertises
    ↓
Client discovers
    ↓
Host filters / authorizes
    ↓
Model may propose
    ↓
Runtime validates
    ↓
Authorized call executes
```

Not:

```text
Server advertised it
    ↓
YOLO
```

---

# Installation

The Tiny-Agent core remains dependency-light:

```bash
python -m pip install -e ".[dev]"
```

Install Stage 05 MCP dependencies with:

```bash
python -m pip install -e ".[stage05]"
```

For Stage 05 tests:

```bash
python -m pip install -e ".[dev,stage05]"
```

The Stage 05 extra currently targets:

```text
mcp[cli] >= 2, < 3
```

This keeps MCP optional for readers working only through earlier stages.

---

# Recommended runnable order

```bash
# 1. No server process/network: inspect the protocol shape
python stages/05-mcp/code/protocol_message_walkthrough.py

# 2. Current SDK server/client in one Python process
python stages/05-mcp/code/in_memory_client.py

# 3. Launch server automatically as a stdio subprocess
python stages/05-mcp/code/stdio_client.py

# 4. Adapt discovered MCP Tools into Tiny-Agent
python stages/05-mcp/code/tiny_agent_mcp_bridge.py

# 5. Remote HTTP boundary (two terminals)
python stages/05-mcp/code/streamable_http_server.py
python stages/05-mcp/code/streamable_http_client.py
```

---

# Current-version warning: old tutorials are everywhere

If an external tutorial shows primarily:

```python
FastMCP(...)
ClientSession(...)
await session.initialize()
```

or builds a new server around the old standalone SSE transport, stop and check its version/date.

Those APIs and lifecycle explanations may be correct for MCP/Python SDK v1-era material.

This Stage 05 module intentionally teaches the current SDK v2 / 2026 protocol model first, then explains how to recognize the historical architecture.

Do not mix snippets from different protocol generations into one file and then accuse Python of betrayal.

---

# External learning resources

Use external resources in this order.

## 1. Official MCP documentation

- MCP documentation: <https://modelcontextprotocol.io/>
- 2026-07-28 protocol release overview: <https://blog.modelcontextprotocol.io/posts/2026-07-28/>

Use the official protocol material as the source of truth for current semantics.

## 2. Official Python SDK

- Python SDK repository: <https://github.com/modelcontextprotocol/python-sdk>
- SDK v2 — what changed: <https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/whats-new.md>
- Client guide: <https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/client/index.md>
- Running/transports guide: <https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/index.md>

The SDK changes faster than a static blog post, so when code signatures disagree, prefer the current official SDK docs.

## 3. Security

- MCP security best practices: <https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices>

Read this before treating a third-party server catalog as a bag of harmless plugins.

---

# Stage architecture

```text
                      external MCP boundary

+-------------------------------------------------------------+
|                         MCP Server                          |
|                                                             |
|   Tools                 Resources              Prompts       |
+-----+----------------------+----------------------+----------+
      |                      |                      |
      |                      | separate semantics   |
      v                      v                      v
+-------------------------------------------------------------+
|                          MCP Client                         |
+---------------------------+---------------------------------+
                            |
                            | Tools only
                            v
                   +------------------+
                   |  MCPToolBridge   |
                   +--------+---------+
                            |
                     Tiny-Agent Tool
                            |
                            v
                   +------------------+
                   |   ToolRegistry   |
                   +--------+---------+
                            |
                    schemas / aexecute
                            |
                            v
                   Agent / Workflow / Host
```

The bridge is intentionally narrow.

It does not turn Tiny-Agent into an MCP-shaped codebase.

---

# What this stage deliberately does not pretend to solve

Stage 05 teaches the current protocol and a clean integration boundary.

It does not claim to finish:

- enterprise OAuth architecture;
- arbitrary third-party server sandboxing;
- production approval UI;
- distributed retry/circuit-breaker policy;
- full async AgentRuntime redesign;
- multi-server dynamic lifecycle management;
- organization-wide MCP registry/governance;
- production audit logging and observability;
- prompt-injection defense for all remote context;
- OS-level isolation for untrusted local servers.

Those concerns connect strongly to Stages 06–10.

The important thing today is to establish the correct architectural boundaries so later production features have somewhere sane to live.

---

# Stage milestone

You have completed Stage 05 when you can:

```text
build MCPServer
    ↓
discover Tools / Resources / Prompts with Client
    ↓
call/read/render the correct primitive
    ↓
explain 2026 stateless MCP vs older handshake MCP
    ↓
run the same capability in-process / stdio / HTTP
    ↓
bridge MCP Tools into Tiny-Agent
    ↓
execute remote tools asynchronously
    ↓
explain why discovery never grants authorization
```

The key question is no longer merely:

> "How do I connect a tool?"

It becomes:

> **How do I connect capabilities through a standard protocol while preserving internal abstractions, origin, trust, authorization, and execution boundaries?**

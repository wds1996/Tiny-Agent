# 01 — MCP Mental Model: Why a Protocol Exists

MCP stands for **Model Context Protocol**.

The shortest useful definition is:

> MCP is a standard protocol for an AI application to discover and use capabilities and context exposed by external servers.

The word to focus on is **protocol**.

MCP is not a new reasoning algorithm, not a smarter LLM, and not an Agent framework.

---

## 1. Start from the problem we already have

In Stage 01, Tiny-Agent registers local Python tools directly:

```python
registry = ToolRegistry([
    Tool(
        name="add",
        description="Add two numbers",
        parameters={...},
        handler=add,
    )
])
```

This is excellent when the capability lives inside the same application.

But imagine a real Agent platform that needs:

```text
GitHub
Google Drive
internal database
browser service
payment service
company knowledge system
local developer tools
```

Without a common protocol, every integration invents its own:

```text
connection format
capability discovery
schema representation
invocation method
error representation
authentication story
transport story
lifecycle conventions
```

You end up maintaining a zoo of adapters.

A slightly unfair but memorable analogy:

> Without a protocol, every appliance arrives with a different-shaped wall socket. Your Agent desk slowly becomes an archaeological site of power adapters.

MCP tries to standardize the socket.

It does **not** decide what electricity should be used for.

---

## 2. Function Calling and MCP solve different layers

This distinction is essential.

### Function Calling

A model/provider interaction commonly looks like:

```text
Application
   |
   | gives schemas
   v
Model
   |
   | proposes tool call
   v
Application runtime
```

The model says something like:

```json
{
  "name": "add",
  "arguments": {
    "a": 20,
    "b": 22
  }
}
```

Function Calling answers:

> How can a model express a structured request to use a capability?

### MCP

MCP lives on another boundary:

```text
AI Application / Host
        |
        | MCP Client
        v
   MCP Server
        |
        +-- Tools
        +-- Resources
        +-- Prompts
```

MCP answers questions such as:

> What capabilities does this external server expose?
>
> What schema does a tool accept?
>
> How do I call it through a standard protocol?
>
> What resources or prompts are available?

Therefore:

```text
Function Calling
    model <-> application control proposal

MCP
    application <-> external capability/context server protocol
```

They can be used together.

Tiny-Agent Stage 05 does exactly that:

```text
MCP Server
   |
   | discover MCP Tool schema
   v
MCPToolBridge
   |
   | normalize
   v
Tiny-Agent ToolRegistry
   |
   | schema visible to model
   v
Function Calling / ReAct runtime
```

MCP does not replace the Agent loop. It gives the Agent loop a standardized source of capabilities.

---

## 3. Host, Client, and Server

You will often see three roles.

### Host

The **host** is the AI application that owns the overall user experience and policy.

Examples:

```text
IDE Agent
chat application
desktop assistant
Tiny-Agent application
```

The host should own high-level concerns such as:

```text
which servers are trusted
which server a user may access
approval policy
credentials
permission narrowing
what reaches the model
what gets logged
```

### Client

An **MCP client** is the protocol participant that talks to an MCP server.

A host can own multiple clients:

```text
                    +--> MCP Client --> Git server
                    |
Host / AI App ------+--> MCP Client --> Docs server
                    |
                    +--> MCP Client --> Database server
```

The client handles protocol details such as requests, responses, discovery, and transport behavior.

### Server

An **MCP server** exposes capabilities/context through standard MCP primitives.

For example:

```text
CompanyDocsServer
├── Tool: search_documents
├── Resource: docs://handbook
└── Prompt: summarize_policy
```

The server describes what it offers.

The host still decides what the application is willing to use.

---

## 4. MCP does not magically create trust

A server can advertise:

```text
Tool name: harmless_read_file
Description: "Totally safe, definitely not suspicious."
```

That description is data from the server.

It is not a security proof.

The same principle from previous Tiny-Agent stages survives:

> Model/server output proposes information and capabilities; application policy owns authorization.

MCP standardizes communication. It does not eliminate trust boundaries.

---

## 5. Discovery changes the integration model

With a hard-coded local integration, the application already knows:

```python
registry.register(add_tool)
```

With MCP, the application can ask the server what it exposes:

```python
async with Client(server) as client:
    tools = await client.list_tools()

    for tool in tools.tools:
        print(tool.name)
        print(tool.input_schema)
```

This means a client can integrate against a capability catalog rather than importing each Python function directly.

That is a major interoperability improvement.

But discovery is not authorization.

A useful rule is:

```text
Server advertises
        ↓
Client discovers
        ↓
Host filters / approves
        ↓
Model may see allowed subset
        ↓
Runtime may execute allowed call
```

Do not collapse those arrows into one magical `connect_everything=True` switch.

---

## 6. MCP does not make a system more agentic

Suppose a deterministic program does:

```text
connect to MCP server
list resource
read resource
print result
```

That program uses MCP.

It is not necessarily an Agent.

Likewise:

```text
MCP != Agent
MCP != LangGraph
MCP != RAG
```

MCP is an interoperability layer that can be used inside any of those architectures.

A Stage 02 deterministic workflow can use MCP.

A Stage 03 LangGraph can use MCP.

A Stage 04 RAG pipeline can obtain data from an MCP server.

A Stage 01 ReAct Agent can execute MCP tools.

---

## 7. Tiny-Agent's Stage 05 architecture

We deliberately preserve Tiny-Agent's existing contracts:

```text
                  external boundary
                         |
                         v
              +--------------------+
              |    MCP Client      |
              +---------+----------+
                        |
                 list_tools / call_tool
                        |
                        v
              +--------------------+
              |   MCPToolBridge    |
              +---------+----------+
                        |
                 Tiny-Agent Tool
                        |
                        v
              +--------------------+
              |    ToolRegistry    |
              +---------+----------+
                        |
                        v
                 Agent / Workflow
```

Notice what is *not* happening:

```text
MCP SDK replaces ToolRegistry       X
MCP server becomes the Agent        X
MCP tool gets automatic permission  X
```

The bridge adapts one boundary while leaving the rest of the architecture intact.

---

## 8. Why this is good software architecture

The Agent runtime depends on a small internal representation:

```python
Tool(
    name=...,
    description=...,
    parameters=...,
    handler=...,
)
```

MCP-specific concerns remain at the edge:

```text
MCP inputSchema
MCP CallToolResult
MCP transport
MCP errors
```

This is the same provider-neutral idea we used in Stage 01 for model APIs and Stage 04 for retrievers.

The internal system does not need to become MCP-shaped everywhere merely because one external boundary uses MCP.

---

## Completion check

Before moving on, you should be able to answer:

1. What problem does MCP standardize?
2. Why is Function Calling not the same thing as MCP?
3. What responsibilities belong to host, client, and server?
4. Why does capability discovery not imply authorization?
5. Why can a deterministic workflow use MCP without becoming an Agent?
6. Why does Tiny-Agent use an adapter instead of rewriting its runtime around MCP types?

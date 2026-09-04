# 02 — Tools, Resources, and Prompts: Three Primitives, Three Meanings

A beginner-friendly MCP server often exposes three primitive categories:

```text
Tools
Resources
Prompts
```

A common mistake is to think:

> "They all eventually become text for the LLM, so why not make everything a Tool?"

Because **how something is selected and what authority it carries matter**.

If everything is a Tool, your protocol design starts resembling a kitchen where the recipe book, refrigerator, and chef's knife are all labeled `execute()`.

Technically possible. Not a great kitchen.

---

## 1. Tool: executable capability

A Tool represents an operation the client can invoke.

Example:

```python
@mcp.tool()
def add(a: int, b: int) -> dict[str, int]:
    """Add two integers."""
    return {"result": a + b}
```

The server exposes metadata including a name, description, and input schema.

A client can discover it:

```python
tools = await client.list_tools()

for tool in tools.tools:
    print(tool.name)
    print(tool.input_schema)
```

and invoke it:

```python
result = await client.call_tool(
    "add",
    {"a": 20, "b": 22},
)
```

A successful result may include:

```text
content
structured_content
is_error
```

Tiny-Agent's bridge prefers structured content when available because:

```python
{"result": 42}
```

is easier for application code to preserve than forcing everything through:

```text
"The result is forty-two."
```

---

## 2. Tool errors are protocol results, not always transport crashes

Suppose the server tool raises:

```python
raise ValueError("Unknown stage")
```

At the MCP application layer, the client can receive a tool result marked as an error:

```python
result.is_error is True
```

That is different from:

```text
network connection died
invalid JSON-RPC message
server process disappeared
```

This distinction matters because an Agent may reasonably observe:

```text
ToolError: Unknown stage
```

and choose another action, while a transport failure may need retry/backoff or operational handling.

Tiny-Agent converts a model-visible MCP tool failure into `MCPToolError` at the bridge boundary so the application can distinguish it explicitly.

---

## 3. Resource: readable context identified by URI

A Resource is for data/context that can be read.

Example:

```python
@mcp.resource("tiny-agent://about")
def about() -> str:
    return (
        "Tiny-Agent teaches Agent engineering "
        "from mechanism to production."
    )
```

A client can discover fixed resources:

```python
resources = await client.list_resources()
```

and read one:

```python
result = await client.read_resource(
    "tiny-agent://about"
)
```

The mental model is closer to:

```text
read this context
```

than:

```text
execute this action
```

That difference should remain visible in your application design.

---

## 4. Resource templates

Sometimes the set of possible resources is parameterized.

Example:

```python
@mcp.resource("tiny-agent://stage/{stage}")
def stage_resource(stage: str) -> str:
    ...
```

Conceptually:

```text
tiny-agent://stage/1
tiny-agent://stage/2
tiny-agent://stage/5
```

Listing every possible URI would be silly, so MCP can expose a resource template instead.

The client can inspect templates:

```python
templates = await client.list_resource_templates()
```

and still read a concrete URI:

```python
await client.read_resource(
    "tiny-agent://stage/5"
)
```

This is useful for things such as:

```text
files://project/{path}
database://table/{name}
docs://article/{id}
```

provided the server enforces authorization and validation correctly.

---

## 5. Prompt: reusable model-facing template

A Prompt represents a reusable prompt/workflow template exposed by the server.

Example:

```python
@mcp.prompt()
def explain_stage(
    stage: str,
    audience: str = "beginner",
) -> str:
    return (
        f"Explain Tiny-Agent Stage {stage} "
        f"to a {audience}."
    )
```

The client can discover prompts:

```python
prompts = await client.list_prompts()
```

and render one:

```python
prompt = await client.get_prompt(
    "explain_stage",
    {
        "stage": "5",
        "audience": "beginner",
    },
)
```

Notice that retrieving a prompt is not the same as executing a side-effecting tool.

The result is model-facing content/messages that the host can decide how to use.

---

## 6. A useful control mental model

A common conceptual shorthand is:

```text
Tool      -> model may choose an action
Resource  -> application may choose context
Prompt    -> user/application may choose a reusable prompt
```

Do not interpret this as a security mechanism built into the names themselves.

It is a useful design distinction about **who typically initiates selection** and **what the primitive means**.

The host still owns actual permissions and policy.

---

## 7. Why not expose a document as `read_document()` Tool?

Sometimes you can.

But compare:

```text
Tool:
read_document(path="handbook.md")
```

with:

```text
Resource:
docs://handbook
```

The Resource makes the semantics explicit:

> This is context/data that can be read.

A Tool says:

> This is an executable operation.

That distinction helps UIs, clients, permission models, discovery, and future maintainers understand the system.

Do not destroy useful semantics merely because both can eventually return text.

---

## 8. Tiny-Agent deliberately bridges only Tools

Our Stage 05 bridge does this:

```text
MCP Tool
  ↓
Tiny-Agent Tool
```

It does **not** do:

```text
MCP Resource -> fake Tool
MCP Prompt   -> fake Tool
```

Why?

Because Tiny-Agent's `ToolRegistry` is specifically an executable-capability abstraction.

Resources and Prompts deserve separate consumption paths when the integrated runtime later needs them.

This keeps semantics honest.

---

## 9. Tool schema is still not authorization

Suppose a server exposes:

```json
{
  "name": "delete_repository",
  "inputSchema": {
    "type": "object",
    "properties": {
      "repo": {"type": "string"}
    }
  }
}
```

A valid schema tells us:

```text
what arguments are structurally acceptable
```

It does not tell us:

```text
whether this user may delete that repository
whether this server is trusted
whether human approval is required
```

Schema validation and authorization are separate layers.

Stage 09 will deepen this, but Stage 05 must keep the boundary correct from day one.

---

## 10. A complete teaching server

The Stage 05 demo intentionally exposes all three primitives:

```python
mcp = MCPServer("Tiny-Agent Stage 05 Demo")

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

This is more educational than building a server with fifteen tools and never explaining why Resources or Prompts exist.

---

## Completion check

You should now be able to explain:

1. What makes a Tool semantically different from a Resource?
2. When is a resource template useful?
3. What does a Prompt return conceptually?
4. Why does Tiny-Agent bridge only MCP Tools into `ToolRegistry`?
5. Why is a valid Tool schema not an authorization decision?
6. What is the difference between an MCP tool error and a broken transport?

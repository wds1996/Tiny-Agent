# 02 — Tools、Resources、Prompts：三种 Primitive，三种语义

一个适合初学者的 MCP Server 常见三类 primitive：

```text
Tools
Resources
Prompts
```

常见误区是：

> “反正最后都可能变成给 LLM 的文本，为什么不全部做成 Tool？”

因为 **如何被选择、它代表什么语义、以及它可能携带什么 authority，都很重要。**

如果一切都是 Tool，你的 protocol design 就像厨房里把菜谱、冰箱和菜刀都统一标成 `execute()`。

技术上不是绝对不行，但这厨房很难维护。

---

## 1. Tool：可执行 capability

Tool 表示 client 可以 invoke 的 operation。

```python
@mcp.tool()
def add(a: int, b: int) -> dict[str, int]:
    """Add two integers."""
    return {"result": a + b}
```

Server 暴露 name、description、input schema 等 metadata。

Client discovery：

```python
tools = await client.list_tools()

for tool in tools.tools:
    print(tool.name)
    print(tool.input_schema)
```

Invoke：

```python
result = await client.call_tool(
    "add",
    {"a": 20, "b": 22},
)
```

成功结果可能包含：

```text
content
structured_content
is_error
```

Tiny-Agent bridge 在存在时优先保留 `structured_content`，因为：

```python
{"result": 42}
```

比过早扁平化成：

```text
"The result is forty-two."
```

更适合 application 继续处理。

---

## 2. Tool error 不总是 transport crash

如果 server Tool 内部：

```python
raise ValueError("Unknown stage")
```

MCP application layer 可能收到：

```python
result.is_error is True
```

这与下面这些不同：

```text
network connection died
invalid JSON-RPC message
server process disappeared
```

Agent 可以把一个正常返回的 Tool-level failure 当 observation，并尝试 repair/choose another action；transport failure 更可能进入 retry/backoff/operational handling。

Tiny-Agent bridge 会把 model-visible MCP Tool failure 转换为显式 `MCPToolError`。

---

## 3. Resource：用 URI 标识的 readable context/data

Resource 更适合“读取数据/上下文”。

```python
@mcp.resource("tiny-agent://about")
def about() -> str:
    return (
        "Tiny-Agent teaches Agent engineering "
        "from mechanism to production."
    )
```

Client 可以：

```python
resources = await client.list_resources()
```

然后：

```python
result = await client.read_resource(
    "tiny-agent://about"
)
```

它的语义更接近：

```text
read this context
```

而不是：

```text
execute this action
```

这个区别应当保留在 application design 中。

---

## 4. Resource template

某些 Resource URI 是参数化集合：

```python
@mcp.resource("tiny-agent://stage/{stage}")
def stage_resource(stage: str) -> str:
    ...
```

概念上：

```text
tiny-agent://stage/1
tiny-agent://stage/2
tiny-agent://stage/5
```

不需要把所有可能 URI 全列出来。MCP 可以暴露 resource template：

```python
templates = await client.list_resource_templates()
```

然后读取具体 URI：

```python
await client.read_resource(
    "tiny-agent://stage/5"
)
```

适合：

```text
files://project/{path}
database://table/{name}
docs://article/{id}
```

前提仍然是 server 正确做 authorization 与 validation。

---

## 5. Prompt：可复用 model-facing template

Prompt 表示 server 暴露的 reusable prompt/workflow template。

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

Client discovery：

```python
prompts = await client.list_prompts()
```

Render：

```python
prompt = await client.get_prompt(
    "explain_stage",
    {
        "stage": "5",
        "audience": "beginner",
    },
)
```

获取 Prompt 与执行 side-effecting Tool 不是一回事。返回的是 model-facing content/messages，Host 再决定如何使用。

---

## 6. 一个有用的 control mental model

常见 shorthand：

```text
Tool      -> model may choose an action
Resource  -> application may choose context
Prompt    -> user/application may choose a reusable prompt
```

这只是 selection semantics 的心智模型，不是名字自带的 security system。

真正 permission/policy 仍归 Host。

---

## 7. 为什么不把 document 全做成 `read_document()` Tool

有时当然可以。

比较：

```text
Tool:
read_document(path="handbook.md")
```

与：

```text
Resource:
docs://handbook
```

Resource 明确表达：

> 这是 readable context/data。

Tool 表达：

> 这是 executable operation。

这种 distinction 对 UI、client、permission model、discovery、维护者都更有信息量。

不要因为“都能返回 text”，就把所有语义磨平成一个接口。

---

## 8. Tiny-Agent 故意只 bridge Tools

Stage 05 bridge：

```text
MCP Tool
  ↓
Tiny-Agent Tool
```

不会做：

```text
MCP Resource -> fake Tool
MCP Prompt   -> fake Tool
```

因为 Tiny-Agent `ToolRegistry` 的语义就是 executable capability registry。

Resources/Prompts 以后应有独立 consumption path。

这叫保持语义诚实。

---

## 9. Tool schema 仍然不是 authorization

Server 暴露：

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

Schema 只能告诉我们：

```text
什么 arguments 结构合法
```

不能告诉我们：

```text
这个 user 是否能删除 repo
server 是否可信
是否需要 human approval
```

Schema validation 与 authorization 是两个不同层。

---

## 10. 完整教学 server

Stage 05 demo 同时暴露三类 primitive：

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

比“堆十五个 Tool 但从不解释 Resource/Prompt 为什么存在”更有教学价值。

---

## 完成检查

你应该能解释：

1. Tool 与 Resource 的语义区别；
2. resource template 什么时候有价值；
3. Prompt 概念上返回什么；
4. Tiny-Agent 为什么只把 MCP Tool bridge 到 `ToolRegistry`；
5. valid Tool schema 为什么不代表授权；
6. MCP Tool error 与 broken transport 有什么区别。
# 05 — Python SDK v2 与 Tiny-Agent Bridge

现在 protocol model 已经清楚，终于可以放心享受 framework convenience。

顺序很重要：

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

如果直接从最后一行开始，MCP 很容易看起来像“一堆 decorator”。理解前四层之后，decorator 才会变成真正有意义的便利。

---

## 1. 当前 Python SDK 高层 server：`MCPServer`

Stage 05 面向 SDK v2：

```python
from mcp.server import MCPServer

mcp = MCPServer(
    "Tiny-Agent Stage 05 Demo"
)
```

然后注册 primitive：

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

SDK 负责围绕 Python function 构造 protocol schema 与 server plumbing。

---

## 2. 为什么网上经常看到 `FastMCP`

旧 Python SDK v1 高层 API 常见：

```python
from mcp.server.fastmcp import FastMCP
```

v2 当前高层 server 则是：

```python
MCPServer
```

这不只是 cosmetic rename；v2 还与 2026 protocol architecture、新 high-level client 对齐。

复制教程前先识别 SDK generation。

很多“为什么 import 失败”的 debug，本质上是考古，不是 Python 语法问题。

---

## 3. 当前高层 Client：`Client`

v2 client：

```python
from mcp import Client

async with Client(server) as client:
    tools = await client.list_tools()
```

Context 内可以直接得到：

```python
client.protocol_version
client.server_info
client.server_capabilities
client.instructions
```

通常不需要手工：

```python
await session.initialize()
```

High-level Client 会处理 current-version discovery/negotiation 与 older-server compatibility。

---

## 4. 一个 Client interface，多种 transport

### In-process

```python
async with Client(mcp) as client:
    ...
```

适合：

```text
unit tests
teaching
deterministic integration tests
```

无 subprocess、无 port、移动部件最少。

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

适合 local external process。

### Streamable HTTP

```python
async with Client(
    "http://127.0.0.1:8000/mcp"
) as client:
    ...
```

适合 service boundary。

Agent-facing code 不应因为 transport 变化就换一整套 Tool abstraction。

---

## 5. 为什么 MCP 暴露了 Tiny-Agent sync-only Tool layer 的局限

Stage 05 前：

```python
Tool.invoke(...)
ToolRegistry.execute(...)
```

默认 handler 同步返回。

但 remote MCP call 天然是：

```python
result = await client.call_tool(...)
```

一个诱人的坏方案：

```python
def handler(...):
    return asyncio.run(
        client.call_tool(...)
    )
```

如果当前已经运行 event loop，就会出问题；而这恰恰常见于：

```text
web servers
notebooks
async Agent runtimes
LangGraph applications
MCP clients themselves
```

Nested event-loop hack 是把教程提前变成未来 Stack Overflow 问题的高效方法。

---

## 6. Tiny-Agent backward-compatible async Tool path

Stage 05 增加：

```python
await tool.ainvoke(arguments)
```

以及：

```python
await registry.aexecute(
    name,
    arguments,
)
```

Async path 同时支持 sync/async handler：

```python
async def ainvoke(self, arguments):
    result = self.handler(**arguments)

    if inspect.isawaitable(result):
        return await result

    return result
```

旧 sync path 继续服务 Stage 01 code。

如果 sync path 意外收到 async handler，应显式失败，而不是把 coroutine object 当 Tool result：

```text
Tool 'remote' is asynchronous;
use Tool.ainvoke() or ToolRegistry.aexecute()
```

这比把下面这种东西喂给 model 好得多：

```text
<coroutine object handler at 0x...>
```

---

## 7. `MCPToolBridge`

Bridge 的责任故意很窄：

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

用法：

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

Remote server 暴露：

```text
add
stage_summary
```

Tiny-Agent local interface：

```text
demo__add
demo__stage_summary
```

---

## 8. 为什么 namespace 放在 bridge

真实 Host 可能同时连接：

```text
github -> search
notion -> search
jira   -> search
```

Flat ToolRegistry 无法安全注册三个 `search`。

Host 可以用 origin-aware local name：

```text
github__search
notion__search
jira__search
```

这体现了更一般的原则：

> Remote protocol name 不必原封不动成为 application internal global name。

Adapter 本来就应该 normalize boundary。

---

## 9. Discovery 如何变成 Tiny-Agent Tool

概念代码：

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

已有 model/provider layer 仍只看到：

```python
registry.schemas()
```

LLM 不需要知道这个 Tool 是本地 Python 还是 MCP remote Tool。

这正是 adapter 的价值。

---

## 10. Structured result vs text result

MCP Tool 可能返回：

```python
{
    "result": 42
}
```

Bridge 在可用时优先：

```python
result.structured_content
```

否则再把 MCP content blocks 渲染成 text。

这里延续一条通用工程原则：

> **在真正需要低保真表示之前，不要过早丢失结构化信息。**

---

## 11. 为什么 Resources / Prompts 不经过 Tool bridge

Bridge 只映射：

```text
MCP Tool -> Tiny-Agent Tool
```

不会注册：

```text
Resource as fake Tool
Prompt as fake Tool
```

未来 Host 可以独立提供：

```python
await context_provider.read_resource(...)
await prompt_catalog.get_prompt(...)
```

这样保留 protocol semantics，也防止 `ToolRegistry` 变成“什么都往里塞”的 EverythingRegistry。

---

## 12. `AgentRuntime` 应该放在哪里

Stage 01 `AgentRuntime` 是 synchronous teaching runtime。

长期正确架构不是：

```text
force async MCP into sync runtime
```

而是：

```text
sync teaching runtime        -> stays simple
async-capable tool boundary  -> introduced now
future async production runtime/orchestration
                             -> awaits remote capabilities naturally
```

Stage 05 先准备 abstraction boundary，而不是为了新功能重写早期教学 snapshot。

这也是项目同时保留：

```text
stages/
```

与：

```text
src/tiny_agent/
```

的原因。

---

## 13. Migration trap

| 看到的 API/模式 | 通常意味着 |
|---|---|
| `FastMCP` | Python SDK v1-era high-level server |
| `ClientSession` + `initialize()` | classic handshake-era client style |
| standalone SSE | legacy transport architecture |
| `MCPServer` + `Client` | Python SDK v2 high-level API |
| `protocol_version == "2026-07-28"` | current protocol revision |

旧示例仍有历史与兼容价值，但不要把 lifecycle assumption 无意混入新 v2 code。

---

## 完成检查

你应该能回答：

1. SDK v2 为什么使用 `MCPServer` / `Client`？
2. `Client(mcp)` 为什么适合测试？
3. 为什么需要 async Tool execution path？
4. 为什么在每个 remote handler 内 `asyncio.run()` 是坏架构？
5. `MCPToolBridge` 精确翻译什么？
6. 为什么 namespace remote Tool？
7. Resources / Prompts 为什么不进入 `ToolRegistry`？
8. Stage 01 sync teaching code 如何与新的 async remote capability 共存？
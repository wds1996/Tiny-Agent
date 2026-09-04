# 03 — MCP 2026：Stateless Core、Discovery、Transports 与 Extensions

这一章非常重要，因为大量 MCP 材料仍然在教授旧的 session-oriented lifecycle。Tiny-Agent 当前面向：

```text
MCP protocol: 2026-07-28
Python SDK: v2
```

核心迁移可以概括为：

```text
older MCP
connect -> initialize -> session -> requests

MCP 2026
self-describing request -> response
+ optional discovery
+ explicit extensions for richer workflows
```

Core 变得更小、更 stateless；更复杂的行为则进入显式 request flow 与 extension。

---

## 1. MCP 仍采用 JSON-RPC 语义

概念 Tool call：

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

概念 response：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "structuredContent": {"result": 5}
  }
}
```

真实 encoding、negotiation、validation、transport 应交给 official SDK。

`protocol_message_walkthrough.py` 是教学显微镜，不是鼓励你手搓一套 MCP protocol stack。

---

## 2. 为什么旧 lifecycle 有 `initialize()`

较早 MCP revision 常见：

```text
Client -- initialize --> Server
Client <-- result ----- Server
Client -- initialized -> Server
          session
```

HTTP 后续 request 也可能依赖 session state，所以旧教程会出现：

```python
ClientSession(...)
await session.initialize()
```

以及 sticky session 相关部署讨论。

这些教程不是“错”，而是属于不同 protocol generation。

现代 Agent engineering 有一项隐形技能：版本考古。

---

## 3. 2026 stateless core

现代 request 自带足够信息，不再依赖旧式 mandatory connection-wide handshake。

高层结构可以理解为：

```text
request
├── protocol version
├── client information/capabilities
├── method/name routing metadata
└── method parameters
```

类比：

- 旧式：先酒店 check-in，之后一直靠 session wristband；
- 2026：每个快递包裹本身包含处理它所需的 routing/sender 信息。

后者更适合普通 horizontal HTTP scaling，因为 request 不天然绑定某个 sticky worker。

---

## 4. `server/discover` 是 optional discovery，不是 mandatory ceremony

Client 可以用普通 discovery request 获取 server identity/capability：

```text
Client -> server/discover -> Server
Client <- capabilities ---- Server
```

它可以用于提前拿 catalog，但不是“开启 protocol session”的仪式。

SDK v2 高层 `Client` 把 compatibility machinery 藏在 application 之外：

```python
async with Client(server) as client:
    print(client.protocol_version)
    print(client.server_capabilities)
```

学习者应该知道旧 `initialize()` 为什么存在，但不需要在每个新 application 里手工复刻旧 negotiation。

---

## 5. Stateless protocol != stateless application

Long-running operation 仍然可以有：

```text
job_id
cursor
transaction/workflow handle
artifact id
```

区别是 state 被显式引用：

```json
{"job_id": "job-123"}
```

而不是藏在 transport session 中。

“Protocol stateless，所以 application 不能有 state”就像说“HTTP stateless，所以购物车违反物理定律”。

---

# Part II — Transports

## 6. stdio：local subprocess boundary

```text
Host process
    | spawn
    v
MCP server process

stdin  <---- requests
stdout ----> responses
```

示例：

```python
params = StdioServerParameters(
    command=sys.executable,
    args=["mcp_server.py"],
)

transport = stdio_client(params)
async with Client(transport) as client:
    tools = await client.list_tools()
```

优势：

- 无 TCP port；
- Host 管理 process lifetime；
- local packaging 简洁；
- process boundary 清晰。

### stdout 规则

stdio 模式下 stdout 是 protocol wire：

```python
print("debug: hello")  # protocol stdout 上很危险
```

请使用 stderr/logging。

> stdout 不是你的日记本，它是线缆。

---

## 7. Streamable HTTP：remote/service boundary

```python
async with Client("http://127.0.0.1:8000/mcp") as client:
    tools = await client.list_tools()
```

心智模型：

```text
local integration  -> stdio
remote service     -> Streamable HTTP
```

不要用某一个 SDK flag 来定义“2026 stateless MCP”。更深层的是 protocol semantic change；SDK flag 还可能服务 compatibility。

---

## 8. Header-based routing

现代 HTTP request 可以暴露 method/tool identity 等 routing metadata，例如：

```text
MCP-Protocol-Version
Mcp-Method
Mcp-Name
```

Gateway 可以基于标准化 method/tool identity 做 route/policy，而不必先深度解析任意 Tool arguments。

概念教学示例：

```python
headers = {
    "MCP-Protocol-Version": "2026-07-28",
    "Mcp-Method": "tools/call",
    "Mcp-Name": "search_papers",
}
```

真实 wire protocol 仍由 official SDK 实现。

---

## 9. Legacy HTTP+SSE

旧 standalone HTTP+SSE transport 对新项目属于 legacy/deprecated architecture。

维护旧系统时仍要认识它；新 Stage 05 design 应从 stdio 或 Streamable HTTP 开始。

Method 内部需要 streaming 并不等于要把 dedicated legacy SSE transport 作为默认 server architecture。

---

# Part III — 为什么需要 Extensions

2026 core 故意保持小。更丰富的 optional capability 通过 negotiated **extensions framework** 演进。

```text
small stable core
      +
negotiated extension IDs
      +
versioned extension behavior
```

这比把每个实验特性永久塞进 core protocol 更健康。

Extension advertisement 依然不是 authorization：

```text
双方都理解 feature
!= caller 被允许使用 feature
```

---

## 10. Tasks extension：long-running remote Tool work

某些 Tool 不可能在一个短 request 内完成。

概念 lifecycle：

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

关键 abstraction 是 **remote capability task handle**，不是 hidden connection session。

必须区分四种 ID：

```text
MCP task id        -> remote capability execution
service run_id     -> deployed Agent job
thread/checkpoint  -> Agent orchestration state
TaskLedger item    -> Tiny-Agent long-horizon harness sub-work
```

同一个 research run 完全可能同时拥有这四种 ID。

系统设计时还要问：每一层的 cancellation 到底由谁拥有？

---

## 11. MRTR：Multi Round-Trip Requests

旧式 server-initiated request 更依赖 held-open bidirectional session。MCP 2026 把 elicitation/sampling 等交互重构成显式 multi-round request/response。

概念上：

```text
client -> original operation
server -> input_required + requested information
client -> retry/continue with inputResponses
server -> result
```

这样可以支持 interactive workflow，而不把 permanent session 当 hidden source of truth。

它更像“表单缺一个字段，请你补一下”，而不是 server 从屏幕里伸手过来借你的键盘。

Host 仍然决定是否允许 requested user/model interaction。

---

## 12. MCP Apps

MCP Apps 允许 server 为 capability 关联 interactive UI。Host 可以在 sandboxed boundary 中渲染 UI，再通过 governed MCP interaction 回传 action。

关键不变量：

```text
rendered UI
!= authority
```

一个视觉上很有说服力的“Delete everything”按钮，并没有因此获得权限。

Consent、authentication、authorization、execution boundary 仍然由 Host 控制。

---

## 13. Cacheable catalogs 与 deterministic ordering

Capability list 可以稳定/cacheable，避免 client 每次重建巨大 Tool catalog，也有利于上游 prompt cache 稳定。

这直接连接 Stage 07 context engineering：

```text
server owns many capabilities
-> client caches/discovers catalog
-> Host selects relevant subset
-> only needed Tool schemas enter model context
```

Protocol discovery 与 model context selection 是不同层。

---

## 14. Authorization hardening

2026 protocol authorization 方向更加贴近标准 OAuth/OIDC deployment practice。

仍然要分清：

```text
discovery:       what exists?
authentication: who is the caller?
authorization:  may this caller perform this action?
```

Tool 出现在 `tools/list` 里，只回答第一问。

Stage 09/10 再完整展开 runtime/service policy。

---

## 15. Transport 不应泄漏进 Agent logic

坏设计：

```python
if tool_is_stdio:
    agent_logic_a()
elif tool_is_http:
    agent_logic_b()
```

更好：

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

Agent 关心 capability semantics；adapter 关心 protocol bytes 怎么走。

---

## 16. Version migration cheat sheet

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

不要把三代 snippet 混在一起，然后得出“Python 今天心情不好”的结论。

---

## 17. Worked architecture：long-running data analysis

假设 Agent 调一个 external MCP Tool 处理大数据集：

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

MCP task 解决 remote capability execution；你的 service 仍负责 user/tenant identity、run durability、policy、artifact access 与 final Agent state。

---

## 完成检查

你应该能够解释：

1. 为什么旧 MCP 示例有 `initialize()`；
2. 2026 stateless core 改了什么；
3. 为什么 `server/discover` 不是旧 mandatory handshake 的简单改名；
4. 为什么 stateless transport 不禁止 application state；
5. stdio vs Streamable HTTP；
6. standalone SSE 为什么对新项目是 legacy；
7. Extensions 解决什么；
8. MCP Tasks vs Agent run/checkpoint/TaskLedger；
9. MRTR 如何支持 interactive multi-round flow；
10. MCP Apps UI 为什么不获得 authority；
11. discovery/authentication/authorization 为什么必须分开；
12. Agent logic 为什么应该 transport-independent。
# Stage 05 — MCP：跨边界标准化能力与上下文

Stage 05 系统讲解 **Model Context Protocol（MCP）**：它是一套让 AI application 以标准协议连接外部 capability 与 context 的 interoperability protocol。

本阶段面向：

```text
MCP protocol revision: 2026-07-28
Official Python SDK: v2
```

版本信息非常重要，因为大量现有 MCP 教程仍然讲的是较早的 session/initialize lifecycle 与 Python SDK v1 API。

教学顺序刻意安排为：

```text
local hard-coded ToolRegistry
        ↓
为什么需要标准 protocol
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

目标不是背 MCP decorator，而是理解：**MCP 到底标准化什么、故意不负责什么，以及它如何接入 Stage 00–04 已经建立的 Agent architecture。**

---

# 前置要求

完成 Stage 00–04，或已经理解：

- message-based LLM interaction；
- Structured Output / Function Calling；
- provider-neutral Tool schema；
- ReAct Agent runtime；
- Workflow vs Agent control ownership；
- explicit state/orchestration；
- RAG 与 external evidence boundary；
- 基本 async Python：`async`、`await`、async context manager。

不需要任何 MCP 前置经验。

---

# 本阶段最核心的一句话

> **Function Calling 标准化的是 model 如何在 application 内提出 structured action proposal；MCP 标准化的是 application 如何跨外部 protocol boundary 发现并调用 capability/context。**

二者属于不同层，但可以自然组合。

Tiny-Agent 的组合路径是：

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

MCP 不替代 Agent runtime，它只是给 runtime 提供一个标准化的 capability source。

---

# 学习目标

完成本阶段后，你应该能够：

1. 解释 MCP 解决什么问题；
2. 区分 MCP 与 Function Calling；
3. 区分 MCP 与 Agent framework；
4. 解释 Host、Client、Server 的职责；
5. 不把 Tools / Resources / Prompts 扁平化成同一种东西；
6. 从 client discovery MCP capability；
7. 调用 Tool，并解释 `structured_content`、`content`、`is_error`；
8. 读取 fixed Resource，并理解 resource template；
9. list/render Prompt；
10. 解释为什么 2026-07-28 core 不再要求旧式 `initialize/initialized` handshake；
11. 解释 `server/discover`；
12. 区分 protocol statelessness 与 application state；
13. 区分 stdio 与 Streamable HTTP；
14. 识别 standalone SSE 教程属于旧架构；
15. 使用 Python SDK v2 `MCPServer` 构建 server；
16. 使用 v2 `Client` 消费 server；
17. 解释 remote Tool execution 为什么天然 async；
18. 使用 Tiny-Agent `ToolRegistry.aexecute()`；
19. 把 discovered MCP Tools 适配成 Tiny-Agent Tools；
20. 给多个 server 的 Tool 做 namespace；
21. 解释 capability discovery 为什么不是 authorization；
22. 把 remote Resources、Prompts、Tool results 当作 untrusted external data；
23. 解释 server annotations 为什么只是 hints，不是 security guarantee；
24. 识别 v1 / pre-2026 tutorial 的 migration trap。

---

# Part A — MCP mental model

阅读：

1. [MCP Mental Model](theory/01-mcp-mental-model.zh-CN.md)
2. [Tools、Resources 与 Prompts](theory/02-tools-resources-prompts.zh-CN.md)
3. [`code/protocol_message_walkthrough.py`](code/protocol_message_walkthrough.py)

到这里必须能自然区分：

```text
Function Calling != MCP
MCP != Agent
```

以及：

```text
Tool      = executable capability
Resource  = readable context/data
Prompt    = reusable model-facing template
```

如果这三者仍感觉“反正都是返回文本”，先别往后赶。

---

# Part B — 当前 MCP protocol model

阅读：

4. [Stateless Protocol 与 Transports](theory/03-stateless-protocol-and-transports.zh-CN.md)

本章取代旧 roadmap 中的：

```text
03-client-server-lifecycle.md
```

因为当前 protocol architecture 已发生实质变化。

必须记住：

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

官方 Python SDK v2 `Client` 会处理当前 discovery/version compatibility，并能对较老 server 做兼容 fallback。

---

# Part C — 构建一个 server，观察三种 primitive

阅读/运行：

5. [`code/mcp_server.py`](code/mcp_server.py)
6. [`code/in_memory_client.py`](code/in_memory_client.py)

Demo server 故意很小：

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

为什么不一口气暴露 37 个 Tools？因为如果还没讲清 Tool 与 Resource 的区别，就先堆 37 个 decorator，那是在优化截图密度，不是在优化学习。

In-memory client：

```python
async with Client(mcp) as client:
    ...
```

特别适合学习和测试，因为没有 subprocess/network 干扰协议概念。

---

# Part D — stdio process boundary

运行：

7. [`code/stdio_client.py`](code/stdio_client.py)

它会把 `mcp_server.py` 作为 subprocess 启动，并通过 stdio 连接。

```text
Tiny-Agent / Host process
        |
        | spawn
        v
MCP server process

stdin  <--- protocol request
stdout ---> protocol response
```

重要规则：

> **stdout 是 protocol wire。**

不要在 stdio server 中随手向 stdout `print()` debug 信息。使用 stderr/logging。

---

# Part E — Streamable HTTP service boundary

一个 terminal 启 server：

```bash
python stages/05-mcp/code/streamable_http_server.py
```

另一个 terminal：

```bash
python stages/05-mcp/code/streamable_http_client.py
```

阅读：

8. [`code/streamable_http_server.py`](code/streamable_http_server.py)
9. [`code/streamable_http_client.py`](code/streamable_http_client.py)

心智模型：

```text
local integration
    -> stdio

remote/service integration
    -> Streamable HTTP
```

新 Stage 05 架构不要从旧 standalone SSE tutorial 起步。

---

# Part F — 把 MCP Tools 接入 Tiny-Agent

阅读：

10. [Python SDK v2 与 Tiny-Agent Bridge](theory/05-python-sdk-v2-and-tiny-agent-bridge.zh-CN.md)
11. [`../../src/tiny_agent/mcp_bridge.py`](../../src/tiny_agent/mcp_bridge.py)
12. [`code/tiny_agent_mcp_bridge.py`](code/tiny_agent_mcp_bridge.py)
13. [`../../src/tiny_agent/tool.py`](../../src/tiny_agent/tool.py)
14. [`../../tests/test_async_tools.py`](../../tests/test_async_tools.py)
15. [`../../tests/test_stage05_mcp.py`](../../tests/test_stage05_mcp.py)

Stage 05 增加 backward-compatible async capability path：

```python
await tool.ainvoke(...)
await registry.aexecute(...)
```

因为 remote MCP call 天然是：

```python
await client.call_tool(...)
```

我们不会用到处套 `asyncio.run()` 的方式硬把 async MCP 塞进 sync handler。

---

# Part G — Security 与 trust boundary

最后阅读：

16. [MCP Security Boundaries](theory/04-mcp-security-boundaries.zh-CN.md)
17. [复习题](exercises/review-questions.zh-CN.md)
18. [2026 MCP 扩展：Tasks、MRTR 与 MCP Apps](advanced/README.zh-CN.md)

顺序是刻意的：先知道 protocol 能做什么，再讨论 Host 应允许它做什么。

安全不变量：

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

而不是：

```text
Server advertised it
    ↓
YOLO
```

---

# 安装

Tiny-Agent core 保持轻量：

```bash
python -m pip install -e ".[dev]"
```

Stage 05 MCP：

```bash
python -m pip install -e ".[stage05]"
```

Stage 05 tests：

```bash
python -m pip install -e ".[dev,stage05]"
```

当前 extra：

```text
mcp[cli] >= 2, < 3
```

---

# 推荐运行顺序

```bash
# 1. 不起 server/network，先看 protocol shape
python stages/05-mcp/code/protocol_message_walkthrough.py

# 2. 当前 SDK server/client 同一进程
python stages/05-mcp/code/in_memory_client.py

# 3. stdio subprocess
python stages/05-mcp/code/stdio_client.py

# 4. discovered MCP Tools -> Tiny-Agent
python stages/05-mcp/code/tiny_agent_mcp_bridge.py

# 5. remote HTTP，两个 terminals
python stages/05-mcp/code/streamable_http_server.py
python stages/05-mcp/code/streamable_http_client.py
```

---

# 版本警告：旧 MCP 教程非常多

如果教程主要使用：

```python
FastMCP(...)
ClientSession(...)
await session.initialize()
```

或者以旧 standalone SSE 为默认新服务架构，请先看发布时间与 SDK/protocol version。

这些代码可能对 v1/旧协议是正确的，但 Stage 05 故意优先教学 current SDK v2 / 2026 protocol model，再解释历史兼容。

不要把三个 protocol generation 的 snippet 拼进一个文件，然后怪 Python 背叛了你。

---

# 外部学习资源

## 1. MCP 官方文档

- MCP docs: <https://modelcontextprotocol.io/>
- 2026-07-28 release: <https://blog.modelcontextprotocol.io/posts/2026-07-28/>

Current semantics 以官方 protocol material 为 source of truth。

## 2. Official Python SDK

- <https://github.com/modelcontextprotocol/python-sdk>
- v2 changes: <https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/whats-new.md>
- Client guide: <https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/client/index.md>
- Running/transports: <https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/index.md>

## 3. Security

- <https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices>

在把第三方 MCP server catalog 当成“无害插件袋”之前先读它。

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

Bridge 故意保持 narrow，不把整个 Tiny-Agent 内部架构改造成 MCP-shaped codebase。

---

# 本阶段不假装解决什么

Stage 05 教当前 protocol 与 clean integration boundary，但不宣称已经解决：

- enterprise OAuth architecture；
- arbitrary third-party server sandboxing；
- production approval UI；
- distributed retry/circuit breaker；
- full async AgentRuntime redesign；
- multi-server dynamic lifecycle management；
- organization-wide MCP registry/governance；
- production audit logging/observability；
- remote context prompt-injection full defense；
- untrusted local server 的 OS isolation。

这些问题会连接到 Stage 06–10。

---

# Stage milestone

完成 Stage 05 时，你应该能完整解释：

```text
build MCPServer
    ↓
discover Tools / Resources / Prompts with Client
    ↓
call/read/render the correct primitive
    ↓
explain 2026 stateless MCP vs older handshake MCP
    ↓
run same capability in-process / stdio / HTTP
    ↓
bridge MCP Tools into Tiny-Agent
    ↓
execute remote tools asynchronously
    ↓
explain why discovery never grants authorization
```

最终问题已经不再只是：

> “怎么连一个 Tool？”

而是：

> **如何通过标准协议连接 capability，同时保留内部 abstraction、origin、trust、authorization 与 execution boundary？**
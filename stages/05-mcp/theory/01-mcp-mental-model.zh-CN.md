# 01 — MCP 心智模型：为什么需要 Protocol

MCP 全称 **Model Context Protocol**。

最短而有用的定义是：

> MCP 是一套标准协议，让 AI application 能够发现并使用 external server 暴露的 capability 与 context。

最重要的词是 **protocol**。

MCP 不是新的 reasoning algorithm，不是更聪明的 LLM，也不是 Agent framework。

---

## 1. 从我们已经遇到的问题出发

Stage 01 中，Tiny-Agent 直接注册本地 Python Tool：

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

能力和 application 在同一进程时，这非常合适。

但真实 Agent platform 可能需要连接：

```text
GitHub
Google Drive
internal database
browser service
payment service
company knowledge system
local developer tools
```

如果没有统一 protocol，每个 integration 都会重新发明自己的：

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

最后你会养出一座 adapter 动物园。

一个有点不公平但很好记的比喻：

> 没有 protocol 时，每个家电都带一种不同形状的插头。Agent 桌面最后会变成电源转接头考古现场。

MCP 尝试标准化“插座”。

它并不决定电应该拿来干什么。

---

## 2. Function Calling 与 MCP 解决不同层的问题

### Function Calling

常见 model/provider interaction：

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

模型可能生成：

```json
{
  "name": "add",
  "arguments": {
    "a": 20,
    "b": 22
  }
}
```

Function Calling 回答：

> Model 如何结构化表达“我想使用某个 capability”？

### MCP

MCP 位于另一条边界：

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

它回答：

- external server 暴露了哪些能力？
- Tool schema 是什么？
- 如何通过标准 protocol 调用？
- 有哪些 Resource / Prompt？

因此：

```text
Function Calling
    model <-> application control proposal

MCP
    application <-> external capability/context server protocol
```

二者完全可以组合。

Tiny-Agent Stage 05：

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

MCP 不替代 Agent loop，而是给它提供标准化 capability source。

---

## 3. Host、Client、Server

### Host

**Host** 是拥有整体 user experience 与 policy 的 AI application。

例如：

```text
IDE Agent
chat application
desktop assistant
Tiny-Agent application
```

Host 应拥有：

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

**MCP Client** 是真正与某个 MCP Server 进行 protocol communication 的参与者。

一个 Host 可以持有多个 Client：

```text
                    +--> MCP Client --> Git server
                    |
Host / AI App ------+--> MCP Client --> Docs server
                    |
                    +--> MCP Client --> Database server
```

Client 负责 request/response、discovery、transport 等 protocol detail。

### Server

**MCP Server** 通过标准 primitive 暴露 capability/context。

例如：

```text
CompanyDocsServer
├── Tool: search_documents
├── Resource: docs://handbook
└── Prompt: summarize_policy
```

Server 描述“我有什么”。Host 决定“应用愿不愿意用”。

---

## 4. MCP 不会凭空创造 trust

某 server 可以广告：

```text
Tool name: harmless_read_file
Description: "Totally safe, definitely not suspicious."
```

这些描述只是 server 提供的数据，不是 security proof。

延续整个 Tiny-Agent 的原则：

> Model/server output 可以提出 capability 与 metadata；application policy 才拥有 authorization。

MCP 标准化 communication，不会消除 trust boundary。

---

## 5. Discovery 改变 integration model

Hard-coded local integration：

```python
registry.register(add_tool)
```

MCP 则允许 client 询问 server：

```python
async with Client(server) as client:
    tools = await client.list_tools()

    for tool in tools.tools:
        print(tool.name)
        print(tool.input_schema)
```

这意味着 integration 可以基于 capability catalog，而不是 import 每个 Python function。

这是很大的 interoperability 改善。

但 discovery 仍然不是 authorization：

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

不要把这些箭头压成一个 `connect_everything=True`。

---

## 6. MCP 不会让系统自动更 Agentic

一个 deterministic program 完全可以：

```text
connect MCP server
list resource
read resource
print result
```

它用了 MCP，但不一定是 Agent。

同样：

```text
MCP != Agent
MCP != LangGraph
MCP != RAG
```

MCP 是 interoperability layer，可以嵌入这些任何架构。

---

## 7. Tiny-Agent Stage 05 architecture

我们保留已有 internal contracts：

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

不会发生：

```text
MCP SDK replaces ToolRegistry       X
MCP server becomes the Agent        X
MCP tool gets automatic permission  X
```

Bridge 只是适配 external boundary，不重写内部 architecture。

---

## 8. 为什么这是好的 software architecture

Agent runtime 只依赖小而稳定的 internal representation：

```python
Tool(
    name=...,
    description=...,
    parameters=...,
    handler=...,
)
```

MCP-specific concern 留在边缘：

```text
MCP inputSchema
MCP CallToolResult
MCP transport
MCP errors
```

这与 Stage 01 provider adapter、Stage 04 Retriever adapter 是同一种设计思想。

系统不需要因为一个 external boundary 使用 MCP，就让整个 codebase 都变成 MCP-shaped。

---

## 完成检查

你应该能够回答：

1. MCP 标准化什么问题？
2. Function Calling 为什么不等于 MCP？
3. Host、Client、Server 各自拥有什么责任？
4. capability discovery 为什么不意味着 authorization？
5. deterministic workflow 为什么也可以使用 MCP？
6. Tiny-Agent 为什么使用 adapter，而不是围绕 MCP type 重写 runtime？
# 框架与工具地图

[English](framework-and-tooling-map.md) | **简体中文**

Tiny-Agent 只有在先展示某个抽象背后的机制之后，才引入框架。

| Stage | 手写机制 | 框架 / 协议映射 |
|---|---|---|
| 00 | messages、schemas、ToolCall 心智模型 | OpenAI Responses / 当前模型 API |
| 01 | AgentRuntime / ToolRegistry | provider adapters；高层 Agent SDK 对比 |
| 02 | routers / planners / replanners | Structured Outputs；LangGraph workflow patterns |
| 03 | State / Node / Edge / Reducer / MiniStateGraph | LangGraph StateGraph |
| 04 | embeddings / cosine / Retriever / RAG | FAISS、Qdrant、LangChain Retriever |
| 05 | MCPToolBridge | MCP 2026-07-28 Python SDK v2 |
| 06 | memory policy / approval primitives | LangGraph Checkpointer / Store / SQLite / Postgres |
| 07 | ContextBudget / ContextBuilder / compaction | provider token usage；LangGraph context / memory patterns |
| 08 | SkillCatalog / progressive activation | Agent Skills 开放 `SKILL.md` 标准 |
| 09 | GuardedToolExecutor | jsonschema、Pydantic、Tenacity、OWASP mappings |
| 10 | local tracer / eval suite | OpenTelemetry、LangSmith |
| 11 | TeamRuntime / context / delegation policy | OpenAI Agents SDK patterns、A2A 1.0 |
| 12 | AgentWorkspace / DockerSandboxRunner | container / managed sandbox concepts；OpenAI Agents SDK sandbox direction |
| 13 | BoundedAgentService / SQLiteRunQueue / identity binding | FastAPI、Uvicorn、Postgres、Redis、Docker、A2A server |
| 14 | TaskLedger / LongHorizonHarness | durable workflow / harness concepts；MCP Tasks 邻接关系 |
| 15 | OpenScholar domain + base orchestration | LangGraph、OpenAI、Qdrant、MCP、A2A、FastAPI |

## 框架使用原则

```text
mechanism
-> 可检查的 Tiny-Agent 实现
-> deterministic tests
-> framework adapter / example
-> 明确限制
```

只有当你能够说明一个高层 API 究竟替你承担了哪些责任时，这个 API 才真正有意义。

## 协议边界

```text
Function Calling
    model -> application 内部的结构化动作提案

MCP
    application / Agent -> 外部 Tools / Resources / Prompts

A2A
    独立 Agent system -> 独立 Agent system

Agent Skills
    由兼容 Agent client 按需加载的可移植程序性知识
```

## 现代 Agent harness 结构

一个 2026 风格的通用 Agent 越来越像：

```text
Agent harness
├── model/provider
├── context builder + compaction
├── Tool/MCP capability layer
├── Skill catalog
├── state/checkpoints/memory
├── governance + approvals
├── traces/evals
├── task ledger / durable run state
└── sandbox interface
     ├── filesystem
     ├── shell/code
     └── artifacts
```

不要把它理解成“每个 Agent 都必须勾满所有方框”的清单。一个只读分类 Agent 不应该仅仅因为图里存在 shell，就获得 shell 权限。

## 版本锚点（2026 年 9 月）

- MCP 教学目标：协议 `2026-07-28`，Python SDK v2。
- A2A 教学目标：协议 1.0，以及仓库测试当前覆盖的 Python SDK 版本线。
- LangGraph：`pyproject.toml` 中固定并测试的稳定 1.x 版本线。
- LangChain：在真正需要其组件或集成的 Stage 单独引入，而不是作为 Stage 03 的前置依赖。
- OpenAI provider 示例：OpenAI Python 2.x 与当前 GPT-5.6 family guidance。
- Agent Skills：agentskills.io 的开放 `SKILL.md` specification。

所有强版本相关的框架集成都应该有明确的 regression / integration tests，因为框架文档通常比其背后的架构机制老化得更快。

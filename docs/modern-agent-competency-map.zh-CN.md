# Tiny-Agent 2026 现代 Agent 能力地图

[English](modern-agent-competency-map.md) | **简体中文**

这份文档回答一个问题：

> 如果学习者完整学完 Tiny-Agent，应该能够解释并实现哪些现代 Agent 工程核心能力？

## Layer 1 — 模型 / 应用边界

| 能力 | Stage | 证据 |
|---|---|---|
| messages / instructions | 00 | theory + minimal API mental model |
| Structured Output / JSON Schema | 00 | schema-constrained control data |
| Function / Tool Calling | 00 | ToolCall -> runtime -> observation |
| 模型能力 / 模型选择 | 00 | reasoning / cost / latency trade-offs |
| context / token budgeting | 00, 06A | 显式 ContextBudget |
| provider adapters | 01, 02 | 归一化 Model / StructuredDecisionModel |

## Layer 2 — Agent 控制流

| 能力 | Stage |
|---|---|
| ReAct / decide-act-observe | 01 |
| 有边界的停止条件 | 01, 07 |
| deterministic workflow vs Agent | 02 |
| semantic routing | 02 |
| planner-executor | 02 |
| bounded replanning | 02 |
| 显式状态机 | 03 |
| graph orchestration | 03 |
| streaming / checkpoint / interrupt | 03, 06 |

## Layer 3 — 知识与上下文

| 能力 | Stage |
|---|---|
| chunking / embeddings / similarity | 04 |
| FAISS / Qdrant | 04 |
| reranking / Agentic RAG | 04 |
| retrieval evaluation | 04, 08 |
| MCP Tools / Resources / Prompts | 05 |
| MCP 2026 stateless core | 05 |
| MCP extensions / Tasks / MRTR / Apps | 05 advanced |
| short / long-term memory | 06 |
| Context Engineering | 06A |
| compaction / provenance / JIT context | 06A |
| Agent Skills / progressive disclosure | 06B |

## Layer 4 — 安全、可靠性与权限

| 能力 | Stage |
|---|---|
| 本地 schema validation | 07 |
| failure taxonomy / redaction | 07 |
| timeout / cancellation / retry | 07 |
| idempotency reasoning | 06, 07, 10 |
| run-wide budgets / loop detection | 07 |
| principals / least privilege | 07 |
| exact approval binding | 07 |
| prompt-injection boundaries | 07 |
| memory / Skill provenance | 06, 06B |
| workspace path policy | 09A |
| controlled sandbox compute | 09A |
| network / credential separation | 09A |

## Layer 5 — 评估与协作

| 能力 | Stage |
|---|---|
| traces / spans / privacy-aware capture | 08 |
| Tool / trajectory evaluation | 08 |
| deterministic vs LLM judges | 08 |
| offline / online eval | 08 |
| cost / latency / quality regression gates | 08 |
| delegation vs handoff | 09 |
| context projection | 09 |
| fan-out / fan-in | 09 |
| A2A 1.0 interoperability | 09, 10 |

## Layer 6 — 生产与长时程执行

| 能力 | Stage |
|---|---|
| thin service boundary | 10 |
| request / run / thread / identity separation | 10 |
| trusted auth / tenant binding | 10 |
| concurrency / backpressure / deadlines | 10 |
| durable jobs / leases | 10 |
| Postgres / Redis lifecycle | 10 |
| liveness / readiness / shutdown | 10 |
| Docker / Compose topology | 10 |
| task ledger / session handoff | 10A |
| externalized progress / artifacts | 10A |
| evaluator / repair loop | 10A |
| harness / compute rehydration | 09A, 10A |

## Layer 7 — Capstone 综合能力

OpenScholar 展示的不是“把所有能力都打开”，而是一个真实应用如何从这些机制中选择真正需要的子集。

它的核心不变量是：

```text
metadata != scientific evidence
memory != evidence
model proposal != policy
retrieval result != evidence sufficiency
citation existence != semantic support
approval != authorization
protocol compatibility != trust
container != perfect sandbox
```

## A+ 完成标准

学习者在选择框架之前，应能够为一个新 Agent 系统回答：

1. 哪些决策真的需要模型？
2. 状态机是什么？
3. 哪些 state 需要 durable？作用域是什么？
4. 每一次模型调用究竟应该收到哪些 context？
5. 哪些能力是 Tools，哪些是 Skills，哪些属于外部协议？
6. 系统里有哪些 evidence / trust classes？
7. 模型提案能够触达多大的权限？
8. 哪些动作需要 approval，哪些还需要 authorization？
9. 代码和文件执行在哪里发生？
10. 进程或 sandbox 丢失后，任务如何继续？
11. 除了最终文本之外，如何评估 Agent？
12. 每一个 durable resource 属于哪个 service identity / tenant？
13. 为什么 multi-Agent 的额外复杂度是合理的？
14. overload、timeout、retry、shutdown 和部分副作用发生时怎么办？
15. 哪些 production claim 仍取决于具体部署，而不是由某个库自动解决？

如果这些问题都能被准确回答，学习者就已经从“会用 Agent 框架”跨到了“会工程化设计 Agent 系统”。
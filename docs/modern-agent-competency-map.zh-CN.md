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
| context / token budgeting | 00, 07 | 显式 ContextBudget |
| provider adapters | 01, 02 | 归一化 Model / StructuredDecisionModel |

## Layer 2 — Agent 控制流

| 能力 | Stage |
|---|---|
| ReAct / decide-act-observe | 01 |
| 有边界的停止条件 | 01, 09 |
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
| retrieval evaluation | 04, 10 |
| MCP Tools / Resources / Prompts | 05 |
| MCP 2026 stateless core | 05 |
| MCP extensions / Tasks / MRTR / Apps | 05 advanced |
| short / long-term memory | 06 |
| Context Engineering | 07 |
| compaction / provenance / JIT context | 07 |
| Agent Skills / progressive disclosure | 08 |

## Layer 4 — 安全、可靠性与权限

| 能力 | Stage |
|---|---|
| 本地 schema validation | 09 |
| failure taxonomy / redaction | 09 |
| timeout / cancellation / retry | 09 |
| idempotency reasoning | 06, 09, 13 |
| run-wide budgets / loop detection | 09 |
| principals / least privilege | 09 |
| exact approval binding | 09 |
| prompt-injection boundaries | 09 |
| memory / Skill provenance | 06, 08 |
| workspace path policy | 12 |
| controlled sandbox compute | 12 |
| network / credential separation | 12 |

## Layer 5 — 评估与协作

| 能力 | Stage |
|---|---|
| traces / spans / privacy-aware capture | 10 |
| Tool / trajectory evaluation | 10 |
| deterministic vs LLM judges | 10 |
| offline / online eval | 10 |
| cost / latency / quality regression gates | 10 |
| delegation vs handoff | 11 |
| context projection | 11 |
| fan-out / fan-in | 11 |
| A2A 1.0 interoperability | 11, 13 |

## Layer 6 — 生产与长时程执行

| 能力 | Stage |
|---|---|
| thin service boundary | 13 |
| request / run / thread / identity separation | 13 |
| trusted auth / tenant binding | 13 |
| concurrency / backpressure / deadlines | 13 |
| durable jobs / leases | 13 |
| Postgres / Redis lifecycle | 13 |
| liveness / readiness / shutdown | 13 |
| Docker / Compose topology | 13 |
| task ledger / session handoff | 14 |
| externalized progress / artifacts | 14 |
| evaluator / repair loop | 14 |
| harness / compute rehydration | 12, 14 |

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

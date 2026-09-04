# Tiny-Agent 测试指南

> Language: [English](README.md) | 简体中文

`tests/` 目录不是一个塞满神秘 `pytest` 文件的附录。在 Tiny-Agent 中，测试是**课程所讲 Agent 机制的可执行规范（executable specification）**。

推荐把课程理解成三层：

```text
Stage 理论
    -> 解释某条工程不变量为什么存在

src/tiny_agent/
    -> 把这条不变量实现成可复用代码

tests/test_*.py
    -> 用确定性的正例和反例验证这条不变量
```

因此，测试文件和 Stage 里的教学示例解决的问题不同：

- `stages/.../code/*.py` 主要回答：**“这个机制是怎么工作的？”**
- `tests/test_*.py` 主要回答：**“无论怎么改代码，哪些行为都必须继续成立，尤其是在边界条件下？”**

阅读测试时，不要把重点放在背 `pytest` 语法。真正值得学习的是：**为什么这里故意构造了一个坏输入？这个 assertion 究竟在保护哪条架构契约？**

---

## 1. 应该怎样阅读 tests？

学习一个机制时，推荐顺序是：

1. 阅读对应 Stage README 和理论章节；
2. 运行该 Stage 的小型教学示例；
3. 查看 `src/tiny_agent/` 中的真实实现；
4. 根据本指南阅读对应测试；
5. 故意破坏一条不变量，观察测试为什么失败；
6. 恢复实现，并能够解释为什么测试重新通过。

例如 Stage 01 讲的是：

```text
model 提出 ToolCall
    -> runtime 执行 Tool
    -> Tool observation 返回 model
    -> model 继续或结束
```

[`test_runtime.py`](test_runtime.py) 把这张图变成了可以执行的规范；[`test_runtime_edges.py`](test_runtime_edges.py) 则继续追问：如果模型无限调用 Tool、Tool 报错，或者模型既不给 ToolCall 也不给 final answer，会发生什么？

### 本指南使用的测试类型

| 标记 | 含义 |
|---|---|
| **Core** | Tiny-Agent 自己的确定性机制测试；通常不需要网络或外部服务。 |
| **Framework** | 验证与真实框架/协议的映射，例如 LangGraph、Qdrant、MCP、OpenTelemetry、OpenAI Agents SDK、A2A。 |
| **Service** | 可能真正依赖 Postgres、Redis、FastAPI 等服务边界的集成测试。 |
| **Cross-stage** | 后续 Stage 引入更严格的安全/生产语义后，用来保护前面 Stage 已建立的不变量。 |

除非本指南明确说明需要环境变量或外部服务，否则 Framework 测试通常仍然是离线、确定性的。

---

## 2. 怎样运行测试而不丢失学习价值？

先安装轻量开发依赖：

```bash
python -m pip install -e ".[dev]"
```

学习一个机制时，优先只运行一个文件：

```bash
pytest -q tests/test_runtime.py
```

也可以只运行一条具体行为：

```bash
pytest -q \
  tests/test_runtime.py::test_agent_executes_tool_then_finishes
```

按关键词挑选某类行为：

```bash
pytest -q tests/test_guarded_runtime.py -k retry
```

依赖真实框架的 Stage 使用根 README 中对应的 extra，例如：

```bash
python -m pip install -e ".[dev,stage03]"
pytest -q tests/test_langgraph_runtime.py tests/test_stage03_frameworks.py

python -m pip install -e ".[dev,stage07]"
pytest -q tests/test_validation.py tests/test_reliability.py \
  tests/test_governance.py tests/test_guarded_runtime.py \
  tests/test_stage07_integrations.py
```

确实需要外部基础设施的测试会显式要求环境变量：

```bash
TEST_POSTGRES_URI='postgresql://...' \
pytest -q tests/test_stage06_postgres.py

TEST_REDIS_URL='redis://...' \
TEST_POSTGRES_URI='postgresql://...' \
pytest -q tests/test_stage10_integrations.py
```

不要把真实生产凭证写进命令、fixture、测试输出或提交到仓库中。

---

# 3. 按 Stage 对应的完整测试地图

## Stage 01 — ReAct Runtime 与 Provider Boundary

对应课程为整合后的 [Stage 01 中文教程](../stages/01-react-runtime/README.zh-CN.md)。ReAct 循环、Runtime 架构、工具边界、确定性测试和模型服务适配器均已在该主章节中连续讲解。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_runtime.py`](test_runtime.py) | Core | 用确定性的 fake model 验证：模型先提出 ToolCall，runtime 执行 Tool，把 observation 放回消息，再次调用模型，最终得到 final answer；同时检查完整 message role 顺序。 | 这是 Stage 01 最小 ReAct loop 的可执行规范。如果它失败，说明最基础的 model/runtime/Tool 边界已经发生变化。 |
| [`test_runtime_edges.py`](test_runtime_edges.py) | Core | 验证 `max_steps` 停止条件、安全的 Tool failure observation，以及模型既没有 ToolCall 又没有 final answer 时必须拒绝继续。 | Happy path 很容易写；真正让循环成为 runtime 的，是 bounded stopping 和 failure semantics。 |
| [`test_openai_adapter.py`](test_openai_adapter.py) | Framework，离线 | 验证 `OpenAIResponsesModel` 如何把 Tiny-Agent messages/Tool schema 转成 Responses API 请求，再把 provider `function_call` 归一化成 Tiny-Agent `ToolCall`；也覆盖同一轮多个 ToolCall。使用 fake client，不访问网络。 | 证明 provider wire format 被限制在 adapter 内，而不是渗透进 Agent runtime。 |
| [`test_openai_adapter_edges.py`](test_openai_adapter_edges.py) | Framework，离线 | 验证 direct final text、非法 JSON arguments、非 object arguments、ToolCall 与附带文本同时出现、以及未知内部 message role。 | Provider response 也是外部输入，adapter 必须显式拒绝坏数据，不能静默“猜一个意思”。 |

## Stage 02 — Routing、Structured Decision、Planning 与 Budget

对应课程：[Stage 02 中文教程](../stages/02-planning-routing/README.zh-CN.md)，重点配合 [Routing Patterns](../stages/02-planning-routing/theory/02-routing-patterns.zh-CN.md)、[Planning 与 Replanning](../stages/02-planning-routing/theory/03-planning-and-replanning.zh-CN.md)、[Planner / Executor](../stages/02-planning-routing/theory/04-planner-executor.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_workflows.py`](test_workflows.py) | Core | RuleRouter 与 fallback、schema-constrained LLM routing、route 决策后的 deterministic dispatch、固定 Plan 执行、失败后才 replan，以及 replan budget。 | 直观展示“语义判断交给模型”和“普通控制流由程序拥有”是两件事。 |
| [`test_structured_decision.py`](test_structured_decision.py) | Framework，离线 | OpenAI structured-decision adapter 使用 strict JSON Schema，并只接受 object decision；非法 JSON 或 array 会被拒绝。 | Router/Planner 的输出是 application data，不是自由散文。 |
| [`test_structured_decision_edges.py`](test_structured_decision_edges.py) | Framework，离线 | Provider refusal 与 incomplete response 会被表示成两个一等错误结果，而不是和“JSON 解析失败”混为一谈。 | Production control flow 必须知道“为什么没有合法 decision”。 |
| [`test_workflow_budgets.py`](test_workflow_budgets.py) | Core | 最大 Plan 长度、step id 唯一性、total execution-step budget。 | Model 生成的 Plan 仍然只是 proposal，application 必须在执行前和执行中限制它。 |

这一部分在 Stage 07 后还有一个安全回归测试：[`test_workflow_safety.py`](test_workflow_safety.py)，见下方 **Cross-stage tests**。

## Stage 03 — Explicit State 与 LangGraph

对应课程：[Stage 03 中文教程](../stages/03-stateful-orchestration/README.zh-CN.md)，重点配合 [为什么需要显式 State](../stages/03-stateful-orchestration/theory/01-why-explicit-state.zh-CN.md)、[Agent 状态机](../stages/03-stateful-orchestration/theory/02-state-machines-for-agents.zh-CN.md)、[LangGraph Core Concepts](../stages/03-stateful-orchestration/theory/03-langgraph-core-concepts.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_state_graph.py`](test_state_graph.py) | Core | 手写 `TinyStateGraph` 的 fixed/conditional edge、未知 route 拒绝、cycle step budget、graph topology validation、node update contract。 | 让你先理解 graph 本质，不把所有行为都误认为“LangGraph 框架魔法”。 |
| [`test_langgraph_runtime.py`](test_langgraph_runtime.py) | Framework | 用 LangGraph 重建 ReAct loop，仍保留 application-owned model-step budget，并在本阶段把 Tool failure 作为 observation 暴露给模型。 | 从 `while` loop 换成 graph 改变的是 orchestration 表达，不是 Tool execution authority。 |
| [`test_stage03_frameworks.py`](test_stage03_frameworks.py) | Framework | LangGraph streaming update、带 checkpointer 的 `interrupt()` / `Command(resume=...)`、`thread_id`，以及 LangChain Tool/message 与既有概念的对应关系。 | 验证“手写机制之后”本 Stage 真正引入的框架能力。 |

Framework tests 使用 `.[dev,stage03]`。

## Stage 04 — Retrieval、RAG、Vector Backend 与 Embedding

对应课程：[Stage 04 中文教程](../stages/04-agentic-rag/README.zh-CN.md)，重点配合 [Vector Search 与 Similarity](../stages/04-agentic-rag/theory/03-vector-search-and-similarity.zh-CN.md)、[FAISS vs Vector Database](../stages/04-agentic-rag/theory/04-faiss-vs-vector-database.zh-CN.md)、[Agentic RAG](../stages/04-agentic-rag/theory/07-agentic-rag.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_retrieval.py`](test_retrieval.py) | Core | Chunk overlap/metadata、非法 chunk 参数、cosine 边界、确定且归一化的教学 embedding、top-k ranking、metadata filter 在 ranking 前生效。 | 保护所有后续向量后端下面的第一性原理 retrieval semantics。 |
| [`test_rag.py`](test_rag.py) | Core | Basic RAG 必须先 retrieve；Agentic RAG 可以跳过检索、最多进行 bounded query rewrite、证据足够后回答、证据持续不足时 abstain，并拒绝 malformed control decision。 | 让 Agentic RAG 成为 bounded workflow，而不是“模型觉得不够就无限搜”。 |
| [`test_stage04_vector_backends.py`](test_stage04_vector_backends.py) | Framework | FAISS 最近邻；教学 FAISS adapter 不伪装原生 metadata filtering；Qdrant local mode + payload filter；LangChain Retriever adapter。 | 帮助学习者看到不同 backend 真正负责什么，而不是把所有 vector system 当成同一种东西。 |
| [`test_openai_embeddings.py`](test_openai_embeddings.py) | Framework，离线/复用 | 用 fake client 验证 OpenAI embedding adapter 遵守 provider-neutral embedding contract 与 dimension 约束。Stage 11 的生产型 retrieval path 也复用它。 | 保护 Stage 04 定义的 embedding interface，使后面替换真实 provider 时不改 retrieval 核心语义。 |

FAISS/Qdrant/LangChain tests 使用 `.[dev,stage04]`。

## Stage 05 — MCP 与 Async Tool Execution

对应课程：[Stage 05 中文教程](../stages/05-mcp/README.zh-CN.md)，重点配合 [MCP Mental Model](../stages/05-mcp/theory/01-mcp-mental-model.zh-CN.md)、[Stateless Protocol 与 Transports](../stages/05-mcp/theory/03-stateless-protocol-and-transports.zh-CN.md)、[Python SDK v2 与 Tiny-Agent Bridge](../stages/05-mcp/theory/05-python-sdk-v2-and-tiny-agent-bridge.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_async_tools.py`](test_async_tools.py) | Core | `ToolRegistry.aexecute()` 可以执行 sync handler，也会正确 await async handler；反过来，sync `execute()` 遇到 async handler 必须报错，而不能把 coroutine object 当结果返回。 | Remote MCP Tool 天然是 async，因此 Tool abstraction 必须有真实的 async boundary。 |
| [`test_stage05_mcp.py`](test_stage05_mcp.py) | Framework | MCP v2 / `2026-07-28` protocol、Tools/Resources/Prompts discovery、structured Tool result、bridge namespace、ToolRegistry population、remote async execution 与显式 MCP Tool error。 | 确保教程验证的是当前 MCP，而不是旧 `initialize()` 生命周期。 |

使用 `.[dev,stage05]`。

## Stage 06 — Memory、Durable Persistence 与 HITL

对应课程：[Stage 06 中文教程](../stages/06-memory-persistence-hitl/README.zh-CN.md)，重点配合 [Context / State / Checkpoint / Memory](../stages/06-memory-persistence-hitl/theory/01-context-state-checkpoint-memory.zh-CN.md)、[Long-term Memory 与 Write Policy](../stages/06-memory-persistence-hitl/theory/03-long-term-memory-and-write-policy.zh-CN.md)、[Durable Persistence 与 Resume](../stages/06-memory-persistence-hitl/theory/04-durable-persistence-and-resume.zh-CN.md)、[Human-in-the-Loop](../stages/06-memory-persistence-hitl/theory/05-human-in-the-loop-and-approval.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_memory_policy.py`](test_memory_policy.py) | Core | Memory namespace 按 owner 而不是 thread 隔离；candidate shape validation；允许明确请求、非敏感 semantic memory；默认拒绝 incidental、sensitive 与 procedural self-rewrite memory。 | “模型提取到一个事实”并不等于“有权把它永久保存”。 |
| [`test_approval.py`](test_approval.py) | Core | Serializable approval payload；`approve` / `edit` / `reject`；edit 必须提供修改后的 arguments；reject 不返回任何可执行 arguments。 | 把人工审查变成结构化 policy data，而不是一句模糊的 yes/no。 |
| [`test_stage06_langgraph.py`](test_stage06_langgraph.py) | Framework | Checkpoint 按 thread 隔离；SQLite checkpoint 在新 saver/graph object 中仍能恢复；Store 跨 thread namespace；HITL edit 在执行前修改参数；reject 永不进入 execution node。 | 直接区分 short-term execution state、durable checkpoint、long-term Store 与 approval。 |
| [`test_stage06_postgres.py`](test_stage06_postgres.py) | Service | `PostgresSaver` 在重新连接后仍可恢复 state；`PostgresStore` 持久化 cross-thread memory。没有 `TEST_POSTGRES_URI` 时自动 skip。 | 证明这些语义不只在 in-memory/local demo 中成立，也能映射到 production-oriented shared backend。 |

使用 `.[dev,stage06]`；Postgres 测试需要测试数据库。

## Stage 06A — Context Engineering

对应课程：[Stage 06A 中文教程](../stages/06a-context-engineering/README.zh-CN.md)，重点配合 [Context 是 Attention Budget](../stages/06a-context-engineering/theory/01-context-is-an-attention-budget.zh-CN.md) 与 [Context Selection / Compaction](../stages/06a-context-engineering/theory/02-context-assembly-selection-compaction.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_context_engineering.py`](test_context_engineering.py) | Core | Required item 与高优先级 item 应被保留；required context 放不下时 fail closed；compaction 必须记录 provenance 与估算 token savings。 | Context window 是一个预算化 selection 问题，不是“有多少容量就塞多少”。 |

## Stage 06B — Agent Skills

对应课程：[Stage 06B 中文教程](../stages/06b-agent-skills/README.zh-CN.md)，重点配合 [Skill Format 与 Progressive Disclosure](../stages/06b-agent-skills/theory/02-skill-format-and-progressive-disclosure.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_skills.py`](test_skills.py) | Core / format integration | Discovery 阶段只读取 Skill metadata 而不把完整 procedure 放进 prompt；activation 才加载 instructions / allowed Tools / references；声明的 Skill name 必须与目录一致。 | Progressive disclosure 成立的前提，就是 discovery 与 activation 必须是两个不同、可验证的动作。 |

YAML parsing 使用 `.[dev,stage06b]`。

## Stage 07 — Reliability、Safety 与 Governance

对应课程：[Stage 07 中文教程](../stages/07-reliability-safety/README.zh-CN.md)，重点配合 [Agent Failure Modes](../stages/07-reliability-safety/theory/01-agent-failure-modes.zh-CN.md)、[Validation 与 Output Handling](../stages/07-reliability-safety/theory/02-validation-and-output-handling.zh-CN.md)、[Timeout / Retry / Cancellation](../stages/07-reliability-safety/theory/03-timeout-retry-cancellation.zh-CN.md)、[Execution Budgets 与 Loops](../stages/07-reliability-safety/theory/04-execution-budgets-and-loops.zh-CN.md)、[Tool Permission 与 Least Privilege](../stages/07-reliability-safety/theory/05-tool-permissions-and-least-privilege.zh-CN.md)、[Prompt Injection 与 Sandboxing](../stages/07-reliability-safety/theory/06-prompt-injection-and-sandboxing.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_validation.py`](test_validation.py) | Core | 教学版 JSON-Schema subset 对合法输入通过；对 missing/wrong/extra/nested value fail closed；application 自己写坏 schema 时不能误报成 model input error。 | Validation 必须在 execution 前发生，而且 developer bug 和 model bad arguments 不是同一类错误。 |
| [`test_reliability.py`](test_reliability.py) | Core | Safe failure classification/redaction、retryable timeout、显式 safe error、bounded backoff、Tool/retry/token/cost budget、fingerprint、repeated-call detector。 | Reliability policy 需要 typed data，不能靠解析任意 exception string 临时猜。 |
| [`test_governance.py`](test_governance.py) | Core | Default-deny permission、role allowlist、approval 与 authorization 分离、高风险 approval gate、审批与精确 arguments fingerprint 绑定。 | 对一次操作的人工批准不能变成另一组参数也能复用的“万能通行证”。 |
| [`test_guarded_runtime.py`](test_guarded_runtime.py) | Core composition | 把 validation -> permission -> approval -> budget -> loop check -> execution -> timeout/retry -> safe failure 串起来；验证被拒绝的调用不会触达 handler，retry 只允许 retry-safe operation。 | 这是 Stage 07 guarded execution pipeline 最完整的可执行规范。 |
| [`test_trust.py`](test_trust.py) | Core | External content 被标记为 untrusted；简单 prompt-injection detector 只是 signal，而不是 authorization policy。 | “内容看起来可疑”和“它有没有权控制执行”是完全不同的问题。 |
| [`test_stage07_integrations.py`](test_stage07_integrations.py) | Framework | 完整 `jsonschema` 特性、Tenacity bounded retry predicate、Pydantic strict application boundary。 | 把前面手写的安全语义映射到成熟库，同时不把 policy ownership 交给库。 |

Integration tests 使用 `.[dev,stage07]`。

## Stage 08 — Observability 与 Evaluation

对应课程：[Stage 08 中文教程](../stages/08-evaluation-observability/README.zh-CN.md)，重点配合 [Tracing 与 Observability](../stages/08-evaluation-observability/theory/02-tracing-and-observability.zh-CN.md)、[Tool 与 Trajectory Evaluation](../stages/08-evaluation-observability/theory/03-tool-and-trajectory-evaluation.zh-CN.md)、[Graders 与 LLM-as-Judge](../stages/08-evaluation-observability/theory/05-graders-and-llm-as-judge.zh-CN.md)、[Quality / Cost / Latency / Regression](../stages/08-evaluation-observability/theory/06-quality-cost-latency-and-regression.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_observability.py`](test_observability.py) | Core | Parent/child trace tree；默认不保存 raw input/output；opt-in capture 时 redaction/truncation；nested sanitization；exception 标记错误但不保存敏感 raw message。 | Observability 应帮助工程师定位问题，而不能成为第二条 secret-leak 通道。 |
| [`test_observed_runtime.py`](test_observed_runtime.py) | Core composition | 给 guarded Tool executor 加 tracing，验证 Agent -> Tool span parentage、Tool name/attempt 属性，以及 failure classification；仍然不记录 raw arguments 或敏感 exception text。 | 展示 Stage 07 execution semantics 如何变成 Stage 08 可观察行为。 |
| [`test_evaluation.py`](test_evaluation.py) | Core | Tool precision/recall/F1、argument accuracy、trajectory sequence 与 policy safety 分开计分、repetition、execution success、metric coverage、regression gate、higher/lower-is-better metric、LLM judge score validation、NaN/Inf 拒绝。 | Final answer 对了远远不够；trajectory、安全、coverage、成本与 regression 都是不同信号。 |
| [`test_stage08_integrations.py`](test_stage08_integrations.py) | Framework | LangSmith tracing 可以完全离线禁用；OpenTelemetry nested span export；error status 不泄露 exception message/event。 | 验证生产型 observability mapping 仍然遵守 core tracer 的 privacy boundary。 |

使用 `.[dev,stage08]`。

## Stage 09 — Multi-Agent Coordination 与 A2A

对应课程：[Stage 09 中文教程](../stages/09-multi-agent/README.zh-CN.md)，重点配合 [Delegation / Handoff / Supervision](../stages/09-multi-agent/theory/02-delegation-handoffs-supervision.zh-CN.md)、[Context Ownership](../stages/09-multi-agent/theory/03-context-ownership-and-shared-state.zh-CN.md)、[Parallelism 与 Coordination](../stages/09-multi-agent/theory/04-parallelism-and-coordination.zh-CN.md)、[Delegation Governance](../stages/09-multi-agent/theory/05-delegation-governance.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_multi_agent.py`](test_multi_agent.py) | Core | Delegation 保持 manager ownership；成功 handoff 才转移 active Agent；失败 handoff 不转移；context projection；default-deny；handoff loop/parallel budget；fan-out 全量 prevalidation；failure redaction；coordination metrics 区分 attempt 与 success。 | Multi-Agent 的核心是 coordination/control，不是“多调用几个模型”。 |
| [`test_stage09_integrations.py`](test_stage09_integrations.py) | Framework，离线 | OpenAI Agents SDK 中 manager-as-Tool 与 handoff object；当前 A2A 1.0 Agent Card；A2A Message/request object，全程不需要网络。 | 把 Tiny-Agent 的 coordination semantics 映射到真实生态接口，同时保持 deterministic test。 |

使用 `.[dev,stage09]`。

## Stage 09A — Workspace 与 Sandbox Compute

对应课程：[Stage 09A 中文教程](../stages/09a-agent-workspace-sandbox/README.zh-CN.md)，重点配合 [Files / Artifacts / Workspace Policy](../stages/09a-agent-workspace-sandbox/theory/02-files-artifacts-and-workspace-policy.zh-CN.md) 与 [Container Isolation / Threat Model](../stages/09a-agent-workspace-sandbox/theory/03-container-isolation-and-threat-model.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_workspace.py`](test_workspace.py) | Core | Workspace path confinement、exclusive create、拒绝 `../` escape，以及 Docker command 的 default-deny baseline：无网络、read-only root、drop capabilities、no-new-privileges。 | 在给 Agent 一个“像电脑一样”的环境前，文件和命令必须先有 application-owned boundary。 |

这个测试只构造 Docker command，不需要真的启动容器。

## Stage 10 — Production Service、Identity、Jobs 与 Infrastructure

对应课程：[Stage 10 中文教程](../stages/10-production-deployment/README.zh-CN.md)，重点配合 [Service Boundaries 与 Identities](../stages/10-production-deployment/theory/01-service-boundaries-and-identities.zh-CN.md)、[Async / Concurrency / Streaming](../stages/10-production-deployment/theory/02-async-concurrency-streaming.zh-CN.md)、[Postgres / Redis / State](../stages/10-production-deployment/theory/03-postgres-redis-and-state.zh-CN.md)、[Authentication / Tenancy / Durable Jobs](../stages/10-production-deployment/theory/08-authentication-tenancy-and-durable-jobs.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_production.py`](test_production.py) | Core | Bounded async service、sync handler 离开 event loop、backpressure/capacity rejection、typed timeout，以及一个很重要的细节：sync worker 即使请求已经 timeout，只要真实 thread 还没结束，就仍然占用 capacity；readiness error 还必须脱敏。 | HTTP request timeout 不会自动杀死 worker thread，service capacity 必须反映真实 execution。 |
| [`test_service_identity.py`](test_service_identity.py) | Core | Client payload 不能自行声明 trusted identity；subject/tenant 只能由 server-authenticated identity 绑定；resource owner check 同时验证 subject 与 tenant。 | Request JSON 中写一个 `user_id` 不等于 authentication。 |
| [`test_jobs.py`](test_jobs.py) | Core / durable | SQLite run queue 跨 object recreation 存活；worker 通过 lease 获得 ownership；只有 lease owner 能 complete job。 | Durable work 在原 request/process 消失后仍然需要明确的执行所有权。 |
| [`test_stage10_integrations.py`](test_stage10_integrations.py) | Framework + Service | FastAPI liveness/readiness/run/request-id/streaming、安全 HTTP error、secret-safe settings、当前 A2A route；设置对应环境变量时还会运行真实 Redis fixed-window 与 Postgres pool 检查。 | 这是 Stage 10 最主要的 service-boundary integration suite。 |

使用 `.[dev,stage10]`。Redis/Postgres case 需要显式测试服务环境变量。

## Stage 10A — Long-Horizon Harness

对应课程：[Stage 10A 中文教程](../stages/10a-long-horizon-harness/README.zh-CN.md)。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_harness.py`](test_harness.py) | Core / durable | Task ledger 把 progress 外部化；新的 runtime object 可以接着完成未完成任务；worker crash 后遗留为 `running` 的 task 会被新 runtime 恢复并重试。 | Long-horizon progress 必须跨 model session/process loss 生存；“聊天还记得”不是 durability mechanism。 |

[`test_jobs.py`](test_jobs.py) 在这里也很重要：Stage 10A 建立在 Stage 10 durable job/lease 思想之上，但 service run queue 与 harness task ledger 仍然是不同 scope。

## Stage 11 — OpenScholar Capstone

对应课程：[Stage 11 中文教程](../stages/11-capstone-enterprise-agent/README.zh-CN.md)。这些测试不是重新孤立讲解前面的机制，而是验证它们组合之后是否仍然保持原来的边界。

| 测试文件 | 类型 | 实际验证什么 | 为什么值得读 |
|---|---|---|---|
| [`test_capstone.py`](test_capstone.py) | Core composition | Evidence threshold / abstention、grounded report evaluation、explicit-request memory、HITL export、workspace path confinement、unknown citation detection。 | 证明即使单个组件都能工作，研究 Agent 仍然必须受到 evidence 与 side-effect governance。 |
| [`test_capstone_v2.py`](test_capstone_v2.py) | Core + Framework | 限制同一 document 重复 chunk、复用 Stage 04 Qdrant retriever contract，并把 semantic citation support 与“citation label 是否存在”分开。 | 有 `[E1]` 并不代表 `[E1]` 真能支撑这一句 claim；retrieval diversity 也会影响 synthesis quality。 |
| [`test_openscholar_production.py`](test_openscholar_production.py) | Framework | 通过 authenticated FastAPI boundary 提供 OpenScholar，并验证 identity 来自 server authentication，而不是 request body 的 `user_id`。 | 把最终 capstone 重新接回 Stage 10 identity / tenant rule。 |
| [`test_stage11_integrations.py`](test_stage11_integrations.py) | Framework composition | LangGraph OpenScholar 完成任务、HITL resume/export、base 与 graph 两种 HTTP implementation，以及 Stage 11 MCP / A2A / API examples 的 smoke test。 | 最终验证主要生态边界可以组合在一起，而不会改变 domain invariant。 |

Stage 11 还会运行 [`test_openai_embeddings.py`](test_openai_embeddings.py)，因为 capstone 可以把确定性的教学 embedding 替换成 provider adapter。

使用 `.[dev,stage11]` 运行完整 integration suite。

---

# 4. Cross-stage Regression Tests

有些测试故意不只属于某一个 Stage。后面的 Stage 应该增强前面的机制，而不能因为“加了更高级的功能”就悄悄破坏早先已经建立的边界。

| 测试文件 | 连接哪些 Stage | 保护什么 |
|---|---|---|
| [`test_workflow_safety.py`](test_workflow_safety.py) | Stage 02 Workflow + Stage 07 Safe Failure | 预期的 `StepFailure` 可以携带开发者明确声明安全的 operational message；意外 exception 则只能留下安全 type/classification，不能把内部 secret text 写进 workflow state。 |
| [`test_openai_embeddings.py`](test_openai_embeddings.py) | Stage 04 Retrieval + Stage 11 Production Retrieval | Provider-specific embedding implementation 必须继续满足 Stage 04 已经定义好的 provider-neutral `EmbeddingModel` contract。 |
| [`test_observed_runtime.py`](test_observed_runtime.py) | Stage 07 Guarded Execution + Stage 08 Tracing | 增加 observability 之后不能绕过原来的 redaction / permission / failure semantics。 |
| [`test_jobs.py`](test_jobs.py) | Stage 10 Durable Jobs + Stage 10A Harness | 两者都需要 durable ownership/progress，但 service run lease 与 harness task ledger 不是同一个对象。 |

如果后续重构让这类测试失败，不要第一反应就是“把 test 改到通过”。先判断：架构是否真的有意改变？还是新的 abstraction 破坏了前面 Stage 的不变量？

---

# 5. 某类测试失败时，优先检查哪里？

| 失败类型 | 第一优先检查位置 |
|---|---|
| `test_runtime*` | `src/tiny_agent/runtime.py`、ToolCall/observation sequence、stop condition |
| `test_openai_adapter*`、`test_structured_decision*` | provider adapter normalization 与 provider-response validation |
| `test_workflows*` | route/Plan validation、Planner/Executor ownership、execution/replan budget |
| `test_state_graph*`、`test_langgraph_runtime*` | state update/edge semantics、graph stopping/checkpoint |
| `test_retrieval*`、`test_rag*`、vector backend tests | chunking、embedding contract、ranking/filtering、retrieval/evidence decision |
| MCP tests | async Tool boundary、protocol version/API shape、bridge namespace/error conversion |
| memory/approval/persistence tests | identity namespace、write policy、checkpoint/Store 区别、interrupt/resume |
| reliability/governance tests | validation、typed failure、retry safety、budget、permission/approval 顺序 |
| observability/evaluation tests | trace privacy、span relationship、metric 定义/coverage、regression gate |
| multi-Agent tests | active ownership、allowed edge、context projection、coordination budget |
| workspace tests | path normalization/confinement、sandbox command policy |
| production tests | concurrency/backpressure、trusted identity、lease、health/readiness、external infra |
| capstone tests | evidence、citation support、HITL、identity、retrieval 与 framework boundary 的组合 |

一个 failing assertion 只有在你能把它重新连接到对应 architecture invariant 时，才真正具有学习价值。

---

# 6. 这些测试没有证明什么？

整个测试套件全部通过，也**不代表**你的部署自动满足所有安全、合规、扩展性或生产 threat model。

例如：

- Docker command-policy test 不等于完整证明 container isolation；
- deterministic RAG test 不等于证明你真实领域 corpus 上 retrieval quality 足够好；
- permission unit test 不能替代企业 IAM / RBAC / ABAC 设计；
- local SQLite durability 不意味着 distributed exactly-once side effect；
- offline A2A/MCP object test 不代表 remote service authentication 和 network reliability 已解决；
- LLM-judge interface test 也不能证明 judge 没有偏差或已经校准。

`tests/` 的职责更窄，但也更明确：

> **把课程中每一条架构承诺变成一个可执行 contract；当实现发生漂移时，让它明确失败，而不是静默改变语义。**

以后如果在 `src/tiny_agent/` 中增加新的 Agent 机制，除了增加/更新测试，也应该同步维护本指南和 [English test guide](README.md)，让未来学习者始终能回答：**“这个 test 到底在验证什么？它属于哪一部分课程？”**

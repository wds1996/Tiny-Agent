# Stage 15 — OpenScholar：完整现代 Agent Capstone

OpenScholar 是 Tiny-Agent 2026 完整学习路径的最终集成测试。

之所以选择“学术研究 Agent”作为 Capstone，是因为这个领域会强迫架构明确区分：**发现（discovery）与证据（evidence）、memory 与 truth、context 与 state、模型提案与控制策略，以及短请求与 durable work**。

## 最终系统集成了什么

```text
Stage 00   LLM / Structured Output / Function Calling / context-cost 基础
Stage 01   ReAct runtime + provider adapters + Tool interface design
Stage 02   bounded planning / routing / replanning
Stage 03   explicit state + LangGraph
Stage 04   RAG / vector retrieval / reranking / evaluation
Stage 05   MCP 2026 core + extensions concepts
Stage 06   memory / checkpoints / durable HITL
Stage 07  context engineering / compaction / JIT context
Stage 08  Agent Skills / procedural knowledge
Stage 09   reliability / safety / governance
Stage 10   tracing / evaluation / regression
Stage 11   multi-Agent / handoffs / A2A
Stage 12  governed workspace / sandbox compute
Stage 13   production serving / identity / durable jobs
Stage 14  long-horizon harness / task ledger / rehydration
```

## 领域架构

```text
question
  ↓
remembered user preferences（不是 evidence）
  ↓
bounded research plan
  ↓
parallel retrieval
  ├── local full text
  └── scholarly metadata discovery
  ↓
trust normalization + score filtering + optional document diversity
  ↓
evidence sufficiency gate
  ├── insufficient -> abstain
  └── sufficient
        ↓
      synthesis
        ↓
 supervisor -> critic -> optional writer
        ↓
 deterministic citation inventory checks
        ↓
 optional semantic citation-support judge
        ↓
 memory write policy
        ↓
 optional human-approved authorized export
        ↓
 ResearchReport + trace + metrics
```

## 两种编排实现

### `BaseOpenScholarAgent`

使用普通 Python / `asyncio` 加 Tiny-Agent primitives。它最大的价值是：控制流非常容易直接检查。

### `LangGraphOpenScholarAgent`

使用相同的领域概念，但通过 `StateGraph`、checkpointer，以及 durable `interrupt` / `Command(resume=...)` 组织运行。

两者共享 domain policy，但 durable execution semantics **故意不完全相同**：

```text
Base version
    -> 返回 approval_required
    -> continuation 需要 application 自己管理

LangGraph version
    -> 可以持久化暂停中的 graph
    -> 之后从 checkpoint resume
```

这不是实现不一致，而是为了准确展示“图编排基础设施究竟增加了什么能力”。

## Evidence Contract

```text
local_fulltext
    -> 实际已经 ingest 的 substantive source text

scholarly_metadata
    -> title / authors / year / venue / DOI 等 discovery facts
    -> 不能作为论文研究结论的证明
```

确定性 evaluator 会检查 citation label 是否存在，以及 grounding gate 是否满足。

可选的 semantic evaluator 则另外回答：

> 被引用的 evidence 是否真的以当前表述强度支持这条 claim？

这两个问题不能混成一个模糊的“citation 看起来对不对”。

## Production Retrieval Path

为了 reproducible learning 和 CI，原来的离线 `HashEmbeddingModel` 会继续保留。

生产形态增加：

```text
OpenAIEmbeddingModel（provider adapter）
        +
QdrantRetriever
        +
RetrieverResearchCorpus
        +
DiversifiedResearchCorpus
```

这样生产系统可以使用真实 neural embedding、带 filter / persistence 的 vector database，以及 repeated-document diversity，而无需修改 `ResearchReport` 或研究 Agent 的主控制流。

参见：

- `src/tiny_agent/integrations/openai_embeddings.py`
- `src/tiny_agent/capstone/production_corpus.py`
- `code/production_retrieval_demo.py`

## Production Service Boundary

最初的教学 API 故意把 body-level `user_id` 暴露成 demo metadata。**不要把它当作 production authentication。**

升级后的生产边界：

```text
HTTP request
-> deployment-specific authenticator
-> AuthenticatedIdentity(subject / roles / tenant)
-> bind trusted metadata
-> BoundedAgentService
-> BaseOpenScholarAgent
```

request schema 中不再包含 identity fields。

参见：

- `src/tiny_agent/integrations/openscholar_production.py`
- `code/production_api_app.py`

Durable HITL 仍属于 LangGraph / checkpointer 路径。真正部署时，还必须把 persisted thread ownership 与 authenticated identity 绑定后，才允许 resume。

知道一个 `thread_id` 从来不等于拥有它。

## Quick Start

安装：

```bash
python -m pip install -e ".[dev,stage15]"
```

离线 deterministic capstone：

```bash
python stages/15-capstone-enterprise-agent/code/base_offline_demo.py
python stages/15-capstone-enterprise-agent/code/langgraph_demo.py
python stages/15-capstone-enterprise-agent/code/langgraph_hitl_demo.py
python stages/15-capstone-enterprise-agent/code/evaluation_demo.py
```

构建真实论文 corpus：

```bash
python stages/15-capstone-enterprise-agent/code/bootstrap_open_corpus.py
python stages/15-capstone-enterprise-agent/code/base_real_corpus_demo.py
```

可选真实 semantic retrieval（需要 OpenAI API key）：

```bash
python stages/15-capstone-enterprise-agent/code/production_retrieval_demo.py
```

生产形态的 authenticated / bounded API demo：

```bash
export OPEN_SCHOLAR_DEMO_API_KEY='local-secret'
python stages/15-capstone-enterprise-agent/code/production_api_app.py
```

## 理论学习顺序

1. `theory/01-capstone-system-design.md`
2. `theory/02-evidence-and-knowledge-base.md`
3. `theory/03-base-implementation.md`
4. `theory/04-langgraph-implementation.md`
5. `theory/05-memory-hitl-safety.md`
6. `theory/06-evaluation-observability.md`
7. `theory/07-production-mcp-a2a.md`
8. `theory/08-modern-production-profile.md`

中文阅读时使用同目录的 `*.zh-CN.md`；代码、测试、manifest 与配置继续和英文教程共用同一份真实实现。

## Interoperability

```text
MCP
  -> 暴露 corpus / search capability

A2A
  -> 把 OpenScholar 暴露为 independent remote Agent

HTTP
  -> 普通 application / service client boundary
```

不要把 protocol compatibility 与 authentication / trust 混为一谈。

## 这里所谓“完整”是什么意思

仓库现在包含现代 Agent 各主要子系统的代码路径：

```text
model/provider boundary
Tool use
planning
state
RAG
MCP
memory
HITL
context engineering
Skills
safety
evaluation
multi-Agent / A2A
workspace / sandbox
service identity
durable jobs
long-horizon harnesses
deployment
```

默认 OpenScholar demo 仍然故意保持 local / offline，以便学习和 CI 可重复。

真正 enterprise production 仍需要组织自己选择：

- real IAM；
- durable Postgres checkpointer / Store；
- managed sandbox infrastructure；
- data retention / licensing；
- hardened egress；
- autoscaling；
- backups；
- operational SLOs。

这个区分是刻意的：

> **Tiny-Agent 现在教授的是完整架构，并提供可以运行的 reference mechanisms；它不会假装一个教学仓库能够替每个组织提供全部生产基础设施和安全策略。**
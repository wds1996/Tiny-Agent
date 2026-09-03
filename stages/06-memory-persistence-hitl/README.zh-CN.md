# Stage 06 — Memory、Durable Persistence 与 Human-in-the-Loop

Stage 06 讲解一个 Agent 如何 **有选择地记忆、在进程重启后继续执行，并在高影响 side effect 前安全暂停等待人工审查**。

本阶段直接建立在 Stage 03 的 LangGraph checkpoint / interrupt 基础上，但不会重复 Stage 03。

Stage 03 回答：

> Checkpoint 和 interrupt 是什么？

Stage 06 进一步问：

> 什么值得被记住？应该存在哪里？执行如何跨 restart 生存？谁有权批准真正的 side effect？

核心原则：

> **Memory 不是一个万能桶。Persistence 不等于 long-term memory。Human approval 不等于 authorization。**

---

# 学习路径

```text
context / state / checkpoint / memory boundaries
        ↓
thread-scoped short-term memory
        ↓
context trimming / summarization / retention
        ↓
MemoryCandidate + MemoryWritePolicy
        ↓
cross-thread long-term Store
        ↓
InMemorySaver vs SQLiteSaver vs PostgresSaver
        ↓
durable resume after process recreation
        ↓
approve / edit / reject HITL
        ↓
durable HITL across restart
        ↓
privacy / tenancy / deletion / memory poisoning / audit
```

顺序是刻意的。

如果一开始就“装 Redis，然后叫它 memory”，你是在 memory semantics 还没定义前先选 infrastructure。

---

# 前置要求

完成 Stage 00–05，或已经理解：

- Structured Output / Function Calling；
- ReAct / Tool runtime；
- Workflow vs Agent control ownership；
- explicit graph state；
- LangGraph node/edge/checkpoint/interrupt 基础；
- RAG vs external evidence；
- MCP capability boundary；
- Python context manager 与 database 基础。

Stage 03 尤其重要，因为本阶段默认你已理解：

```text
checkpointer
thread_id
interrupt(...)
Command(resume=...)
node restart on resume
```

---

# 学习目标

完成 Stage 06 后，你应该能够：

1. 区分 LLM context、runtime state、checkpoint、short-term memory、long-term memory、RAG knowledge；
2. 解释 `thread_id` 与 `user_id` 为什么不是一回事；
3. 用 checkpointer 保留 thread-scoped state；
4. 解释 context trimming、token budget、summarization trade-off；
5. 区分 semantic / episodic / procedural memory；
6. 区分 semantic memory 与 semantic search；
7. 比较 profile-style memory 与 memory item collection；
8. 解释 hot-path memory write vs background consolidation；
9. 把 model-extracted memory 视为 proposal，而不是 authorized write；
10. 使用 conservative memory-write policy；
11. 使用 LangGraph Store 做 cross-thread memory；
12. 即使二者都用 PostgreSQL，也能解释 Checkpointer vs Store；
13. 比较 `InMemorySaver`、`SqliteSaver`、`PostgresSaver`；
14. 证明 checkpoint 可以跨 runtime object recreation 生存；
15. 解释 checkpoint history、replay、schema migration；
16. 解释 durable recovery 为什么不保证 external side effect exactly-once；
17. 使用 `approve`、`edit`、`reject` review outcome；
18. human edit 后重新 validate arguments；
19. 解释 approval 为什么不替代 authorization；
20. 原 process 消失后仍能 resume human-reviewed workflow；
21. 讨论 memory ownership、consent、retention、deletion、multi-tenant isolation；
22. 解释 memory poisoning，以及 procedural memory 为什么需要更强 governance；
23. 知道 Stage 08 应观察哪些 memory/HITL signal。

---

# Part A — 先画清边界

阅读：

1. [Context、State、Checkpoint 与 Memory](theory/01-context-state-checkpoint-memory.zh-CN.md)
2. [Short-term Memory 与 Context Management](theory/02-short-term-memory-and-context-management.zh-CN.md)

运行：

```bash
python stages/06-memory-persistence-hitl/code/thread_short_term_memory.py
```

你必须能不看笔记画出：

```text
LLM context
    = selected data visible to the model now

runtime state
    = data required to continue execution

checkpoint
    = persisted execution snapshot/version

short-term memory
    = thread-scoped retained state

long-term memory
    = selected information across threads

RAG knowledge
    = external evidence/document corpus
```

在 `thread_id != user_id` 没有变成直觉之前，不要继续。

---

# Part B — 决定什么值得 long-term memory

阅读：

3. [Long-term Memory 与 Write Policy](theory/03-long-term-memory-and-write-policy.zh-CN.md)

运行：

```bash
python stages/06-memory-persistence-hitl/code/memory_write_policy.py
python stages/06-memory-persistence-hitl/code/long_term_memory_store.py
```

Tiny-Agent 引入 framework-neutral primitive：

```python
MemoryCandidate
ConservativeMemoryWritePolicy
```

Model/application 可以提出：

```python
candidate = MemoryCandidate(
    namespace=("user-42", "memories"),
    key="explanation-style",
    value={"style": "concise Chinese + runnable examples"},
    kind="semantic",
    explicit_user_request=True,
)
```

真正 durable write 仍需经过 policy：

```python
decision = policy.evaluate(candidate)

if decision.store:
    store.put(candidate.namespace, candidate.key, candidate.value)
```

Baseline policy 会故意拒绝：

```text
没有 explicit remember request 的 incidental fact
sensitive data
procedural self-rewrite
```

这是一种保守教学 baseline，不是所有产品的唯一 policy。

---

# Part C — Short-term memory vs long-term Store

当前 LangGraph semantics 与我们的概念模型可以清楚映射：

```text
Checkpointer
    ↓
thread-scoped execution / short-term memory

Store
    ↓
custom namespace + key
cross-thread long-term memory
```

例如：

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()
namespace = ("user-42", "memories")
store.put(
    namespace,
    "preferred-language",
    {"language": "Chinese"},
)

memory = store.get(namespace, "preferred-language")
```

一个 user 可以有很多 thread，但通过 user-owned namespace 分享经过选择的 long-term memories。

---

# Part D — 让 execution 真正 durable

阅读：

4. [Durable Persistence 与 Resume](theory/04-durable-persistence-and-resume.zh-CN.md)

运行：

```bash
python stages/06-memory-persistence-hitl/code/sqlite_durable_checkpoint.py
```

Demo 会明确做：

```text
Saver + Graph A
    ↓
write checkpoint
    ↓
close both objects
    ↓
Saver + Graph B
    ↓
load same SQLite file + thread_id
    ↓
recover state
```

这证明 state 不再依赖原 Python object 的寿命。

---

# Persistence backend ladder

## `InMemorySaver`

适合：

- unit test；
- tutorial；
- local semantics。

Process 消失，它也消失。

## `SqliteSaver`

适合：

- local durable demo；
- lightweight local workflow；
- 学习 restart/recovery semantics。

Stage 06 使用它，因为 durability 可见、容易复现。

## `PostgresSaver`

作为 production-oriented shared persistence 示例。

Stage 06 不是只展示 import，而是真正包含 Postgres CI integration tests。

安装：

```bash
python -m pip install -e ".[dev,stage06]"
```

本地 Postgres 示例：

```bash
export DATABASE_URL='postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable'
python stages/06-memory-persistence-hitl/code/postgres_persistence.py
```

同一示例同时使用：

```text
PostgresSaver -> execution checkpoints
PostgresStore -> cross-thread long-term memory
```

同一种 infrastructure family，不代表相同语义。

---

# Part E — Human review 不只是 Yes / No

阅读：

5. [Human-in-the-Loop 与 Approval](theory/05-human-in-the-loop-and-approval.zh-CN.md)

运行：

```bash
python stages/06-memory-persistence-hitl/code/human_approval.py
```

Tiny-Agent 增加：

```python
ApprovalRequest
ApprovalDecision
ApprovalResolution
```

三种 outcome：

```text
approve
    -> execute reviewed arguments

edit
    -> human changes arguments, then application revalidates

reject
    -> no executable arguments are returned
```

安全 execution shape：

```text
model proposes side effect
        ↓
review policy
        ↓
interrupt
        ↓
human approve / edit / reject
        ↓
schema validation
        ↓
authorization
        ↓
side effect
```

绝不能把真实 side effect 放在 interrupt 前面，再问大家“刚才那个操作你们满意吗？”

---

# Part F — 跨 process restart 的 Durable HITL

运行：

```bash
python stages/06-memory-persistence-hitl/code/durable_hitl_resume.py
```

这是本阶段 milestone：

```text
runtime A
  -> prepare production action
  -> interrupt
  -> save checkpoint in SQLite
  -> runtime A disappears

runtime B
  -> reconstruct graph
  -> open same SQLite DB
  -> same thread_id
  -> Command(resume=human_decision)
  -> continue
```

Reviewer 不需要 original Python process 一直活着。

这才是 operationally durable HITL。

---

# Part G — 宣布胜利前先做 governance

阅读：

6. [Memory Governance 与 Production](theory/06-memory-governance-and-production.zh-CN.md)

包括：

- namespace ownership / multi-tenancy；
- consent / user expectation；
- sensitive information；
- retention / forgetting；
- memory conflict resolution；
- procedural-memory governance；
- memory poisoning；
- checkpoint security；
- concurrency / lost updates；
- memory/HITL evaluation signals。

然后完成：

[复习题](exercises/review-questions.zh-CN.md)

---

# Code map

```text
code/
├── memory_write_policy.py
├── thread_short_term_memory.py
├── long_term_memory_store.py
├── sqlite_durable_checkpoint.py
├── human_approval.py
├── durable_hitl_resume.py
└── postgres_persistence.py
```

推荐顺序：

```text
memory_write_policy.py
        ↓
thread_short_term_memory.py
        ↓
long_term_memory_store.py
        ↓
sqlite_durable_checkpoint.py
        ↓
human_approval.py
        ↓
durable_hitl_resume.py
        ↓
postgres_persistence.py
```

---

# Theory map

```text
theory/
├── 01-context-state-checkpoint-memory.zh-CN.md
├── 02-short-term-memory-and-context-management.zh-CN.md
├── 03-long-term-memory-and-write-policy.zh-CN.md
├── 04-durable-persistence-and-resume.zh-CN.md
├── 05-human-in-the-loop-and-approval.zh-CN.md
└── 06-memory-governance-and-production.zh-CN.md
```

---

# Tests

Framework-neutral policy：

```bash
pytest -q \
  tests/test_memory_policy.py \
  tests/test_approval.py
```

LangGraph + SQLite + local Store：

```bash
pytest -q tests/test_stage06_langgraph.py
```

Postgres integration 在 GitHub Actions 自动运行；本地需要数据库：

```bash
TEST_POSTGRES_URI='postgresql://...' \
pytest -q tests/test_stage06_postgres.py
```

---

# 外部学习资源

## 1. LangGraph memory docs

- Memory: <https://docs.langchain.com/oss/python/langgraph/add-memory>
- Long-term memory / Store: <https://docs.langchain.com/oss/python/langchain/long-term-memory>

Parts A–C 后再读，用于把 Tiny-Agent conceptual boundary 映射到当前 API。

## 2. Persistence docs

- <https://docs.langchain.com/oss/python/langgraph/persistence>

运行 `sqlite_durable_checkpoint.py` 后阅读，重点看：

```text
threads
checkpoints
checkpoint history
SqliteSaver
PostgresSaver
serialization
```

## 3. Interrupt docs

- <https://docs.langchain.com/oss/python/langgraph/interrupts>

运行 `human_approval.py` 后阅读，特别注意：

- `Command` resume；
- node restart semantics；
- interrupt 前的 idempotent side effect；
- interrupt ordering / serializable payload。

## 4. High-level LangChain HITL

- <https://docs.langchain.com/oss/python/langchain/human-in-the-loop>

只有理解 lower-level LangGraph mechanism 后再读，观察 high-level API 如何包装 approve/edit/reject policy。

## 5. Academic memory architecture

- Sumers et al., *Cognitive Architectures for Language Agents (CoALA)*: <https://arxiv.org/abs/2309.02427>

它用于拓宽 memory/action architecture 视角，不是 SDK tutorial。

---

# 推荐初学顺序

```text
1. Stage 03 persistence/interrupt refresher
2. Stage 06 theory 01
3. thread_short_term_memory.py
4. Stage 06 theory 02
5. memory_write_policy.py
6. Stage 06 theory 03
7. long_term_memory_store.py
8. official LangGraph Memory docs
9. sqlite_durable_checkpoint.py
10. Stage 06 theory 04
11. official Persistence docs
12. human_approval.py
13. Stage 06 theory 05
14. official Interrupt docs
15. durable_hitl_resume.py
16. high-level LangChain HITL comparison
17. Stage 06 theory 06
18. CoALA paper / exercises
```

---

# Stage boundary

Stage 06 不宣称已经完成全部 production memory engineering。

留到后续/更深实现的问题包括：

- sophisticated semantic memory retrieval/reranking；
- background consolidation infrastructure；
- conflict-free distributed memory write；
- 完整 GDPR/行业 privacy implementation；
- secret-management system；
- enterprise RBAC/ABAC approval system；
- distributed exactly-once side-effect semantics；
- retry/circuit-breaker/tool sandbox policy（Stage 07）；
- memory/HITL metrics/tracing（Stage 08）；
- full service/deployment operations（Stage 10）。

---

# Milestone

完成 Stage 06 后，你应该能够构建并解释一个 Agent：

```text
maintains thread-scoped state
        +
selectively writes cross-thread memory
        +
persists execution to durable storage
        +
pauses for approve/edit/reject review
        +
can resume after the original runtime is gone
```

真正的问题不再是：

> “Agent 有没有 memory？”

而是：

> **记住什么？谁拥有它？保存多久？什么 execution 能恢复？哪个 human/policy 有权授权下一次 side effect？**
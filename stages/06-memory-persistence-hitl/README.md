# Stage 06 — Memory, Durable Persistence & Human-in-the-Loop

Stage 06 teaches how an Agent can **remember deliberately, survive process restarts, and pause safely for human review before consequential actions**.

This stage builds directly on Stage 03's introduction to LangGraph checkpoints and interrupts, but it does not repeat that lesson. Stage 03 answered:

> What is a checkpoint or interrupt?

Stage 06 asks the production-minded questions:

> What should be remembered, where should it live, how does execution survive a restart, and who is allowed to approve a side effect?

The central lesson is:

> **Memory is not a bucket. Persistence is not long-term memory. Human approval is not authorization.**

---

# Learning path

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

This order is deliberate.

If you begin with "install Redis and call it memory," you have chosen infrastructure before deciding what memory means.

---

# Prerequisites

Complete Stage 00–05, or already understand:

- Structured Output and Function Calling;
- ReAct/tool runtimes;
- workflow vs Agent control ownership;
- explicit graph state;
- LangGraph nodes/edges/checkpoints/interrupt basics;
- RAG vs external evidence;
- MCP capability boundaries;
- basic Python context managers and database concepts.

Stage 03 is especially important because Stage 06 assumes you already understand:

```text
checkpointer
thread_id
interrupt(...)
Command(resume=...)
node restart on resume
```

---

# Learning objectives

After Stage 06, you should be able to:

1. distinguish LLM context, runtime state, checkpoint, short-term memory, long-term memory, and RAG knowledge;
2. explain why `thread_id` and `user_id` are different identities;
3. use a checkpointer to retain thread-scoped state;
4. explain context trimming, token budgets, and summarization tradeoffs;
5. distinguish semantic, episodic, and procedural memory;
6. distinguish semantic memory from semantic search;
7. compare profile-style memory with collections of memory items;
8. explain hot-path vs background memory writes;
9. treat a model-extracted memory as a proposal rather than an authorized write;
10. use a conservative memory-write policy;
11. use LangGraph Store for cross-thread memory;
12. explain Checkpointer vs Store even when both use PostgreSQL;
13. compare `InMemorySaver`, `SqliteSaver`, and `PostgresSaver`;
14. prove that a checkpoint survives recreation of runtime objects;
15. explain checkpoint history, replay, and schema migration concerns;
16. explain why durable recovery does not guarantee exactly-once external side effects;
17. use `approve`, `edit`, and `reject` review outcomes;
18. revalidate edited arguments before execution;
19. explain why approval does not replace authorization;
20. resume a human-reviewed workflow after the original process is gone;
21. reason about memory ownership, consent, retention, deletion, and multi-tenant isolation;
22. explain memory poisoning and why procedural memory needs stronger governance;
23. identify the observability/evaluation signals that Stage 08 should later measure.

---

# Part A — Draw the boundaries first

Read:

1. [`theory/01-context-state-checkpoint-memory.md`](theory/01-context-state-checkpoint-memory.md)
2. [`theory/02-short-term-memory-and-context-management.md`](theory/02-short-term-memory-and-context-management.md)

Run:

```bash
python stages/06-memory-persistence-hitl/code/thread_short_term_memory.py
```

You should be able to draw this without notes:

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

Do not continue until `thread_id != user_id` feels obvious.

---

# Part B — Decide what deserves long-term memory

Read:

3. [`theory/03-long-term-memory-and-write-policy.md`](theory/03-long-term-memory-and-write-policy.md)

Run:

```bash
python stages/06-memory-persistence-hitl/code/memory_write_policy.py
python stages/06-memory-persistence-hitl/code/long_term_memory_store.py
```

Tiny-Agent introduces two framework-neutral primitives:

```python
MemoryCandidate
ConservativeMemoryWritePolicy
```

The model/application may produce a candidate:

```python
candidate = MemoryCandidate(
    namespace=("user-42", "memories"),
    key="explanation-style",
    value={"style": "concise Chinese + runnable examples"},
    kind="semantic",
    explicit_user_request=True,
)
```

but durable storage happens only after policy:

```python
decision = policy.evaluate(candidate)

if decision.store:
    store.put(candidate.namespace, candidate.key, candidate.value)
```

The baseline policy deliberately rejects:

```text
incidental facts without an explicit remember request
sensitive data
procedural self-rewrites
```

This is intentionally conservative teaching behavior, not a universal product policy.

---

# Part C — Short-term memory vs long-term Store

Current LangGraph semantics map cleanly to the model we just built:

```text
Checkpointer
    ↓
thread-scoped execution / short-term memory

Store
    ↓
custom namespace + key
cross-thread long-term memory
```

Example:

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

One user may have many thread IDs while sharing selected memories through a user-owned namespace.

---

# Part D — Make execution durable

Read:

4. [`theory/04-durable-persistence-and-resume.md`](theory/04-durable-persistence-and-resume.md)

Run:

```bash
python stages/06-memory-persistence-hitl/code/sqlite_durable_checkpoint.py
```

The example deliberately creates:

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

That proves the state no longer depends on the original Python objects.

---

# Persistence backend ladder

## `InMemorySaver`

Use for:

- unit tests;
- tutorials;
- local semantics.

It disappears with the process.

## `SqliteSaver`

Use for:

- local durable demos;
- lightweight local workflows;
- learning restart/recovery semantics.

Stage 06 uses it because the durability is visible and easy to reproduce.

## `PostgresSaver`

Use as the production-oriented shared persistence example.

Stage 06 includes real Postgres CI integration tests rather than only an import example.

Install Stage 06 dependencies:

```bash
python -m pip install -e ".[dev,stage06]"
```

Optional local Postgres example:

```bash
export DATABASE_URL='postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable'
python stages/06-memory-persistence-hitl/code/postgres_persistence.py
```

The example uses both:

```text
PostgresSaver -> execution checkpoints
PostgresStore -> cross-thread long-term memory
```

Same infrastructure family, different semantics.

---

# Part E — Human review is more than Yes/No

Read:

5. [`theory/05-human-in-the-loop-and-approval.md`](theory/05-human-in-the-loop-and-approval.md)

Run:

```bash
python stages/06-memory-persistence-hitl/code/human_approval.py
```

Tiny-Agent adds:

```python
ApprovalRequest
ApprovalDecision
ApprovalResolution
```

with three outcomes:

```text
approve
    -> execute reviewed arguments

edit
    -> human changes arguments, then application revalidates

reject
    -> no executable arguments are returned
```

The safe execution shape is:

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

Never place the real side effect before the interrupt and then ask whether everybody enjoyed it.

---

# Part F — Durable HITL across process restart

Run:

```bash
python stages/06-memory-persistence-hitl/code/durable_hitl_resume.py
```

This is the stage milestone.

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

The reviewer does not need the original Python process to stay alive.

That is what **durable human-in-the-loop** means operationally.

---

# Part G — Governance before declaring victory

Read:

6. [`theory/06-memory-governance-and-production.md`](theory/06-memory-governance-and-production.md)

Topics include:

- namespace ownership and multi-tenancy;
- consent and user expectation;
- sensitive information;
- retention and forgetting;
- memory conflict resolution;
- procedural-memory governance;
- memory poisoning;
- checkpoint security;
- concurrency/lost updates;
- memory/HITL evaluation signals.

Then complete:

[`exercises/review-questions.md`](exercises/review-questions.md)

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

Suggested order:

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
postgres_persistence.py (optional local DB)
```

---

# Theory map

```text
theory/
├── 01-context-state-checkpoint-memory.md
├── 02-short-term-memory-and-context-management.md
├── 03-long-term-memory-and-write-policy.md
├── 04-durable-persistence-and-resume.md
├── 05-human-in-the-loop-and-approval.md
└── 06-memory-governance-and-production.md
```

---

# Tests

Framework-neutral policies:

```bash
pytest -q \
  tests/test_memory_policy.py \
  tests/test_approval.py
```

LangGraph + SQLite + local Store:

```bash
pytest -q tests/test_stage06_langgraph.py
```

Postgres integration requires a database and is run automatically in GitHub Actions:

```bash
TEST_POSTGRES_URI='postgresql://...' \
pytest -q tests/test_stage06_postgres.py
```

---

# External learning resources

Use these resources in this order rather than opening ten framework tabs at once.

## 1. Official LangGraph memory docs

- Memory: <https://docs.langchain.com/oss/python/langgraph/add-memory>
- Long-term memory / Store concepts: <https://docs.langchain.com/oss/python/langchain/long-term-memory>

Use these after Parts A–C to map Tiny-Agent's conceptual boundaries onto current APIs.

## 2. Official persistence docs

- LangGraph Persistence: <https://docs.langchain.com/oss/python/langgraph/persistence>

Read after `sqlite_durable_checkpoint.py`.

Focus on:

```text
threads
checkpoints
checkpoint history
SqliteSaver
PostgresSaver
serialization
```

## 3. Official interrupt docs

- LangGraph Interrupts: <https://docs.langchain.com/oss/python/langgraph/interrupts>

Read after `human_approval.py`.

Pay special attention to:

- resume with `Command`;
- node restart semantics;
- idempotent side effects before interrupts;
- interrupt ordering and serializable payloads.

## 4. High-level LangChain HITL comparison

- LangChain Human-in-the-Loop middleware: <https://docs.langchain.com/oss/python/langchain/human-in-the-loop>

Only read this **after** the lower-level LangGraph mechanism is clear.

It is useful for seeing how mature Agent APIs package approve/edit/reject policies.

## 5. Academic memory architecture

- Sumers et al., *Cognitive Architectures for Language Agents (CoALA)*: <https://arxiv.org/abs/2309.02427>

Use it for a broader memory/action architecture perspective rather than as an SDK tutorial.

---

# Recommended beginner reading order

```text
1. Stage 03 persistence/interrupt chapter refresher
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

Stage 06 deliberately does **not** claim to finish production memory engineering.

Deferred or expanded later:

- sophisticated semantic memory retrieval/reranking;
- background consolidation infrastructure;
- conflict-free distributed memory writes;
- complete GDPR/sector-specific privacy implementation;
- secret-management systems;
- enterprise RBAC/ABAC approval systems;
- distributed exactly-once side-effect semantics;
- retry/circuit-breaker/tool sandbox policy (Stage 07);
- memory/HITL metrics and tracing (Stage 08);
- full service/deployment operations (Stage 10).

This stage establishes the correct architecture and durable local/production-backend mechanics before those layers arrive.

---

# Milestone

By the end of Stage 06 you should be able to build and explain an Agent that:

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

The key question is no longer:

> Does the Agent have memory?

It is:

> **What is remembered, who owns it, how long does it live, what can be recovered, and which human/policy is allowed to authorize the next side effect?**

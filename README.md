# Tiny-Agent

> Learn AI Agents by building one from first principles to production.

Tiny-Agent is an open-source, learning-first Agent engineering project for **anyone who wants to understand how modern AI Agents actually work**.

The repository does not begin with a black-box framework call. It builds the stack progressively:

```text
LLM interfaces
    -> Structured Output / Function Calling
    -> ReAct runtime
    -> provider adapters
    -> workflow / routing / planning
    -> explicit state / LangGraph
    -> RAG / vector databases / Agentic retrieval
    -> MCP / standardized external capabilities
    -> memory / durable persistence / HITL
    -> reliability / safety / tool governance
    -> evaluation / observability
    -> multi-Agent
    -> production deployment
```

The goal is not only to make examples run. The goal is to understand **why each abstraction exists, what responsibility it owns, where it fails, and how it maps to maintainable software**.

---

# Core philosophy

1. **Mechanism before framework** — build or inspect the minimum mechanism first, then introduce the mature framework/tool that solves the same problem.
2. **Theory and code stay together** — each capability stage contains conceptual notes, runnable examples, tests, and exercises where applicable.
3. **Educational snapshots are preserved** — later framework code does not erase earlier handwritten implementations.
4. **Deterministic when possible, agentic when useful** — autonomy is added only where uncertainty justifies it.
5. **Model output is a proposal, not authority** — routes, plans, ToolCalls, retrieval queries, memory candidates, and actions remain subject to application validation and policy.
6. **Runtimes own execution** — LLMs can propose actions; application/runtime code governs execution, observations, budgets, stopping, data access, and durable side effects.
7. **State is explicit when orchestration demands it** — complex branching, persistence, interruption, and resumption should not be hidden in local variables.
8. **External evidence and remote capabilities are not authority** — retrieved documents, MCP metadata, remote prompts, Tool results, and remembered content retain explicit trust boundaries.
9. **Memory is governed state, not a magic bucket** — thread checkpoints, long-term memory, RAG knowledge, secrets, and audit logs have different semantics and lifecycles.
10. **Human approval is not authorization** — reviewed actions still require ordinary validation and application permission checks.
11. **Least privilege beats persuasive prompting** — capabilities, credentials, roles, approvals, budgets, and sandbox boundaries are deterministic controls, not instructions the model may reinterpret.
12. **Production concerns are part of Agent learning** — reliability, permissions, tracing, evaluation, cost, retention, privacy, and deployment are not optional afterthoughts.
13. **Tests include failure boundaries** — malformed provider data, invalid routes, loop budgets, unsafe failures, retrieval misses, remote capability errors, persistence failures, authorization denials, and state-transition errors are first-class test cases.
14. **Tutorial simplifications are documented** — beginner code may be intentionally small, but its production limitations must be explicit.

---

# Repository model

Tiny-Agent has two complementary layers:

```text
stages/
    stable learning modules and educational snapshots

src/tiny_agent/
    latest evolving reusable implementation
```

A concept is normally introduced in a stage before it becomes part of the integrated implementation.

Typical stage structure:

```text
stage-name/
├── README.md        # learning order, goals, milestone, external resources
├── theory/          # detailed conceptual notes
├── code/            # runnable teaching examples
└── exercises/       # review/coding/interview questions
```

---

# Learning path

The project is organized by **capability**, not by calendar day or framework name.

| Stage | Capability | Main milestone |
|---|---|---|
| [00 — Foundations](stages/00-foundations/) | LLM API, messages, Structured Output, Function Calling | Build a minimal tool-use loop without an Agent framework |
| [01 — ReAct Runtime](stages/01-react-runtime/) | ReAct, Tool Registry, runtime loop, provider adapter | Build and test a provider-neutral tool-using Agent runtime |
| [02 — Planning & Routing](stages/02-planning-routing/) | Workflow vs Agent, Router, Planner–Executor, bounded replanning | Choose the least dynamic architecture that solves a task |
| [03 — Stateful Orchestration](stages/03-stateful-orchestration/) | Explicit state, state machines, LangGraph, LangChain components, checkpoint/interrupt | Rebuild existing Agent/workflow patterns as inspectable state graphs |
| [04 — Agentic RAG](stages/04-agentic-rag/) | Chunking, embeddings, FAISS, Qdrant, retrievers, reranking, grounded Agentic retrieval | Build a bounded evidence-grounded retrieval Agent |
| [05 — MCP](stages/05-mcp/) | MCP 2026 stateless protocol, Tools/Resources/Prompts, stdio/HTTP, Python SDK v2 | Discover and consume standardized external capabilities through a clean Tiny-Agent bridge |
| [06 — Memory / Persistence / HITL](stages/06-memory-persistence-hitl/) | thread memory, long-term Store, SQLite/Postgres checkpoints, approve/edit/reject HITL | Persist and resume stateful Agents with deliberate memory and human-review policies |
| [07 — Reliability & Safety](stages/07-reliability-safety/) | typed failures, validation, timeout/retry, budgets, permissions, approval binding, injection/sandbox boundaries | Build a guarded runtime that fails predictably and limits model authority |
| [08 — Evaluation & Observability](stages/08-evaluation-observability/) | traces, trajectory eval, quality/cost/latency metrics | Measure whether Agent behavior actually works |
| [09 — Multi-Agent](stages/09-multi-agent/) | delegation, handoffs, specialists, interoperability | Justify when multiple Agents beat one Agent/workflow |
| [10 — Production Deployment](stages/10-production-deployment/) | FastAPI, async, PostgreSQL, Redis, Docker, CI | Turn Tiny-Agent into a deployable service |
| [11 — Enterprise Capstone](stages/11-capstone-enterprise-agent/) | integrated research/knowledge Agent | Combine the learning path into a portfolio-quality system |

For the framework/infrastructure mapping, see:

**[Framework & Tooling Map](docs/framework-and-tooling-map.md)**

---

# Current implemented stages

## ✅ Stage 00 — LLM & Tool-Use Foundations

- message-based LLM interaction;
- provider boundary;
- Structured Output / JSON Schema;
- Function Calling;
- minimal repeated tool loop;
- framework-free runnable example;
- review questions.

## ✅ Stage 01 — ReAct & Core Agent Runtime

- explicit ReAct feedback loop;
- normalized `ToolCall` / `ModelResponse`;
- `Tool` / `ToolRegistry`;
- maximum-step protection;
- OpenAI Responses provider adapter;
- `call_id` correlation;
- deterministic fake-model/provider tests;
- real multi-tool example;
- explicit production-limitations chapter.

## ✅ Stage 02 — Planning, Routing & Deterministic Workflows

- Workflow vs Agent decision framework;
- deterministic and semantic routing;
- schema-constrained control decisions;
- Planner–Executor separation;
- bounded replanning;
- plan/step/replan budgets;
- safe expected failure vs redacted unexpected failure;
- runnable deterministic and real-model examples;
- edge-case tests.

## ✅ Stage 03 — Stateful Orchestration

- explicit state and state-machine theory;
- handwritten `TinyStateGraph`;
- nodes, edges, conditional edges, cycles, START/END;
- LangGraph `StateGraph` fundamentals;
- LangGraph rebuild of the Stage 01 ReAct loop;
- graph version of Stage 02 Planner–Executor recovery;
- streaming state updates;
- checkpointing with `InMemorySaver` for teaching/testing;
- `interrupt()` / `Command(resume=...)` fundamentals;
- LangChain messages and Tool abstractions;
- curated official/community learning resources;
- dedicated framework compatibility tests.

## ✅ Stage 04 — RAG & Agentic Retrieval

- RAG fundamentals and fixed two-step RAG;
- chunking, overlap, metadata, and provider-neutral embedding interfaces;
- deterministic offline teaching embedding;
- cosine similarity and exact brute-force top-k retrieval;
- FAISS, Qdrant, and LangChain Retriever adapters;
- candidate retrieval vs reranking and hybrid-retrieval theory;
- bounded Agentic RAG query rewriting and evidence-sufficiency checks;
- explicit insufficient-evidence abstention;
- Recall@k / MRR and deterministic/backend tests.

## ✅ Stage 05 — MCP: Standardized Capabilities Across Boundaries

- Function Calling vs MCP boundary;
- Host / Client / Server mental model;
- Tools, Resources, Prompts, and resource templates;
- MCP 2026-07-28 stateless core and Python SDK v2;
- in-process, stdio, and Streamable HTTP examples;
- async Tool execution path;
- namespaced `MCPToolBridge`;
- remote capability trust/authorization boundaries;
- real SDK compatibility and runnable-example CI.

## ✅ Stage 06 — Memory, Durable Persistence & Human-in-the-Loop

- context vs state vs checkpoint vs short-/long-term memory;
- `thread_id` vs cross-thread owner namespace;
- semantic/episodic/procedural memory taxonomy;
- `MemoryCandidate` + conservative write policy;
- LangGraph Store for cross-thread memory;
- `InMemorySaver` / `SqliteSaver` / `PostgresSaver`;
- SQLite process-recreation durability;
- real PostgreSQL checkpointer/Store tests;
- approve/edit/reject review model;
- durable HITL resume;
- idempotency and memory-governance boundaries.

## ✅ Stage 07 — Reliability, Safety & Tool Governance

- typed model-safe Tool failures and raw-exception redaction;
- local Tool argument validation before handler execution;
- handwritten validation subset plus maintained `jsonschema` adapter;
- Pydantic strict-mode comparison for stable typed boundaries;
- async timeout/cancellation semantics and sync-worker caveats;
- bounded exponential retry/backoff and Tenacity comparison;
- retryable-failure vs retry-safe/idempotent-action separation;
- run-wide Tool/retry/time/token/cost budgets;
- exact repeated-ToolCall loop detection;
- default-deny role allowlists and authenticated `Principal` context;
- exact Tool+arguments approval binding;
- prompt-injection data/control-plane trust boundaries;
- narrow Tool and least-privilege guidance;
- process termination vs real sandbox distinction;
- composed `GuardedToolExecutor`;
- OWASP/Python/jsonschema/Pydantic/Tenacity/LangChain security references;
- Python 3.10/3.12 compatibility + runnable-example CI.

Stages 08–11 currently contain roadmap scaffolds and will be implemented progressively.

---

# Framework learning strategy

Frameworks/tools are introduced **after** the underlying mechanism or protocol problem is visible.

```text
Python while-loop Agent
    -> explicit state machine
    -> handwritten TinyStateGraph
    -> LangGraph
```

```text
chunk / vector / cosine from first principles
    -> brute-force Retriever
    -> FAISS
    -> Qdrant
    -> LangChain Retriever
    -> Agentic RAG
```

```text
hard-coded local ToolRegistry
    -> MCP roles/primitives/wire shape
    -> MCP Python SDK v2
    -> stdio / Streamable HTTP
    -> Tiny-Agent MCP bridge
```

```text
thread state -> Checkpointer -> SQLite/PostgreSQL
memory candidate -> write policy -> Store
risky action -> interrupt -> approve/edit/reject -> validate + authorize
```

```text
raw Tool invocation
    -> typed safe failures
    -> local validation
    -> handwritten retry/budget/permission mechanisms
    -> jsonschema / Pydantic / Tenacity comparison
    -> GuardedToolExecutor
    -> LangChain middleware/guardrails comparison
```

```text
print trajectory
    -> structured trace/event model
    -> LangSmith / OpenTelemetry
```

This prevents the project from becoming a collection of framework API recipes.

---

# Quick start

Clone the repository and install the lightweight core development environment:

```bash
python -m pip install -e ".[dev]"
pytest -q
```

## Optional capability extras

```bash
# real OpenAI examples
python -m pip install -e ".[openai]"

# Stage 03 LangGraph / LangChain
python -m pip install -e ".[stage03]"

# Stage 04 vector backends
python -m pip install -e ".[stage04]"

# Stage 05 MCP v2
python -m pip install -e ".[stage05]"

# Stage 06 persistence / HITL
python -m pip install -e ".[dev,stage06]"

# Stage 07 reliability / safety comparisons
python -m pip install -e ".[dev,stage07]"
```

Follow the stage-specific learning orders rather than reading code directories alphabetically.

---

# Testing philosophy

Tiny-Agent separates deterministic correctness tests from optional framework/backend compatibility and live provider behavior.

```text
Core deterministic tests             Optional integration tests                      Live examples
------------------------             --------------------------                      -------------
Pure Python                          LangGraph / FAISS / Qdrant / MCP / Postgres      Real model/API
Fake models + policy tests           jsonschema / Tenacity / Pydantic                 API keys/network
No token cost                        Local/in-memory + real CI backends                Potential cost
Mechanism correctness                Library/protocol compatibility                   End-to-end behavior
```

Important failure boundaries include:

- loop/step/rewrite/tool/retry budgets;
- malformed provider responses and structured decisions;
- invalid graph routes/cycles and plan validation;
- model-safe error redaction;
- Tool JSON Schema validation;
- permission/default-deny behavior;
- exact-action approval binding;
- timeout/cancellation/retry semantics;
- prompt-injection trust-boundary handling;
- checkpoint/interrupt compatibility and durable recovery;
- retrieval misses and evidence-insufficiency abstention;
- MCP discovery/schema normalization and remote errors;
- memory-write denial and HITL edit/reject behavior;
- SQLite/PostgreSQL persistence.

---

# Repository structure

```text
Tiny-Agent/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── docs/
│   └── framework-and-tooling-map.md
├── .github/workflows/
│   └── tests.yml
├── stages/
│   ├── 00-foundations/
│   ├── 01-react-runtime/
│   ├── 02-planning-routing/
│   ├── 03-stateful-orchestration/
│   ├── 04-agentic-rag/
│   ├── 05-mcp/
│   ├── 06-memory-persistence-hitl/
│   ├── 07-reliability-safety/
│   ├── 08-evaluation-observability/
│   ├── 09-multi-agent/
│   ├── 10-production-deployment/
│   └── 11-capstone-enterprise-agent/
├── src/tiny_agent/
│   ├── approval.py
│   ├── decision.py
│   ├── governance.py
│   ├── guarded_runtime.py
│   ├── memory_policy.py
│   ├── reliability.py
│   ├── runtime.py
│   ├── state_graph.py
│   ├── langgraph_runtime.py
│   ├── retrieval.py
│   ├── rag.py
│   ├── mcp_bridge.py
│   ├── trust.py
│   ├── validation.py
│   ├── validators/
│   ├── retrievers/
│   ├── tool.py
│   ├── types.py
│   ├── workflows.py
│   └── models/
├── tests/
└── pyproject.toml
```

---

# License

Tiny-Agent is open-source software released under the **MIT License**.

Copyright (c) 2026 wds1996.

See [`LICENSE`](LICENSE) for the full license text.

---

# Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

Good contributions include clearer explanations, runnable examples, exercises/interview questions, deterministic tests, edge cases, bug fixes, diagrams, adapters, governance policies, and evaluation cases.

When adding a capability, update both its educational stage under `stages/` and `src/tiny_agent/` when the capability belongs in the reusable implementation.

---

# References and versioning

Primary references are maintained in the relevant stage documentation. Framework, database, security, and protocol APIs evolve quickly, so examples should be checked against current official documentation whenever dependencies are updated.

Current optional dependency policy targets stable major-version ranges:

```text
Stage 03
langgraph >= 1.2, < 2
langchain >= 1.3, < 2

Stage 04
faiss-cpu >= 1.9, < 2
qdrant-client >= 1.14, < 2
langchain >= 1.3, < 2
numpy >= 1.26

Stage 05
mcp[cli] >= 2, < 3
protocol teaching target: MCP 2026-07-28

Stage 06
langgraph >= 1.2, < 2
langgraph-checkpoint-sqlite >= 3.1, < 4
langgraph-checkpoint-postgres >= 3.1, < 4
psycopg[binary,pool] >= 3.3, < 4

Stage 07
jsonschema >= 4.25, < 5
tenacity >= 9, < 10
pydantic >= 2.11, < 3
security reference baseline: OWASP Top 10 for LLM Applications 2025
```

---

Tiny-Agent grows in small, reviewable capability stages so that repository history remains useful as learning material rather than only as the final codebase.

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
    -> memory / HITL
    -> reliability / safety
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
5. **Model output is a proposal, not authority** — routes, plans, tool calls, retrieval queries, and actions remain subject to application validation and policy.
6. **Runtimes own execution** — LLMs can propose actions; application/runtime code governs execution, observations, budgets, stopping, and data access.
7. **State is explicit when orchestration demands it** — complex branching, persistence, interruption, and resumption should not be hidden in local variables.
8. **External evidence and remote capabilities are not authority** — retrieved documents, MCP metadata, remote prompts, and tool results retain explicit trust boundaries.
9. **Production concerns are part of Agent learning** — reliability, permissions, tracing, evaluation, cost, and deployment are not optional afterthoughts.
10. **Tests include failure boundaries** — malformed provider data, invalid routes, loop budgets, unsafe failures, retrieval misses, remote capability errors, and state-transition errors are first-class test cases.
11. **Tutorial simplifications are documented** — beginner code may be intentionally small, but its production limitations must be explicit.

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
| [06 — Memory / Persistence / HITL](stages/06-memory-persistence-hitl/) | session state, long-term memory, durable persistence, human approval | Pause/resume stateful Agents with deliberate memory policies |
| [07 — Reliability & Safety](stages/07-reliability-safety/) | validation, retry, timeout, budgets, permissions, injection defense | Build a guarded runtime that fails predictably |
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
- LangChain messages and tool abstractions;
- curated official/community learning resources;
- dedicated framework compatibility tests.

## ✅ Stage 04 — RAG & Agentic Retrieval

- RAG fundamentals and fixed two-step RAG;
- chunking, overlap, metadata, and provider-neutral embedding interfaces;
- deterministic offline `HashEmbeddingModel` for teaching/tests;
- cosine similarity and exact brute-force top-k retrieval;
- FAISS `IndexFlatIP` adapter with normalized-vector cosine ranking;
- Qdrant local-mode adapter with collections, payloads, and metadata filtering;
- LangChain `BaseRetriever` adapter;
- candidate retrieval vs reranking and hybrid-retrieval theory;
- bounded Agentic RAG retrieval decisions;
- controlled query rewriting and evidence-sufficiency checks;
- explicit insufficient-evidence abstention;
- retrieval metrics such as Recall@k and MRR;
- deterministic tests plus optional-backend compatibility tests.

## ✅ Stage 05 — MCP: Standardized Capabilities Across Boundaries

- Function Calling vs MCP boundary;
- Host / Client / Server mental model;
- MCP Tools, Resources, Prompts, and resource templates;
- conceptual JSON-RPC/wire-message walkthrough;
- explicit comparison of classic handshake-era MCP with the 2026-07-28 stateless core;
- current Python SDK v2 `MCPServer` and `Client` APIs;
- in-process client/server learning path;
- local stdio subprocess transport;
- Streamable HTTP service transport;
- backward-compatible async `Tool.ainvoke()` / `ToolRegistry.aexecute()` support;
- `MCPToolBridge` for converting discovered MCP Tools into Tiny-Agent Tools;
- host-owned namespaces for multi-server tool-name collisions;
- structured MCP tool results and explicit MCP tool errors;
- security/trust boundaries for remote tools, resources, prompts, credentials, and server metadata;
- curated current official MCP/Python-SDK references;
- dedicated MCP v2 compatibility tests.

Stages 06–11 currently contain roadmap scaffolds and will be implemented progressively.

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
    -> FAISS local index
    -> Qdrant vector database
    -> LangChain Retriever adapter
    -> Agentic RAG
```

```text
hard-coded local ToolRegistry
    -> inspect MCP roles/primitives/wire shape
    -> MCP Python SDK v2
    -> stdio / Streamable HTTP
    -> Tiny-Agent MCP bridge
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

## OpenAI examples

```bash
python -m pip install -e ".[openai]"
export OPENAI_API_KEY="your-key"
```

## Stage 03 LangGraph / LangChain examples

```bash
python -m pip install -e ".[stage03]"
```

## Stage 04 FAISS / Qdrant / LangChain retrieval examples

```bash
python -m pip install -e ".[stage04]"
```

## Stage 05 MCP v2 examples

```bash
python -m pip install -e ".[stage05]"
```

For Stage 05 tests:

```bash
python -m pip install -e ".[dev,stage05]"
pytest -q tests/test_stage05_mcp.py
```

Follow the stage-specific learning orders rather than reading code directories alphabetically.

---

# Testing philosophy

Tiny-Agent separates deterministic correctness tests from optional framework/backend compatibility and live provider behavior.

```text
Core deterministic tests          Optional integration tests                 Live examples
------------------------          --------------------------                 -------------
Pure Python                       LangGraph / FAISS / Qdrant / MCP SDK       Real model/API
Fake models                       Local/in-memory framework backends          API keys/network
No token cost                     No model token cost                         Potential cost
Mechanism correctness             Library/protocol compatibility             End-to-end behavior
```

Important failure boundaries are tested explicitly:

- loop/step/rewrite budgets;
- malformed provider responses;
- invalid structured decisions;
- invalid graph routes/cycles;
- plan validation;
- safe failure propagation;
- checkpoint/interrupt compatibility;
- invalid embedding dimensions;
- metadata filtering behavior;
- evidence-insufficiency abstention;
- sync/async Tool misuse;
- MCP discovery/schema normalization;
- namespaced remote Tool execution;
- MCP tool-level errors.

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
│
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
│
├── src/tiny_agent/
│   ├── decision.py
│   ├── runtime.py
│   ├── state_graph.py
│   ├── langgraph_runtime.py
│   ├── retrieval.py
│   ├── rag.py
│   ├── mcp_bridge.py
│   ├── retrievers/
│   │   ├── faiss.py
│   │   ├── qdrant.py
│   │   └── langchain_adapter.py
│   ├── tool.py
│   ├── types.py
│   ├── workflows.py
│   └── models/
│
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

Good contributions include:

- clearer explanations;
- runnable examples;
- exercises/interview questions;
- deterministic tests and edge cases;
- bug fixes;
- diagrams;
- provider/framework/retriever/protocol adapters;
- evaluation cases;
- documentation improvements.

When adding a capability, update both:

1. its educational stage under `stages/`; and
2. `src/tiny_agent/` when the capability belongs in the reusable implementation.

---

# References and versioning

Primary references are maintained in the relevant stage documentation.

Framework, database, and protocol APIs evolve quickly. Tiny-Agent examples should be checked against current official documentation whenever dependencies are updated.

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
```

---

Tiny-Agent grows in small, reviewable capability stages so that the repository history remains useful as learning material rather than only as the final codebase.

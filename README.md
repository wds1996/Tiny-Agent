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
    -> RAG / vector databases
    -> MCP
    -> memory / HITL
    -> reliability / safety
    -> evaluation / observability
    -> multi-Agent
    -> production deployment
```

The goal is not only to make examples run. The goal is to understand **why each abstraction exists, what responsibility it owns, where it fails, and how it maps to maintainable software**.

---

# Core philosophy

1. **Mechanism before framework** — build the minimum mechanism first, then introduce the mature framework that solves the same problem.
2. **Theory and code stay together** — each capability stage contains conceptual notes, runnable examples, tests, and exercises where applicable.
3. **Educational snapshots are preserved** — later framework code does not erase earlier handwritten implementations.
4. **Deterministic when possible, agentic when useful** — autonomy is added only where uncertainty justifies it.
5. **Model output is a proposal, not authority** — routes, plans, tool calls, and actions remain subject to application validation and policy.
6. **Runtimes own execution** — LLMs can propose actions; application/runtime code governs execution, observations, budgets, and stopping.
7. **State is explicit when orchestration demands it** — complex branching, persistence, interruption, and resumption should not be hidden in local variables.
8. **Production concerns are part of Agent learning** — reliability, permissions, tracing, evaluation, cost, and deployment are not optional afterthoughts.
9. **Tests include failure boundaries** — malformed provider data, invalid routes, loop budgets, unsafe failures, and state-transition errors are first-class test cases.
10. **Tutorial simplifications are documented** — beginner code may be intentionally small, but its production limitations must be explicit.

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
├── README.md        # learning order, goals, milestone
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
| [04 — Agentic RAG](stages/04-agentic-rag/) | Chunking, embeddings, FAISS, Qdrant, retrieval/reranking | Build evidence-grounded Agentic retrieval |
| [05 — MCP](stages/05-mcp/) | MCP host/client/server, tools/resources/prompts | Build and consume a custom MCP server |
| [06 — Memory / Persistence / HITL](stages/06-memory-persistence-hitl/) | session state, long-term memory, durable persistence, human approval | Pause/resume stateful Agents with deliberate memory policies |
| [07 — Reliability & Safety](stages/07-reliability-safety/) | validation, retry, timeout, budgets, permissions, injection defense | Build a guarded runtime that fails predictably |
| [08 — Evaluation & Observability](stages/08-evaluation-observability/) | traces, trajectory eval, quality/cost/latency metrics | Measure whether Agent behavior actually works |
| [09 — Multi-Agent](stages/09-multi-agent/) | delegation, handoffs, specialists, interoperability | Justify when multiple Agents beat one Agent/workflow |
| [10 — Production Deployment](stages/10-production-deployment/) | FastAPI, async, PostgreSQL, Redis, Docker, CI | Turn Tiny-Agent into a deployable service |
| [11 — Enterprise Capstone](stages/11-capstone-enterprise-agent/) | integrated research/knowledge Agent | Combine the learning path into a portfolio-quality system |

For the framework/infrastructure mapping, see:

**[Framework & Tooling Map](docs/framework-and-tooling-map.md)**

This explains where LangChain, LangGraph, FAISS, Qdrant, MCP, LangSmith, FastAPI, PostgreSQL, Redis, Docker, and related tools enter the curriculum.

---

# Current implemented stages

## ✅ Stage 00 — LLM & Tool-Use Foundations

Available now:

- message-based LLM interaction;
- provider boundary;
- Structured Output / JSON Schema;
- Function Calling;
- minimal repeated tool loop;
- framework-free runnable example;
- review questions.

## ✅ Stage 01 — ReAct & Core Agent Runtime

Available now:

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

Available now:

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

Available in the current Stage 03 implementation:

- explicit state and state-machine theory;
- handwritten `TinyStateGraph`;
- nodes, edges, conditional edges, cycles, START/END;
- LangGraph `StateGraph` fundamentals;
- LangGraph rebuild of the Stage 01 ReAct loop;
- graph version of Stage 02 Planner–Executor recovery;
- `stream()` state updates;
- checkpointing with `InMemorySaver` for teaching/testing;
- `interrupt()` / `Command(resume=...)` fundamentals;
- LangChain messages and tool abstractions;
- LangChain vs LangGraph comparison;
- dedicated framework compatibility tests.

Stages 04–11 currently contain roadmap scaffolds and will be implemented progressively.

---

# Framework learning strategy

Frameworks are introduced **after** the underlying mechanism.

Examples:

```text
Python while-loop Agent
    -> explicit state machine
    -> handwritten TinyStateGraph
    -> LangGraph
```

```text
raw embeddings / similarity
    -> FAISS local index
    -> Qdrant vector database
    -> LangChain retriever integrations
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
pip install -e ".[dev]"
pytest -q
```

## OpenAI examples

```bash
pip install -e ".[openai]"
export OPENAI_API_KEY="your-key"
```

## Stage 03 LangGraph / LangChain examples

```bash
pip install -e ".[stage03]"
```

For framework tests as well:

```bash
pip install -e ".[dev,stage03]"
```

Then follow the learning order in:

[`stages/03-stateful-orchestration/README.md`](stages/03-stateful-orchestration/README.md)

---

# Testing philosophy

Tiny-Agent separates deterministic correctness tests from live provider behavior.

```text
Unit / framework compatibility tests     Live integration examples
------------------------------------     -------------------------
Fake models                              Real model
Fake provider clients                    Real API key
Deterministic                            Potentially nondeterministic
Fast / usually no token cost             Network + token cost
Control/protocol correctness             End-to-end behavior
```

The CI suite also keeps optional framework tests separate from core tests so Stage 00 learners do not need the complete framework stack installed.

Important failure boundaries are tested explicitly:

- loop/step budgets;
- malformed provider responses;
- invalid structured decisions;
- invalid graph routes;
- graph cycles;
- plan validation;
- safe failure propagation;
- checkpoint/interrupt compatibility.

---

# Repository structure

```text
Tiny-Agent/
├── README.md
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
│   ├── tool.py
│   ├── types.py
│   ├── workflows.py
│   └── models/
│
├── tests/
└── pyproject.toml
```

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
- provider/framework adapters;
- evaluation cases;
- documentation improvements.

When adding a capability, update both:

1. its educational stage under `stages/`; and
2. `src/tiny_agent/` when the capability belongs in the reusable implementation.

---

# References and versioning

Primary references are maintained in the relevant stage documentation.

Framework APIs evolve quickly. Tiny-Agent examples should be checked against current official documentation whenever dependencies are updated.

Current Stage 03 dependency policy targets stable major versions:

```text
langgraph >= 1.2, < 2
langchain >= 1.3, < 2
```

---

Tiny-Agent grows in small, reviewable capability stages so that the repository history remains useful as learning material rather than only as the final codebase.

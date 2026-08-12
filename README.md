# Tiny-Agent

> Learn AI Agents by building one from first principles to production.

Tiny-Agent is an open-source, learning-first Agent engineering project for **anyone who wants to understand how modern AI Agents actually work**.

This repository does not begin with a large framework or a black-box `create_agent(...)` call. Instead, it builds the Agent stack layer by layer: LLM interfaces, structured outputs, function calling, ReAct and Agent runtimes, model-provider adapters, planning, stateful orchestration, RAG, MCP, memory, human approval, reliability, evaluation, observability, multi-Agent systems, and production deployment.

The goal is not only to teach concepts, but also to show how those concepts become maintainable software.

## Who is this project for?

Tiny-Agent is designed for:

- students learning LLM Agents from scratch;
- engineers who know LLM APIs or function calling but want to understand Agent runtimes;
- internship/job candidates who need production-oriented Agent engineering experience;
- developers who want a small, inspectable reference implementation before learning larger frameworks;
- contributors who want to improve an open-source Agent learning path together.

## Core philosophy

1. **Mechanism before framework** — understand loops, state, tools, protocols, and control flow before using high-level abstractions.
2. **Theory and code stay together** — every stage keeps conceptual notes, runnable examples, and exercises close to each other.
3. **Each stage is independently readable** — later code must not erase earlier learning material.
4. **Production concerns are part of Agent learning** — reliability, permissions, tracing, evals, deployment, and cost are not optional afterthoughts.
5. **LLMs propose actions; runtimes execute actions** — model decisions are separated from auditable execution.
6. **Deterministic when possible, agentic when useful** — not every workflow needs an autonomous Agent.
7. **Provider APIs stay behind adapters** — the core runtime should not become a collection of vendor-specific request objects.
8. **Tests are part of the tutorial** — a serious Agent project must teach how to test runtime behavior without paying for a live model call every time.

---

# Learning Path

The repository is organized by **capability stages**, not by calendar days. Learn at your own pace.

## Stage 00 — LLM & Tool-Use Foundations

📁 [`stages/00-foundations/`](stages/00-foundations/)

**Goal:** understand the minimum building blocks that exist before an Agent runtime.

Topics:

- LLM message-based interaction;
- model/provider boundary;
- structured output and JSON Schema;
- function/tool calling;
- tool schema vs real executable function;
- model-generated tool call vs runtime execution;
- returning tool observations to the model;
- the minimal multi-turn tool loop;
- common tool-calling failure modes.

Key materials:

- [`LLM APIs and Messages`](stages/00-foundations/theory/01-llm-api-and-messages.md)
- [`Structured Output`](stages/00-foundations/theory/02-structured-output.md)
- [`Function Calling`](stages/00-foundations/theory/03-function-calling.md)
- [`Minimal Tool Loop`](stages/00-foundations/code/minimal_tool_loop.py)
- [`Foundation Review Questions`](stages/00-foundations/exercises/review-questions.md)

**Milestone:** you can explain why function calling itself is not yet a complete Agent and implement a minimal tool-use loop without an Agent framework.

---

## Stage 01 — ReAct & Core Agent Runtime

📁 [`stages/01-react-runtime/`](stages/01-react-runtime/)

**Goal:** turn tool calling into a real iterative Agent runtime, then connect that runtime to a real model provider without coupling the runtime to the provider SDK.

Topics:

- ReAct: Reason / Act / Observe;
- action-observation feedback loops;
- Agent stopping conditions;
- provider-neutral model interfaces;
- normalized model responses;
- Tool and ToolRegistry abstractions;
- tool errors as observations;
- maximum-step protection;
- model provider adapters;
- Responses API function-call protocol;
- `call_id` correlation;
- strict tool schemas;
- serial tool dependencies;
- multiple tool calls in one model turn;
- deterministic unit testing with fake models and fake provider clients;
- real multi-tool Agent execution.

Key theory:

- [`ReAct and the Agent Loop`](stages/01-react-runtime/theory/01-react-and-agent-loop.md)
- [`Runtime Architecture`](stages/01-react-runtime/theory/02-runtime-architecture.md)
- [`Model Provider Adapters`](stages/01-react-runtime/theory/03-model-provider-adapter.md)

Educational code:

- [`Minimal ReAct Runtime`](stages/01-react-runtime/code/minimal_react_runtime.py)
- [`OpenAI Multi-Tool Agent`](stages/01-react-runtime/code/openai_multi_tool_agent.py)

Exercises:

- [`ReAct Runtime Review Questions`](stages/01-react-runtime/exercises/review-questions.md)
- [`Provider Adapter Exercises`](stages/01-react-runtime/exercises/provider-adapter-exercises.md)

Current evolving implementation:

- [`src/tiny_agent/runtime.py`](src/tiny_agent/runtime.py)
- [`src/tiny_agent/tool.py`](src/tiny_agent/tool.py)
- [`src/tiny_agent/types.py`](src/tiny_agent/types.py)
- [`src/tiny_agent/models/openai.py`](src/tiny_agent/models/openai.py)

Tests:

- [`tests/test_runtime.py`](tests/test_runtime.py)
- [`tests/test_openai_adapter.py`](tests/test_openai_adapter.py)
- [`.github/workflows/tests.yml`](.github/workflows/tests.yml)

**Milestone:** you can implement and explain a framework-free Agent loop, connect it to a real model through an adapter, preserve tool-call correlation, and test both runtime and provider translation without a live API call.

---

## Stage 02 — Planning, Routing & Deterministic Workflows

📁 [`stages/02-planning-routing/`](stages/02-planning-routing/)

**Goal:** learn when to use dynamic Agent decisions and when to use explicit workflows.

Planned topics:

- task decomposition;
- ReAct vs Plan-and-Execute;
- router patterns;
- planner/executor separation;
- deterministic workflow vs autonomous Agent;
- replanning;
- step budgets and plan validation.

**Milestone:** build a small research workflow that can route, plan, execute, and re-plan without turning every step into an LLM decision.

---

## Stage 03 — Stateful Orchestration

📁 [`stages/03-stateful-orchestration/`](stages/03-stateful-orchestration/)

**Goal:** move from a simple `while` loop to explicit graph/state-based orchestration and provider-aware conversation state.

Planned topics:

- state machines for Agents;
- nodes, edges, and conditional transitions;
- explicit Agent state;
- provider-native conversation state;
- transcript replay vs response chaining;
- preserving reasoning/output items where required;
- LangGraph fundamentals;
- persistence-ready execution;
- streaming state updates;
- comparing a handwritten runtime with framework orchestration.

**Milestone:** rebuild the Agent workflow as an explicit state graph and understand what stateful orchestration adds over the handwritten runtime.

---

## Stage 04 — RAG & Agentic Retrieval

📁 [`stages/04-agentic-rag/`](stages/04-agentic-rag/)

**Goal:** give Agents access to external knowledge and let them decide when and how to retrieve it.

Planned topics:

- document parsing and chunking;
- embeddings and vector retrieval;
- metadata filters;
- reranking and hybrid retrieval;
- ordinary RAG vs Agentic RAG;
- query rewriting;
- retrieval routing;
- evidence-aware answering;
- retrieval evaluation.

**Milestone:** build an Agent that can decide whether retrieval is necessary, refine failed searches, and answer from evidence.

---

## Stage 05 — MCP: Standardized Tools & Context

📁 [`stages/05-mcp/`](stages/05-mcp/)

**Goal:** understand and implement the Model Context Protocol instead of treating MCP as a magic connector.

Planned topics:

- MCP host / client / server;
- tools, resources, and prompts;
- local vs remote MCP servers;
- exposing custom tools through MCP;
- consuming MCP tools from an Agent;
- schema discovery;
- trust boundaries and permission concerns.

**Milestone:** implement a custom MCP server and connect it to Tiny-Agent.

---

## Stage 06 — Memory, Persistence & Human-in-the-Loop

📁 [`stages/06-memory-persistence-hitl/`](stages/06-memory-persistence-hitl/)

**Goal:** make Agents stateful across steps, interruptions, and sessions.

Planned topics:

- context vs short-term memory vs long-term memory;
- session state;
- checkpointing;
- resume/replay;
- long-term user/task memory;
- memory retrieval policies;
- human approval gates;
- approve / edit / reject flows.

**Milestone:** build an Agent that can pause before risky actions, persist state, and resume later.

---

## Stage 07 — Reliability, Safety & Tool Governance

📁 [`stages/07-reliability-safety/`](stages/07-reliability-safety/)

**Goal:** make Agent execution controlled rather than merely impressive in demos.

Planned topics:

- invalid tool arguments;
- retries and retryable errors;
- timeout and cancellation;
- fallback tools/models;
- max steps / max tool calls / token budgets;
- loop detection;
- permission models;
- tool allowlists;
- prompt injection and indirect prompt injection;
- sandboxing concepts;
- audit logs.

**Milestone:** build a guarded runtime that fails predictably and does not grant the model unrestricted execution power.

---

## Stage 08 — Evaluation & Observability

📁 [`stages/08-evaluation-observability/`](stages/08-evaluation-observability/)

**Goal:** answer the production question: *How do we know the Agent actually works?*

Planned topics:

- traces and spans;
- tool-call trajectories;
- task-success evaluation;
- tool-selection accuracy;
- argument accuracy;
- retrieval metrics;
- trajectory evaluation;
- latency, tokens, and cost;
- offline vs online evaluation;
- deterministic graders and LLM-as-judge;
- regression test sets.

**Milestone:** create an evaluation suite and trace every important Agent decision and tool execution.

---

## Stage 09 — Multi-Agent Systems & Agent Interoperability

📁 [`stages/09-multi-agent/`](stages/09-multi-agent/)

**Goal:** learn multi-Agent patterns only after mastering single-Agent orchestration.

Planned topics:

- when multiple Agents are justified;
- supervisor / worker;
- handoffs;
- specialist Agents;
- shared vs isolated context;
- coordination failure modes;
- A2A concepts;
- comparing multi-Agent designs with simpler workflows.

**Milestone:** build a small specialist team and justify why multiple Agents are better than one Agent or a deterministic pipeline for the chosen task.

---

## Stage 10 — Production Service & Deployment

📁 [`stages/10-production-deployment/`](stages/10-production-deployment/)

**Goal:** turn an Agent prototype into a deployable service.

Planned topics:

- FastAPI service boundaries;
- async execution;
- streaming responses;
- task/session APIs;
- PostgreSQL / Redis roles;
- configuration and secrets;
- Docker and Docker Compose;
- CI and integration tests;
- structured logging;
- basic monitoring;
- concurrency, rate limits, latency, and cost.

**Milestone:** run Tiny-Agent as a containerized service with tests and reproducible configuration.

---

## Stage 11 — Capstone: Enterprise Research & Knowledge Agent

📁 [`stages/11-capstone-enterprise-agent/`](stages/11-capstone-enterprise-agent/)

**Goal:** combine the entire learning path into one portfolio-quality open-source Agent application.

Target capabilities:

- task routing and planning;
- web/document/database tools;
- Agentic RAG;
- MCP integrations;
- short- and long-term memory;
- persistence and resumability;
- human approval for risky operations;
- retry/fallback policies;
- traces and evaluation suite;
- FastAPI + Docker deployment;
- clear architecture documentation.

**Milestone:** a complete, inspectable Agent system suitable both as a learning reference and as a serious engineering portfolio project.

---

# Repository Structure

```text
Tiny-Agent/
├── README.md
├── CONTRIBUTING.md
├── .github/workflows/               # Continuous integration
│   └── tests.yml
│
├── stages/                          # Stable educational snapshots
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
├── src/tiny_agent/                  # Latest evolving Tiny-Agent runtime
│   ├── runtime.py
│   ├── tool.py
│   ├── types.py
│   └── models/                      # Provider adapters
│
├── tests/                           # Tests for the latest implementation
└── pyproject.toml
```

Each stage follows this convention whenever applicable:

```text
stage-name/
├── README.md        # goals, prerequisites, learning order, deliverables
├── theory/          # detailed conceptual notes in Markdown
├── code/            # stage-specific runnable implementation snapshots
└── exercises/       # exercises and interview-style questions
```

A theory-only stage is still kept as a full stage directory with Markdown material. We do not remove a stage simply because it has little or no executable code.

# Two ways to use Tiny-Agent

### 1. Learn progressively

Follow `stages/00-foundations` → `stages/01-react-runtime` → ... in order. Each stage preserves the simplest implementation that teaches that concept.

### 2. Read or contribute to the latest runtime

Use [`src/tiny_agent/`](src/tiny_agent/) to inspect the latest integrated implementation. This code evolves as later stages are completed.

# Testing philosophy

Tiny-Agent separates:

```text
Unit tests                         Live integration tests
----------                         ----------------------
Fake model                         Real model
Fake provider client               Real API key
Deterministic                      Potentially nondeterministic
Fast / no token cost               Network + token cost
Runtime/protocol correctness       End-to-end provider behavior
```

Basic unit tests run in GitHub Actions on pull requests. Live provider examples are kept explicit so contributors are not required to spend API credits to run the core test suite.

# Current Status

- ✅ Stage 00 — foundation theory and minimal tool loop are available.
- 🚧 Stage 01 — ReAct runtime, provider-neutral core, OpenAI Responses adapter, tests, and real multi-tool example are the current implementation milestone.
- 📝 Stages 02–11 — learning objectives and scaffolds are defined and will be implemented progressively.

# Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

Tiny-Agent is intended to become a community learning project. Contributions are welcome in areas such as:

- clearer explanations;
- additional runnable examples;
- exercises and interview questions;
- tests;
- bug fixes;
- diagrams;
- provider adapters;
- evaluation cases;
- translations;
- documentation improvements.

When adding a new capability, prefer updating both:

1. the corresponding educational stage under `stages/`; and
2. the latest implementation under `src/tiny_agent/` when the capability belongs in the runtime.

# References

Primary references are maintained inside the relevant stages so learners can understand *why* each technique exists rather than only copying APIs.

Current Stage 01 references include:

- ReAct: *Synergizing Reasoning and Acting in Language Models*, ICLR 2023.
- OpenAI Function Calling documentation.
- OpenAI Responses API / model documentation.
- OpenAI Python SDK.

---

Tiny-Agent is under active development. The project intentionally grows in small, reviewable steps so that its implementation history remains useful as learning material.

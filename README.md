# Tiny-Agent

> Learn AI Agents by building one from first principles to production.

Tiny-Agent is an open-source, learning-first Agent engineering project for **anyone who wants to understand how modern AI Agents actually work**.

This repository does not begin with a large framework or a black-box `create_agent(...)` call. Instead, it builds the Agent stack layer by layer: LLM interfaces, structured outputs, function calling, ReAct and Agent runtimes, model-provider adapters, workflow design, routing, planning, stateful orchestration, RAG, MCP, memory, human approval, reliability, evaluation, observability, multi-Agent systems, and production deployment.

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
9. **Model output is a proposal, not authority** — routes, plans, and tool calls remain subject to application validation, policy, budgets, and permissions.
10. **Early simplifications must be explicit** — tutorial code can be intentionally small, but its production limitations should be documented rather than hidden.

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

**Goal:** turn tool calling into a real iterative Agent runtime, connect it to a real model provider without coupling the runtime to the provider SDK, and understand where the minimal teaching runtime stops being production-ready.

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
- multiple calls vs physical concurrent execution;
- deterministic unit testing with fake models and fake provider clients;
- real multi-tool Agent execution;
- explicit production limitations: validation, error redaction, retries, timeouts, permissions, state, tracing, and evaluation.

Key theory:

- [`ReAct and the Agent Loop`](stages/01-react-runtime/theory/01-react-and-agent-loop.md)
- [`Runtime Architecture`](stages/01-react-runtime/theory/02-runtime-architecture.md)
- [`Model Provider Adapters`](stages/01-react-runtime/theory/03-model-provider-adapter.md)
- [`Scope and Production Limitations`](stages/01-react-runtime/theory/04-scope-and-production-limitations.md)

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
- [`tests/test_runtime_edges.py`](tests/test_runtime_edges.py)
- [`tests/test_openai_adapter.py`](tests/test_openai_adapter.py)
- [`tests/test_openai_adapter_edges.py`](tests/test_openai_adapter_edges.py)
- [`.github/workflows/tests.yml`](.github/workflows/tests.yml)

**Milestone:** you can implement and explain a framework-free Agent loop, connect it to a real model through an adapter, preserve tool-call correlation, test runtime/protocol boundaries without a live API call, and explain which parts are deliberate teaching simplifications rather than production guarantees.

---

## Stage 02 — Planning, Routing & Deterministic Workflows

📁 [`stages/02-planning-routing/`](stages/02-planning-routing/)

**Goal:** learn how much autonomy a task actually needs, keep predictable control flow in software, and introduce model-driven routing/planning only where semantic judgment adds value.

Core questions:

- What is the real control-flow difference between a Workflow and an Agent?
- When is one LLM call enough?
- When should routing be a deterministic rule?
- When does semantic routing justify an LLM call?
- Why should a Router choose a destination but not own arbitrary dispatch?
- What does explicit planning add over local ReAct decisions?
- Why is a Plan a bounded proposal rather than ground truth?
- When should observations trigger replanning?
- Why must `max_plan_steps`, `max_total_steps`, and `max_replans` be application-owned budgets?
- How can a Stage 01 ReAct Agent become a scoped Executor inside a larger workflow?

Key theory:

- [`Agent vs Workflow`](stages/02-planning-routing/theory/01-agent-vs-workflow.md)
- [`Routing Patterns`](stages/02-planning-routing/theory/02-routing-patterns.md)
- [`Planning and Replanning`](stages/02-planning-routing/theory/03-planning-and-replanning.md)
- [`Planner–Executor`](stages/02-planning-routing/theory/04-planner-executor.md)

Educational code:

- [`Deterministic Router`](stages/02-planning-routing/code/deterministic_router.py) — no API key required
- [`OpenAI Semantic Router`](stages/02-planning-routing/code/openai_router.py) — schema-constrained route selection
- [`Planner + ReAct Executor`](stages/02-planning-routing/code/planner_executor_agent.py) — Stage 02 orchestration composed with the Stage 01 runtime
- [`Bounded Replanning`](stages/02-planning-routing/code/bounded_replanning.py) — deterministic failure/recovery example, no API key required

Current evolving implementation:

- [`src/tiny_agent/decision.py`](src/tiny_agent/decision.py) — provider-neutral structured control decisions
- [`src/tiny_agent/models/openai_structured.py`](src/tiny_agent/models/openai_structured.py) — Responses API JSON-Schema decisions
- [`src/tiny_agent/workflows.py`](src/tiny_agent/workflows.py) — rule routing, LLM routing, planner, replanner, and bounded workflow execution

Tests:

- [`tests/test_structured_decision.py`](tests/test_structured_decision.py)
- [`tests/test_workflows.py`](tests/test_workflows.py)
- [`tests/test_workflow_budgets.py`](tests/test_workflow_budgets.py)
- [`tests/test_workflow_safety.py`](tests/test_workflow_safety.py)

Exercises:

- [`Stage 02 Review Questions and Coding Exercises`](stages/02-planning-routing/exercises/review-questions.md)

The central architecture principle is:

```text
model proposes route / plan / next action
            |
            v
application validates and governs
            |
            v
explicit workflow executes
```

**Milestone:** you can choose between deterministic workflow, routing, Planner–Executor, bounded replanning, and a ReAct Agent based on task uncertainty rather than architectural fashion. You can also build a structured Planner whose local Executor is itself a Stage 01 Agent.

---

## Stage 03 — Stateful Orchestration

📁 [`stages/03-stateful-orchestration/`](stages/03-stateful-orchestration/)

**Goal:** move from simple Python loops to explicit graph/state-based orchestration and provider-aware conversation state.

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
- comparing handwritten orchestration with framework orchestration.

**Milestone:** rebuild existing Tiny-Agent patterns as explicit state graphs and understand what the framework adds over ordinary Python control flow.

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

- local tool argument validation;
- error classification and safe model-facing failures;
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
- routing accuracy;
- plan quality and unnecessary-step analysis;
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
- concurrent tool execution;
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
├── src/tiny_agent/                  # Latest evolving Tiny-Agent implementation
│   ├── decision.py                  # Structured routing/planning decisions
│   ├── runtime.py                   # ReAct Agent loop
│   ├── tool.py
│   ├── types.py
│   ├── workflows.py                 # Routing and Planner–Executor workflows
│   └── models/                      # Provider adapters
│       ├── openai.py
│       └── openai_structured.py
│
├── tests/                           # Deterministic unit tests
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

Follow `stages/00-foundations` → `stages/01-react-runtime` → `stages/02-planning-routing` → ... in order. Each stage preserves the simplest implementation that teaches that concept.

### 2. Read or contribute to the latest implementation

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

The unit suite increasingly tests **failure boundaries**, not only successful demos: stopping budgets, malformed provider data, plan validation, safe failure propagation, and invalid control decisions are treated as first-class learning material.

# Current Status

- ✅ Stage 00 — LLM/tool-use foundations and minimal tool loop.
- ✅ Stage 01 — ReAct runtime, provider-neutral core, OpenAI Responses adapter, edge-case tests, real multi-tool example, and explicit production-limitations chapter.
- 🚧 Stage 02 — workflow vs Agent, deterministic/LLM routing, structured planning, Planner–Executor, bounded replanning, tests, and runnable examples are under active review.
- 📝 Stages 03–11 — learning objectives and scaffolds are defined and will be implemented progressively.

# Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

Tiny-Agent is intended to become a community learning project. Contributions are welcome in areas such as:

- clearer explanations;
- additional runnable examples;
- exercises and interview questions;
- tests and edge cases;
- bug fixes;
- diagrams;
- provider adapters;
- evaluation cases;
- translations;
- documentation improvements.

When adding a new capability, prefer updating both:

1. the corresponding educational stage under `stages/`; and
2. the latest implementation under `src/tiny_agent/` when the capability belongs in the reusable runtime/orchestration layer.

# References

Primary references are maintained inside the relevant stages so learners can understand *why* each technique exists rather than only copying APIs.

Current reference families include:

- ReAct: *Synergizing Reasoning and Acting in Language Models*, ICLR 2023.
- OpenAI Function Calling, Responses API, Structured Outputs, and current model documentation.
- Anthropic, *Building Effective Agents*.
- LangGraph workflow/agent documentation.
- LLM-Agent planning research and surveys where relevant.

---

Tiny-Agent is under active development. The project intentionally grows in small, reviewable steps so that its implementation history remains useful as learning material.

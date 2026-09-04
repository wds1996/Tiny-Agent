# Tiny-Agent Test Guide

> Language: English | [简体中文](README.zh-CN.md)

The `tests/` directory is not an appendix full of mysterious `pytest` files. In Tiny-Agent, tests are **executable specifications for the mechanisms taught by the course**.

The intended reading loop is:

```text
Stage theory
    -> explains the invariant

src/tiny_agent/
    -> implements the invariant

tests/test_*.py
    -> turns the invariant into deterministic examples and counterexamples
```

A test therefore answers a different question from a tutorial example:

- a `stages/.../code/*.py` example asks **"how does this mechanism work?"**;
- a `tests/test_*.py` file asks **"what must remain true, including at the edges?"**.

When you read a test, focus on the assertion and on the deliberately bad input. The important lesson is usually not the `pytest` syntax; it is the contract that the assertion protects.

---

## 1. How to read the test suite

A useful order for one mechanism is:

1. read the Stage README and relevant theory chapter;
2. run the small teaching example under that Stage;
3. inspect the corresponding implementation under `src/tiny_agent/`;
4. read the tests in this guide;
5. deliberately break one invariant and watch the test fail;
6. restore the invariant and explain *why* the test passes again.

For example, Stage 01 teaches:

```text
model proposes ToolCall
    -> runtime executes Tool
    -> Tool observation returns to model
    -> model continues or stops
```

[`test_runtime.py`](test_runtime.py) makes that diagram executable. [`test_runtime_edges.py`](test_runtime_edges.py) then asks what happens if the model loops forever, a Tool fails, or the model returns no valid next action.

### Test categories used below

| Label | Meaning |
|---|---|
| **Core** | Deterministic Tiny-Agent mechanism test; normally no network or external service. |
| **Framework** | Verifies mapping to a real framework/protocol such as LangGraph, Qdrant, MCP, OpenTelemetry, OpenAI Agents SDK, or A2A. |
| **Service** | Integration test that can require Postgres, Redis, FastAPI, or another service boundary. |
| **Cross-stage** | Protects an earlier mechanism after a later Stage adds stronger safety/production semantics. |

A framework test is still normally offline unless this guide explicitly says that an environment variable/service is required.

---

## 2. Running tests without losing the learning signal

Install the lightweight development dependencies first:

```bash
python -m pip install -e ".[dev]"
```

Run one file while studying one mechanism:

```bash
pytest -q tests/test_runtime.py
```

Run one exact behavior:

```bash
pytest -q \
  tests/test_runtime.py::test_agent_executes_tool_then_finishes
```

Select a concept by name:

```bash
pytest -q tests/test_guarded_runtime.py -k retry
```

Framework-heavy Stages use the extras listed in the root README, for example:

```bash
python -m pip install -e ".[dev,stage03]"
pytest -q tests/test_langgraph_runtime.py tests/test_stage03_frameworks.py

python -m pip install -e ".[dev,stage09]"
pytest -q tests/test_validation.py tests/test_reliability.py \
  tests/test_governance.py tests/test_guarded_runtime.py \
  tests/test_stage09_integrations.py
```

Tests that really need external infrastructure are intentionally explicit:

```bash
TEST_POSTGRES_URI='postgresql://...' \
pytest -q tests/test_stage06_postgres.py

TEST_REDIS_URL='redis://...' \
TEST_POSTGRES_URI='postgresql://...' \
pytest -q tests/test_stage13_integrations.py
```

Do not put real production credentials in commands, fixtures, test output, or committed files.

---

# 3. Stage-by-stage test map

## Stage 01 — ReAct Runtime and provider boundary

Read with the consolidated [Stage 01 chapter](../stages/01-react-runtime/README.md), which teaches the ReAct loop, Runtime architecture, Tool boundaries, deterministic testing, and the provider Adapter as one continuous lesson.

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_runtime.py`](test_runtime.py) | Core | A deterministic fake model proposes a ToolCall, the runtime executes the Tool, appends the Tool observation, calls the model again, and stops on the final answer. It also checks the message-role sequence. | This is the smallest executable specification of the Stage 01 ReAct loop. If it fails, the basic model/runtime/Tool boundary has changed. |
| [`test_runtime_edges.py`](test_runtime_edges.py) | Core | `max_steps` stopping, safe Tool-failure observations, and rejection of an empty model response with neither ToolCalls nor final answer. | Happy-path loops are easy; bounded stopping and failure semantics are what make the loop a runtime rather than a demo. |
| [`test_openai_adapter.py`](test_openai_adapter.py) | Framework, offline | Converts Tiny-Agent messages/Tool schemas into the OpenAI Responses API shape and normalizes provider `function_call` output back into Tiny-Agent `ToolCall`s, including multiple calls in one turn. Uses a fake client, not the network. | Proves that provider-specific wire format stays behind an adapter instead of leaking into the Agent loop. |
| [`test_openai_adapter_edges.py`](test_openai_adapter_edges.py) | Framework, offline | Direct final text, malformed JSON Tool arguments, non-object arguments, incidental text alongside ToolCalls, and unsupported internal roles. | Provider responses are external input. The adapter must reject malformed shapes instead of silently inventing semantics. |

## Stage 02 — Routing, structured decisions, planning, and budgets

Read with the consolidated [Stage 02](../stages/02-workflows-routing-planning/README.md). The chapter develops deterministic workflows, hybrid routing, structured planning, Planner/Executor separation, bounded replanning, and execution budgets as one continuous control-flow lesson.

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_workflows.py`](test_workflows.py) | Core | Rule routing before fallback, schema-constrained LLM routing, deterministic dispatch after a route decision, fixed-plan execution, failure-triggered replanning, and bounded replan behavior. | Shows that semantic decisions and ordinary control flow remain separate responsibilities. |
| [`test_structured_decision.py`](test_structured_decision.py) | Framework, offline | The OpenAI structured-decision adapter sends strict JSON Schema and accepts only an object-shaped decision; invalid JSON and arrays are rejected. | A router/Planner decision is application data, not free-form prose. |
| [`test_structured_decision_edges.py`](test_structured_decision_edges.py) | Framework, offline | Provider refusal and incomplete responses are represented as distinct outcomes instead of being confused with invalid JSON or a normal decision. | Production control logic needs to know *why* no valid decision exists. |
| [`test_workflow_budgets.py`](test_workflow_budgets.py) | Core | Maximum plan length, unique step IDs, and total execution-step budget. | A model-generated Plan is a proposal. The application validates and bounds it before/during execution. |

A later safety regression for these workflows is documented under **Cross-stage tests** below: [`test_workflow_safety.py`](test_workflow_safety.py).

## Stage 03 — Explicit state and LangGraph

Read with [Stage 03](../stages/03-stateful-orchestration/README.md), [explicit state](../stages/03-stateful-orchestration/theory/01-why-explicit-state.md), [state machines](../stages/03-stateful-orchestration/theory/02-state-machines-for-agents.md), and [LangGraph core concepts](../stages/03-stateful-orchestration/theory/03-langgraph-core-concepts.md).

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_state_graph.py`](test_state_graph.py) | Core | Handwritten `TinyStateGraph`: fixed/conditional edges, unknown-route rejection, cycle step budgets, topology validation, and node update contracts. | Lets you understand graph semantics without attributing them to framework magic. |
| [`test_langgraph_runtime.py`](test_langgraph_runtime.py) | Framework | Rebuilds the ReAct loop as a LangGraph graph, preserves an application-owned model-step budget, and surfaces Tool failure as an observation at this teaching stage. | Demonstrates that switching from `while` loop to graph changes orchestration representation, not Tool authority. |
| [`test_stage03_frameworks.py`](test_stage03_frameworks.py) | Framework | LangGraph streaming updates, checkpoint-backed `interrupt()` / `Command(resume=...)`, `thread_id`, and LangChain Tool/message compatibility. | Verifies the exact framework concepts introduced after the handwritten mechanism. |

Install with `.[dev,stage03]` for the framework tests.

## Stage 04 — Retrieval, RAG, vector backends, and embeddings

Read with [Stage 04](../stages/04-agentic-rag/README.md), [vector search](../stages/04-agentic-rag/theory/03-vector-search-and-similarity.md), [FAISS vs vector database](../stages/04-agentic-rag/theory/04-faiss-vs-vector-database.md), and [Agentic RAG](../stages/04-agentic-rag/theory/07-agentic-rag.md).

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_retrieval.py`](test_retrieval.py) | Core | Chunk overlap/metadata, invalid chunk settings, cosine behavior, deterministic normalized teaching embeddings, top-k ranking, and metadata filtering before ranking. | Protects the first-principles retrieval semantics underneath every later vector backend. |
| [`test_rag.py`](test_rag.py) | Core | Basic RAG always retrieves; Agentic RAG may skip retrieval, rewrite once, answer from sufficient evidence, abstain when evidence stays weak, and reject malformed control decisions. | Makes "Agentic RAG" a bounded workflow instead of "keep searching until the model feels confident." |
| [`test_stage04_vector_backends.py`](test_stage04_vector_backends.py) | Framework | FAISS nearest-neighbor behavior, the deliberate lack of fake native metadata filtering in the teaching adapter, Qdrant local search + payload filter, and LangChain retriever adaptation. | Shows what each backend actually owns instead of flattening all vector systems into one abstraction. |
| [`test_openai_embeddings.py`](test_openai_embeddings.py) | Framework, offline/shared | The OpenAI embedding adapter follows the provider-neutral embedding contract and validates dimensions using a fake client. Stage 15 reuses this adapter in its production-oriented retrieval path. | Protects the interface boundary between Stage 04 retrieval and later real embedding providers. |

Install `.[dev,stage04]` for FAISS/Qdrant/LangChain backend tests.

## Stage 05 — MCP and asynchronous Tool execution

Read with [Stage 05](../stages/05-mcp/README.md), [MCP mental model](../stages/05-mcp/theory/01-mcp-mental-model.md), [current stateless protocol/transports](../stages/05-mcp/theory/03-stateless-protocol-and-transports.md), and [the Tiny-Agent bridge](../stages/05-mcp/theory/05-python-sdk-v2-and-tiny-agent-bridge.md).

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_async_tools.py`](test_async_tools.py) | Core | `ToolRegistry.aexecute()` can run sync handlers and await async handlers; synchronous `execute()` refuses an async handler instead of leaking a coroutine object. | Remote MCP Tools are naturally async, so the Tool abstraction needs an honest async boundary. |
| [`test_stage05_mcp.py`](test_stage05_mcp.py) | Framework | MCP v2 / protocol `2026-07-28`, Tool/Resource/Prompt discovery, structured Tool results, bridge namespacing, registry population, remote async execution, and explicit MCP Tool errors. | Confirms current MCP semantics rather than relying on older `initialize()`-era tutorials. |

Install with `.[dev,stage05]`.

## Stage 06 — Memory, durable persistence, and HITL

Read with [Stage 06](../stages/06-memory-persistence-hitl/README.md), [context/state/checkpoint/memory boundaries](../stages/06-memory-persistence-hitl/theory/01-context-state-checkpoint-memory.md), [long-term memory policy](../stages/06-memory-persistence-hitl/theory/03-long-term-memory-and-write-policy.md), [durable persistence](../stages/06-memory-persistence-hitl/theory/04-durable-persistence-and-resume.md), and [HITL approval](../stages/06-memory-persistence-hitl/theory/05-human-in-the-loop-and-approval.md).

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_memory_policy.py`](test_memory_policy.py) | Core | Owner-scoped memory namespaces, candidate validation, explicit non-sensitive semantic-memory writes, and default rejection of incidental, sensitive, or procedural self-rewrite memory. | "The model extracted a fact" is not authorization to persist it. |
| [`test_approval.py`](test_approval.py) | Core | Serializable approval payloads; `approve`, `edit`, `reject`; edited-argument requirements; and rejection returning no executable arguments. | Human review becomes structured policy data rather than an informal yes/no string. |
| [`test_stage06_langgraph.py`](test_stage06_langgraph.py) | Framework | Thread-scoped checkpoints, SQLite durability across new saver/graph objects, cross-thread Store namespaces, HITL edit before execution, and reject paths that never enter execution. | Demonstrates the difference among short-term execution state, durable checkpointing, long-term Store, and approval. |
| [`test_stage06_postgres.py`](test_stage06_postgres.py) | Service | `PostgresSaver` survives connection recreation and `PostgresStore` persists cross-thread memory. Skipped unless `TEST_POSTGRES_URI` is set. | Proves that the same semantics survive a production-oriented shared backend instead of only an in-memory/local demo. |

Use `.[dev,stage06]`; Postgres tests require a test database.

## Stage 07 — Context Engineering

Read with [Stage 07](../stages/07-context-engineering/README.md), especially [context as an attention budget](../stages/07-context-engineering/theory/01-context-is-an-attention-budget.md) and [selection/compaction](../stages/07-context-engineering/theory/02-context-assembly-selection-compaction.md).

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_context_engineering.py`](test_context_engineering.py) | Core | Required and high-priority items survive selection, required context fails closed if it cannot fit, and compaction records provenance plus estimated token savings. | A context window is a budgeted selection problem, not a bucket that should always be filled. |

## Stage 08 — Agent Skills

Read with [Stage 08](../stages/08-agent-skills/README.md), especially [Skill format/progressive disclosure](../stages/08-agent-skills/theory/02-skill-format-and-progressive-disclosure.md).

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_skills.py`](test_skills.py) | Core/framework-format | Skill metadata can be discovered without loading the full procedure, activation loads instructions/allowed Tools/references, and the declared Skill name must match its directory. | Progressive disclosure only works if discovery and activation are distinct, validated operations. |

Install `.[dev,stage08]` for YAML parsing.

## Stage 09 — Reliability, safety, and governance

Read with [Stage 09](../stages/09-reliability-safety/README.md), [failure model](../stages/09-reliability-safety/theory/01-agent-failure-modes.md), [validation](../stages/09-reliability-safety/theory/02-validation-and-output-handling.md), [timeouts/retries](../stages/09-reliability-safety/theory/03-timeout-retry-cancellation.md), [budgets/loops](../stages/09-reliability-safety/theory/04-execution-budgets-and-loops.md), [permissions](../stages/09-reliability-safety/theory/05-tool-permissions-and-least-privilege.md), and [prompt injection/sandboxing](../stages/09-reliability-safety/theory/06-prompt-injection-and-sandboxing.md).

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_validation.py`](test_validation.py) | Core | The teaching JSON-Schema subset accepts supported valid inputs and fails closed on missing/wrong/extra/nested values; malformed application schemas are distinguished from bad model arguments. | Validation must happen before execution, and developer schema bugs should not be mislabeled as model errors. |
| [`test_reliability.py`](test_reliability.py) | Core | Safe failure classification/redaction, retryable timeout, explicit safe errors, bounded backoff, Tool/retry/token/cost budgets, fingerprints, and repeated-call detection. | Reliability policy needs typed data; it cannot be reconstructed from arbitrary exception strings. |
| [`test_governance.py`](test_governance.py) | Core | Default-deny permissions, role allowlists, approval separate from authorization, high-risk approval gates, and exact argument binding via stable fingerprints. | Approval for one reviewed action must not become a reusable permission token for another action. |
| [`test_guarded_runtime.py`](test_guarded_runtime.py) | Core composition | Composes validation -> permission -> approval -> budget -> loop check -> execution -> timeout/retry -> safe failure. It verifies that blocked calls never reach the handler and retries happen only for retry-safe operations. | This is the main executable specification of the Stage 09 guarded execution pipeline. |
| [`test_trust.py`](test_trust.py) | Core | External content is labeled untrusted; simple prompt-injection detection is treated as a signal rather than authorization policy. | "Looks suspicious" and "is allowed to control execution" are completely different questions. |
| [`test_stage09_integrations.py`](test_stage09_integrations.py) | Framework | Full `jsonschema` features, Tenacity bounded retry predicates, and Pydantic strict application boundaries. | Maps the handwritten safety concepts to mature libraries without surrendering application policy. |

Install with `.[dev,stage09]` for integration-library tests.

## Stage 10 — Observability and evaluation

Read with [Stage 10](../stages/10-evaluation-observability/README.md), [tracing/observability](../stages/10-evaluation-observability/theory/02-tracing-and-observability.md), [Tool/trajectory evaluation](../stages/10-evaluation-observability/theory/03-tool-and-trajectory-evaluation.md), [LLM-as-judge](../stages/10-evaluation-observability/theory/05-graders-and-llm-as-judge.md), and [quality/cost/latency regression](../stages/10-evaluation-observability/theory/06-quality-cost-latency-and-regression.md).

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_observability.py`](test_observability.py) | Core | Parent/child trace trees, privacy-safe default capture, opt-in redaction/truncation, nested sanitization, and safe exception recording. | Observability must help engineers without turning traces into a second secret-leak channel. |
| [`test_observed_runtime.py`](test_observed_runtime.py) | Core composition | Wraps the guarded Tool executor with tracing, verifies Agent -> Tool span parentage, useful attributes/attempt counts, and safe failure classification without raw arguments or secret exception text. | Shows how Stage 09 execution semantics become Stage 10 observable behavior. |
| [`test_evaluation.py`](test_evaluation.py) | Core | Tool precision/recall/F1, argument accuracy, trajectory sequence vs policy safety, repetitions, execution success, metric coverage, regression gates, higher/lower-is-better metrics, LLM-judge validation, and non-finite-number rejection. | A correct final string is not enough; trajectory, safety, coverage, cost, and statistical comparability are separate signals. |
| [`test_stage10_integrations.py`](test_stage10_integrations.py) | Framework | LangSmith tracing can be disabled offline; OpenTelemetry exports nested spans and records error status without leaking exception messages/events. | Verifies production observability mappings while preserving the privacy boundary defined by the core tracer. |

Install with `.[dev,stage10]`.

## Stage 11 — Multi-Agent coordination and A2A

Read with [Stage 11](../stages/11-multi-agent/README.md), [delegation/handoff/supervision](../stages/11-multi-agent/theory/02-delegation-handoffs-supervision.md), [context ownership](../stages/11-multi-agent/theory/03-context-ownership-and-shared-state.md), [parallel coordination](../stages/11-multi-agent/theory/04-parallelism-and-coordination.md), and [delegation governance](../stages/11-multi-agent/theory/05-delegation-governance.md).

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_multi_agent.py`](test_multi_agent.py) | Core | Delegation keeps manager ownership, successful handoff transfers ownership, failed handoff does not, context is projected, policies default-deny, handoff loops/parallelism are bounded, fan-out is prevalidated, failures are redacted, and coordination metrics distinguish attempts from successes. | Multi-Agent is a coordination/control problem, not merely "call several models." |
| [`test_stage11_integrations.py`](test_stage11_integrations.py) | Framework, offline | OpenAI Agents SDK manager-as-Tool vs handoff objects, current A2A 1.0 Agent Card shape, and A2A Message/request objects without network calls. | Maps Tiny-Agent coordination semantics to real ecosystem interfaces while keeping the test deterministic. |

Install with `.[dev,stage11]`.

## Stage 12 — Workspace and sandbox compute

Read with [Stage 12](../stages/12-agent-workspace-sandbox/README.md), [workspace/file policy](../stages/12-agent-workspace-sandbox/theory/02-files-artifacts-and-workspace-policy.md), and [container isolation/threat model](../stages/12-agent-workspace-sandbox/theory/03-container-isolation-and-threat-model.md).

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_workspace.py`](test_workspace.py) | Core | Workspace path confinement, exclusive creation, `../` escape rejection, and the default-deny Docker command baseline (`--network none`, read-only root, dropped capabilities, no-new-privileges). | File access and command execution need an application-owned boundary before an Agent receives a computer-like environment. |

The test builds the Docker command; it does not need to launch a real container.

## Stage 13 — Production service, identity, jobs, and infrastructure

Read with [Stage 13](../stages/13-production-deployment/README.md), [service boundaries/identities](../stages/13-production-deployment/theory/01-service-boundaries-and-identities.md), [async/concurrency/streaming](../stages/13-production-deployment/theory/02-async-concurrency-streaming.md), [Postgres/Redis/state](../stages/13-production-deployment/theory/03-postgres-redis-and-state.md), and [authentication/tenancy/durable jobs](../stages/13-production-deployment/theory/08-authentication-tenancy-and-durable-jobs.md).

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_production.py`](test_production.py) | Core | Bounded async service execution, sync handlers off the event loop, backpressure/capacity rejection, typed timeouts, the subtle rule that a timed-out sync thread still occupies capacity until it actually finishes, and privacy-safe readiness failures. | An HTTP timeout does not magically kill a worker thread; service capacity must reflect real execution. |
| [`test_service_identity.py`](test_service_identity.py) | Core | Client payloads cannot assert trusted identity; authenticated subject/tenant are server-bound; owner checks enforce both subject and tenant. | `user_id` from request JSON is data, not authentication. |
| [`test_jobs.py`](test_jobs.py) | Core/durable | SQLite run queue survives object recreation, uses leases, and only the worker that owns the lease can complete the job. | Durable work needs explicit ownership after the request/process that created it is gone. |
| [`test_stage13_integrations.py`](test_stage13_integrations.py) | Framework + Service | FastAPI liveness/readiness/run/request-id/streaming, safe HTTP failures, secret-safe settings, current A2A route serving, plus real Redis fixed-window and Postgres pool checks when their environment variables are present. | This is the main service-boundary integration suite for Stage 13. |

Install `.[dev,stage13]`. Redis/Postgres cases require their explicit test-service environment variables.

## Stage 14 — Long-horizon harness

Read with [Stage 14](../stages/14-long-horizon-harness/README.md).

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_harness.py`](test_harness.py) | Core/durable | A task ledger externalizes progress, a new runtime object resumes unfinished work, and a task left `running` by a crashed worker is recovered and retried. | Long-horizon progress must survive model session/process loss; "the chat remembers" is not a durability mechanism. |

[`test_jobs.py`](test_jobs.py) is also relevant here: Stage 14 builds on Stage 13 durable job/lease concepts, but the task ledger and service run queue remain different scopes.

## Stage 15 — OpenScholar capstone

Read with [Stage 15](../stages/15-capstone-enterprise-agent/README.md). These tests deliberately combine mechanisms from earlier Stages instead of re-teaching them in isolation.

| Test file | Category | What it verifies | Why it matters |
|---|---|---|---|
| [`test_capstone.py`](test_capstone.py) | Core composition | Evidence thresholds/abstention, grounded report evaluation, explicit-request memory, HITL-gated export, workspace path confinement, and unknown-citation detection. | Proves that a research Agent must be evidence-governed even when every individual component works. |
| [`test_capstone_v2.py`](test_capstone_v2.py) | Core + Framework | Diversifies repeated chunks from one document, reuses the Stage 04 Qdrant retriever contract, and separates semantic citation support from mere citation-label existence. | A citation marker can exist and still fail to support the claim. Retrieval diversity is also a synthesis-quality concern. |
| [`test_openscholar_production.py`](test_openscholar_production.py) | Framework | Serves OpenScholar through an authenticated FastAPI boundary and proves identity comes from server authentication, not request-body `user_id`. | Reconnects the capstone to Stage 13 identity/tenant rules. |
| [`test_stage15_integrations.py`](test_stage15_integrations.py) | Framework composition | LangGraph OpenScholar completion, HITL resume/export, base + graph HTTP implementations, and smoke tests for the Stage 15 MCP, A2A, and API examples. | Final composition check that the major ecosystem boundaries can coexist without changing the domain invariants. |

`test_openai_embeddings.py` is also run in the Stage 15 path because the capstone can replace the deterministic teaching embedding with a provider adapter.

Install with `.[dev,stage15]` for the complete integration suite.

---

# 4. Cross-stage regression tests

Some tests intentionally belong to more than one lesson. That is a feature: later Stages should strengthen earlier mechanisms without silently breaking their original semantics.

| Test file | Connects | What it protects |
|---|---|---|
| [`test_workflow_safety.py`](test_workflow_safety.py) | Stage 02 workflows + Stage 09 safe failures | Expected `StepFailure` may expose an explicitly safe operational message, while an unexpected exception keeps only a safe type/classification and does not copy internal secret text into workflow state. |
| [`test_openai_embeddings.py`](test_openai_embeddings.py) | Stage 04 retrieval + Stage 15 production retrieval | The provider-specific embedding implementation must continue to satisfy the same provider-neutral `EmbeddingModel` contract used by earlier retrieval code. |
| [`test_observed_runtime.py`](test_observed_runtime.py) | Stage 09 guarded execution + Stage 10 tracing | Adding observability must not bypass redaction/permission/failure semantics. |
| [`test_jobs.py`](test_jobs.py) | Stage 13 durable jobs + Stage 14 harness | Both need durable ownership/progress, but a service run lease is not the same object as the harness task ledger. |

When one of these fails after a later-stage change, do not automatically "update the test." First decide whether the architecture intentionally changed or whether a later abstraction has violated an earlier invariant.

---

# 5. What a failure usually tells you

| Failure family | First place to inspect |
|---|---|
| `test_runtime*` | `src/tiny_agent/runtime.py`, ToolCall/observation sequencing, stop conditions |
| `test_openai_adapter*`, `test_structured_decision*` | provider adapter normalization and provider-response validation |
| `test_workflows*` | route/Plan validation, Planner/Executor ownership, execution/replan budgets |
| `test_state_graph*`, `test_langgraph_runtime*` | state update/edge semantics and graph stopping/checkpoint behavior |
| `test_retrieval*`, `test_rag*`, vector backend tests | chunking, embedding contract, ranking/filtering, retrieval/evidence decisions |
| MCP tests | async Tool boundary, protocol version/API shape, bridge namespacing/error conversion |
| memory/approval/persistence tests | identity namespace, write policy, checkpoint/Store distinction, interrupt/resume semantics |
| reliability/governance tests | validation, typed failure, retry safety, budgets, permission/approval ordering |
| observability/evaluation tests | trace privacy, span relationships, metric definitions/coverage, regression gates |
| multi-Agent tests | active ownership, allowed edges, context projection, coordination budgets |
| workspace tests | path normalization/confinement and sandbox command policy |
| production tests | concurrency/backpressure, trusted identity, leases, health/readiness, external infrastructure |
| capstone tests | composition: evidence, citation support, HITL, identity, retrieval and framework boundaries |

A failing assertion is useful only if you can connect it back to the invariant it represents.

---

# 6. What these tests do **not** prove

Passing this suite does **not** prove that a deployment is automatically secure, compliant, scalable, or production-ready for every threat model.

For example:

- a Docker command-policy test does not prove complete container isolation;
- deterministic RAG tests do not prove retrieval quality on your domain corpus;
- a permission unit test does not replace enterprise IAM/RBAC/ABAC design;
- local SQLite durability does not imply distributed exactly-once side effects;
- an offline A2A/MCP object test does not prove remote service authentication or network reliability;
- an LLM-judge interface test does not prove a judge is unbiased or calibrated.

The role of this directory is narrower and more useful:

> **turn each architectural promise made by the course into an executable contract that can fail loudly when the implementation drifts.**

If you add a new Agent mechanism to `src/tiny_agent/`, add or update the corresponding test *and* update both this guide and [`README.zh-CN.md`](README.zh-CN.md) so future learners can still answer: "What is this test for, and which lesson does it belong to?"

# Framework & Tooling Map

Tiny-Agent is organized by **Agent capability stages**, not by framework names. Frameworks and infrastructure are introduced only when learners already understand the engineering problem the tool is meant to solve.

The teaching pattern is:

```text
Why the capability is needed
        ->
Implement / inspect the mechanism from first principles
        ->
Introduce the production tool/framework
        ->
Compare what the abstraction adds
```

## Tool-to-stage map

| Stage | Capability | Main tools/frameworks introduced |
|---|---|---|
| 00 | LLM & tool-use foundations | OpenAI SDK, JSON Schema |
| 01 | ReAct & core Agent runtime | OpenAI Responses API, handwritten Tiny-Agent runtime |
| 02 | Workflow, routing, planning | Structured Outputs, handwritten workflow/router/planner |
| 03 | Stateful orchestration | **LangGraph**, selected **LangChain** core abstractions |
| 04 | RAG & Agentic retrieval | **FAISS**, **Qdrant**, LangChain retriever/vector-store integrations |
| 05 | Standardized capabilities/context | **MCP 2026-07-28**, **MCP Python SDK v2**, stdio, Streamable HTTP, Tiny-Agent MCP bridge |
| 06 | Memory, durable persistence, HITL | LangGraph **Checkpointer + Store + interrupt**, **SQLite**, **PostgreSQL**, Tiny-Agent memory/approval policies |
| 07 | Reliability, safety, Tool governance | handwritten policy primitives, **jsonschema**, **Pydantic strict mode**, **Tenacity**, `asyncio` timeout/cancellation, OWASP Agent/LLM risk model |
| 08 | Evaluation & observability | handwritten trace/eval core, **OpenTelemetry**, **LangSmith**, custom datasets/graders/regression gates |
| 09 | Multi-Agent systems & interoperability | handwritten coordination core, **OpenAI Agents SDK**, **A2A 1.0 / a2a-sdk**, LangGraph pattern mapping |
| 10 | Production service & deployment | handwritten service boundary, **FastAPI**, **Uvicorn**, **Pydantic Settings**, **PostgreSQL**, **Redis**, **Docker/Compose**, A2A route hosting, CI |
| 11 | OpenScholar integrated capstone | shared research domain layer, handwritten base orchestrator, **LangGraph** orchestrator, `pypdf`, Crossref, **MCP**, **A2A**, FastAPI, Docker, regression tests |

## Why tools are not separate stages

A framework-only curriculum tends to teach syntax before architecture. Tiny-Agent deliberately avoids a structure such as:

```text
LangChain chapter
LangGraph chapter
Qdrant chapter
MCP decorators chapter
Postgres chapter
Tenacity chapter
LangSmith chapter
OpenTelemetry chapter
OpenAI Agents SDK chapter
A2A chapter
FastAPI chapter
Docker chapter
```

Instead, each tool appears where its abstractions answer a concrete engineering problem.

Examples:

```text
Python while-loop Agent
        -> explicit state machine
        -> LangGraph
```

```text
embedding similarity from first principles
        -> FAISS local index
        -> Qdrant vector database
        -> LangChain Retriever abstraction
```

```text
hard-coded local ToolRegistry
        -> inspect MCP protocol/primitives
        -> MCP Python SDK v2
        -> stdio / Streamable HTTP
        -> Tiny-Agent MCP adapter
```

```text
thread state / memory candidate / risky action
        -> explicit persistence + policy boundaries
        -> LangGraph Checkpointer / Store / interrupt
        -> SQLite / PostgreSQL durable backends
```

```text
raw Tool execution
        -> typed failures / local validation
        -> handwritten retry / budget / permission mechanisms
        -> jsonschema / Pydantic / Tenacity
        -> GuardedToolExecutor
```

```text
print-based trajectory inspection
        -> local trace/span model
        -> RunArtifact + deterministic Agent evaluators
        -> regression gate
        -> OpenTelemetry
        -> LangSmith
```

```text
single Agent / deterministic workflow baseline
        -> explicit delegation + handoff semantics
        -> context/authority/budget boundaries
        -> OpenAI Agents SDK mapping
        -> A2A 1.0 interoperability
        -> Stage 08 evidence-based comparison
```

```text
local Agent call
        -> BoundedAgentService
        -> FastAPI/SSE transport adapter
        -> Postgres/Redis lifecycle
        -> liveness/readiness/graceful shutdown
        -> A2A route hosting
        -> Docker/Compose/CI
```

```text
all capability stages
        -> shared OpenScholar evidence/domain contracts
        -> handwritten base orchestration
        -> LangGraph orchestration over the same domain
        -> deterministic grounding/citation evaluation
        -> HTTP / MCP / A2A / container boundaries
```

## LangChain vs LangGraph

Tiny-Agent teaches these as different layers:

```text
LangChain
    -> reusable LLM application components
       messages, model wrappers, tools, prompts,
       document loaders, splitters, retrievers, vector-store adapters,
       middleware / higher-level guardrails

LangGraph
    -> stateful orchestration/runtime
       state, nodes, edges, branching, persistence,
       interrupts, streaming, resumable execution
```

Neither replaces the first-principles Tiny-Agent implementation.

## Vector search learning order

```text
Text
  -> Chunking
  -> Embeddings
  -> Vector similarity
  -> FAISS
  -> Qdrant
  -> LangChain Retriever abstraction
  -> Agentic RAG
```

FAISS is used first as an inspectable local vector index. Qdrant is introduced next to teach persistence, metadata/payload filtering, collections, service boundaries, and remote vector retrieval.

## MCP learning order

```text
Tiny-Agent local Tool
  -> why integration-specific adapters stop scaling
  -> Host / Client / Server mental model
  -> Tools / Resources / Prompts
  -> JSON-RPC wire walkthrough
  -> classic session model vs MCP 2026 stateless core
  -> MCPServer + Client (in process)
  -> stdio process boundary
  -> Streamable HTTP service boundary
  -> MCPToolBridge
  -> trust / authorization boundaries
```

The official Python SDK v2 is introduced only after the learner can explain what the SDK is abstracting.

```text
MCP Tool      -> Tiny-Agent Tool adapter
MCP Resource  -> remains context/data
MCP Prompt    -> remains a prompt primitive
```

## Memory / persistence / HITL learning order

```text
thread runtime state
    -> Checkpointer
    -> InMemorySaver
    -> SqliteSaver
    -> PostgresSaver

candidate durable fact
    -> MemoryCandidate
    -> MemoryWritePolicy
    -> Store namespace/key
    -> InMemoryStore / PostgresStore

risky side effect
    -> review policy
    -> interrupt
    -> approve / edit / reject
    -> validate + authorize
    -> execute
```

Key distinction:

```text
Checkpointer = persist one execution thread so it can resume
Store        = persist selected data across threads/sessions
```

Infrastructure technology does not define semantic responsibility.

## Reliability / safety / Tool-governance learning order

```text
arbitrary Tool exception
    -> typed safe failure / redaction

model ToolCall
    -> handwritten local validation
    -> jsonschema / Pydantic strict comparison

transient failure
    -> handwritten bounded retry/backoff
    -> retry-safe application policy
    -> Tenacity comparison

Agent trajectory
    -> BudgetLedger
    -> repeated-call detector

capability
    -> authenticated Principal
    -> default-deny role allowlist
    -> exact-action approval binding

external text
    -> explicit untrusted-data envelope
    -> detection as telemetry signal
    -> deterministic permission boundary

blocking/untrusted execution
    -> thread/process distinction
    -> sandbox concepts

all controls
    -> GuardedToolExecutor
```

Stage 07 preserves:

```text
validation          != authorization
approval            != authorization
discovery           != permission
retryable failure   != retry-safe operation
thread timeout      != hard termination
subprocess           != secure sandbox
injection detection != access control
```

## Evaluation / observability learning order

```text
print/debug output
    -> trace vs span mental model
    -> privacy-aware LocalTracer / InMemorySpanSink

Stage 07 guarded Tool execution
    -> ObservedGuardedToolExecutor
    -> failure/attempt/latency trace signals

Agent behavior
    -> EvalExample + RunArtifact
    -> final-response evaluator
    -> Tool selection evaluator
    -> Tool argument evaluator
    -> trajectory evaluator

subjective quality
    -> deterministic grader first
    -> provider-neutral LLMJudgeEvaluator when needed
    -> calibrate against humans

candidate change
    -> EvaluationReport
    -> metric coverage
    -> absolute / relative RegressionGate

local telemetry model
    -> OpenTelemetry adapter

local evaluation model
    -> LangSmith trace / dataset / experiment / online-eval workflow
```

Stage 08 preserves:

```text
logging       != tracing
tracing       != evaluation
metric        != trace
evaluation    != test
trace         != audit log
final answer  != trajectory quality
Tool choice   != Tool arguments
LLM judge     != ground truth
OpenTelemetry != LangSmith
observability != authorization
```

## Multi-Agent / interoperability learning order

```text
plain function / deterministic workflow / one Agent baseline
    -> identify a real responsibility or isolation boundary
    -> handwritten AgentSpec + TeamRuntime
    -> delegation (manager keeps control)
    -> handoff (specialist takes over)
    -> context projection / private namespaces
    -> coordination budgets + handoff-loop protection
    -> parallel fan-out / application-owned fan-in
    -> OpenAI Agents SDK Agent.as_tool() vs handoffs
    -> A2A 1.0 Agent Card / Message / Task / Part / Artifact model
    -> compare quality, latency, cost, and coordination metrics against baseline
```

Stage 09 preserves:

```text
workflow              != multi-Agent
multiple model calls  != multi-Agent
Agent as Tool         != handoff
shared context        != copy all runtime state
discovery             != authorization
delegation            != privilege escalation
parallelism           != free speed
A2A                   != MCP
Agent Card            != internal Tool registry
correct final answer  != good coordination trajectory
```

A2A teaching is explicitly versioned because 1.0 changed Agent Card and operation shapes from older material. Stage 09 covers protocol objects; Stage 10 adds a real ASGI hosting boundary.

## Production service / deployment learning order

Stage 10 deliberately does **not** start from a Dockerfile or giant FastAPI route.

```text
local Agent handler
    -> ServiceRequest / run identity
    -> BoundedAgentService
    -> process-local concurrency admission
    -> queue wait + execution deadline
    -> FastAPI request/response adapter
    -> SSE stream events
    -> liveness / readiness
    -> ASGI lifespan
    -> Postgres pool / Redis coordination
    -> typed environment configuration
    -> A2A route factory + shutdown drain
    -> Docker image / Compose stack
    -> real infrastructure + image-build CI
```

It preserves these distinctions:

```text
HTTP validation       != Tool authorization
request_id            != user identity
thread_id             != access permission
async                  != CPU parallelism
concurrency limit      != rate limit
process-local semaphore != global capacity limit
request timeout        != hard thread/process termination
SSE                     != durable event log
liveness                != readiness
readiness               != monitoring
PostgreSQL               != Redis
Redis cache              != durable source of truth
SecretStr                != secret manager
.env                     != production vault
Docker image             != production correctness
BackgroundTasks          != durable job queue
one worker memory        != shared replica state
A2A compatibility        != caller authentication
InMemoryTaskStore        != durable multi-replica A2A state
```

The same PostgreSQL technology can appear in Stage 06 and Stage 10 for different reasons: Stage 06 teaches persistence semantics; Stage 10 teaches service topology, pooling, lifecycle, and replica effects.

The same A2A protocol appears in Stage 09 and Stage 10 at different layers: Stage 09 teaches interoperability semantics; Stage 10 hosts the protocol over an operational network service.

## Stage 11 capstone integration order

The capstone is deliberately organized by **shared application semantics first, framework comparison second**:

```text
ResearchRequest / Evidence / ResearchReport
    -> local full-text corpus + explicit scholarly-metadata trust class
    -> deterministic evidence filtering / sufficiency gate
    -> shared memory / review / export / evaluation services
    -> BaseOpenScholarAgent (ordinary Python + asyncio)
    -> LangGraphOpenScholarAgent (same domain, graph orchestration)
    -> HTTP / MCP / A2A / Docker adapters
```

Important Stage 11 distinctions:

```text
retrieved candidate        != sufficient evidence
scholarly metadata         != evidence of paper findings
long-term preference       != scientific evidence
correct final prose        != grounded trajectory
human approval             != path authorization
LangGraph checkpoint       != user long-term memory
MCP corpus capability      != A2A whole-Agent service
framework orchestration    != application truth
```

The capstone also explains why the same framework can be useful in one layer and unnecessary in another. Ordinary Python remains the reference implementation for readable control flow; LangGraph earns its role specifically around explicit state, durable pause/resume, and inspectable graph transitions.

## Maintenance rule

When Tiny-Agent introduces a new external tool or framework, the relevant stage should explain:

1. what problem already exists before the tool is introduced;
2. the smallest handwritten/inspectable representation of the mechanism when practical;
3. the tool's core concepts and APIs;
4. what complexity the tool removes;
5. what new complexity or lock-in it introduces;
6. when not to use it;
7. at least one runnable example and one comparison with the underlying mechanism;
8. the version/specification target when the ecosystem is evolving quickly;
9. durability, trust, and ownership boundaries when the tool stores state or executes remote actions;
10. what deterministic application policy remains necessary even after a mature framework is introduced;
11. what telemetry/evaluation data is collected and how privacy/retention are handled when the tool observes runtime behavior;
12. what identity/context/authority is transferred when a tool introduces a new Agent or service boundary;
13. which controls are process-local versus shared across workers/replicas;
14. how long-lived resources start, become ready, drain, and close;
15. which tutorial simplifications stop being correct when the deployment topology changes;
16. in an integrated capstone, which semantics are domain-owned and which are merely framework plumbing.

This keeps Tiny-Agent focused on **Agent engineering**, while still teaching the mainstream tools expected in real projects.
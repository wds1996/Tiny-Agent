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
| 08 | Evaluation & observability | **LangSmith**, OpenTelemetry concepts, custom eval datasets/graders |
| 09 | Multi-Agent systems | OpenAI Agents SDK / AutoGen-style patterns for comparison where useful |
| 10 | Production deployment | **FastAPI**, Docker, PostgreSQL, Redis, CI/CD |
| 11 | Enterprise capstone | Integrated use of the tools learned above |

## Why tools are not separate stages

A framework-only curriculum tends to teach syntax before architecture. Tiny-Agent deliberately avoids a structure such as:

```text
LangChain chapter
LangGraph chapter
Qdrant chapter
MCP decorators chapter
Postgres chapter
Tenacity chapter
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
        -> LangChain middleware/guardrails comparison
```

```text
print-based trajectory inspection
        -> structured traces/spans
        -> LangSmith / OpenTelemetry
```

```text
python script
        -> HTTP service boundary
        -> FastAPI
        -> Docker / deployment
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

Neither replaces the first-principles Tiny-Agent implementation. The handwritten implementation exists so learners can understand what these abstractions actually do.

## Vector search learning order

Stage 04 uses this progression:

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

Stage 05 deliberately does **not** begin with a black-box MCP server decorator.

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

Stage 05 also preserves an important semantic boundary:

```text
MCP Tool      -> Tiny-Agent Tool adapter
MCP Resource  -> remains context/data
MCP Prompt    -> remains a prompt primitive
```

## Memory / persistence / HITL learning order

Stage 06 does **not** begin with "install a database and call it memory."

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

The key distinction is:

```text
Checkpointer = persist one execution thread so it can resume
Store        = persist selected data across threads/sessions
```

Both may use PostgreSQL, but infrastructure technology does not define semantic responsibility.

## Reliability / safety / Tool-governance learning order

Stage 07 deliberately starts from the Stage 01 execution boundary rather than from a guardrails package.

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
    -> LangChain middleware / guardrails comparison
```

This stage preserves several distinctions:

```text
validation          != authorization
approval            != authorization
discovery           != permission
retryable failure   != retry-safe operation
thread timeout      != hard termination
subprocess           != secure sandbox
injection detection != access control
```

These distinctions matter more than memorizing one security library.

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
10. what deterministic application policy remains necessary even after a mature framework is introduced.

This keeps Tiny-Agent focused on **Agent engineering**, while still teaching the mainstream tools expected in real projects.

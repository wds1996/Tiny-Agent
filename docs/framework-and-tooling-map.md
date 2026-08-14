# Framework & Tooling Map

Tiny-Agent is organized by **Agent capability stages**, not by framework names. Frameworks and infrastructure are introduced only when learners already understand the engineering problem the tool is meant to solve.

The teaching pattern is:

```text
Why the capability is needed
        ->
Implement the mechanism from first principles
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
| 05 | Standardized tools/context | **MCP Python SDK**, custom MCP client/server |
| 06 | Memory, persistence, HITL | LangGraph checkpoint/persistence concepts, SQLite/PostgreSQL/Redis where appropriate |
| 07 | Reliability & safety | Pydantic/JSON Schema validation, retry/timeout/cancellation patterns, sandbox/permission concepts |
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
        -> LangChain retriever abstraction
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

Tiny-Agent will teach these as different layers:

```text
LangChain
    -> reusable LLM application components
       messages, model wrappers, tools, prompts,
       document loaders, splitters, retrievers, vector-store adapters

LangGraph
    -> stateful orchestration/runtime
       state, nodes, edges, branching, persistence,
       interrupts, streaming, resumable execution
```

Neither replaces the first-principles Tiny-Agent implementation. The handwritten implementation exists so learners can understand what these abstractions actually do.

## Vector search learning order

Stage 04 will use this progression:

```text
Text
  -> Chunking
  -> Embeddings
  -> Vector similarity
  -> FAISS
  -> Qdrant
  -> LangChain retriever abstraction
  -> Agentic RAG
```

FAISS is used first as an inspectable local vector index. Qdrant is introduced next to teach persistence, metadata/payload filtering, collections, service boundaries, and remote vector retrieval.

## Maintenance rule

When Tiny-Agent introduces a new external tool or framework, the relevant stage should explain:

1. what problem already exists before the tool is introduced;
2. the smallest handwritten implementation of the mechanism when practical;
3. the tool's core concepts and APIs;
4. what complexity the tool removes;
5. what new complexity or lock-in it introduces;
6. when not to use it;
7. at least one runnable example and one comparison with the handwritten version.

This keeps Tiny-Agent focused on **Agent engineering**, while still teaching the mainstream tools expected in real projects.

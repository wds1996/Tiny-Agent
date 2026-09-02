# Framework & Tooling Map

Tiny-Agent uses frameworks only after exposing the mechanism they abstract.

| Stage | Handwritten mechanism | Framework / protocol mapping |
|---|---|---|
| 00 | messages, schemas, ToolCall mental model | OpenAI Responses / current model APIs |
| 01 | AgentRuntime / ToolRegistry | provider adapters; high-level Agent SDK comparison |
| 02 | routers / planners / replanners | Structured Outputs; LangGraph workflow patterns |
| 03 | TinyStateGraph | LangGraph StateGraph; selected LangChain components |
| 04 | embeddings / cosine / Retriever / RAG | FAISS, Qdrant, LangChain Retriever |
| 05 | MCPToolBridge | MCP 2026-07-28 Python SDK v2 |
| 06 | memory policy / approval primitives | LangGraph Checkpointer / Store / SQLite / Postgres |
| 06A | ContextBudget / ContextBuilder / compaction | provider token usage; LangGraph context/memory patterns |
| 06B | SkillCatalog / progressive activation | Agent Skills open `SKILL.md` standard |
| 07 | GuardedToolExecutor | jsonschema, Pydantic, Tenacity, OWASP mappings |
| 08 | local tracer / eval suite | OpenTelemetry, LangSmith |
| 09 | TeamRuntime / context/delegation policy | OpenAI Agents SDK patterns, A2A 1.0 |
| 09A | AgentWorkspace / DockerSandboxRunner | container/managed sandbox concepts; OpenAI Agents SDK sandbox direction |
| 10 | BoundedAgentService / SQLiteRunQueue / identity binding | FastAPI, Uvicorn, Postgres, Redis, Docker, A2A server |
| 10A | TaskLedger / LongHorizonHarness | durable workflow/harness concepts; MCP Tasks adjacency |
| 11 | OpenScholar domain + base orchestration | LangGraph, OpenAI, Qdrant, MCP, A2A, FastAPI |

## Framework rule

```text
mechanism
-> inspectable Tiny-Agent implementation
-> deterministic tests
-> framework adapter/example
-> explicit limitations
```

High-level APIs are useful after you can state which responsibilities they own.

## Protocol distinctions

```text
Function Calling
    model -> structured action proposal inside application

MCP
    application/Agent -> external Tools/Resources/Prompts

A2A
    independent Agent system -> independent Agent system

Agent Skills
    portable procedural knowledge loaded by compatible Agent clients
```

## Modern harness stack

A 2026-style general-purpose Agent increasingly looks like:

```text
Agent harness
├── model/provider
├── context builder + compaction
├── Tool/MCP capability layer
├── Skill catalog
├── state/checkpoints/memory
├── governance + approvals
├── traces/evals
├── task ledger / durable run state
└── sandbox interface
     ├── filesystem
     ├── shell/code
     └── artifacts
```

Do not interpret this as a checklist requiring every box. A read-only classification Agent should not receive a shell merely because the diagram contains one.

## Version anchors (September 2026)

- MCP teaching target: protocol `2026-07-28`, Python SDK v2.
- A2A teaching target: protocol 1.0, current Python SDK line used by CI.
- LangGraph/LangChain target: stable 1.x lines pinned in `pyproject.toml`.
- OpenAI provider examples: OpenAI Python 2.x and current GPT-5.6 family guidance.
- Agent Skills: open `SKILL.md` specification at agentskills.io.

All version-specific integrations belong in CI because framework documentation ages faster than the architecture beneath it.

# Framework & Tooling Map

Tiny-Agent uses frameworks only after exposing the mechanism they abstract.

| Stage | Handwritten mechanism | Framework / protocol mapping |
|---|---|---|
| 00 | messages, schemas, ToolCall mental model | OpenAI Responses / current model APIs |
| 01 | AgentRuntime / ToolRegistry | provider adapters; high-level Agent SDK comparison |
| 02 | routers / planners / replanners | Structured Outputs; LangGraph workflow patterns |
| 03 | State / Node / Edge / Reducer / MiniStateGraph | LangGraph StateGraph |
| 04 | chunking / embeddings / cosine / Retriever / bounded RAG control | FAISS, Qdrant, OpenAI Responses generation |
| 05 | MCPToolBridge | MCP 2026-07-28 Python SDK v2 |
| 06 | memory policy / approval primitives | LangGraph Checkpointer / Store / SQLite / Postgres |
| 07 | ContextBudget / ContextBuilder / compaction | provider token usage; LangGraph context/memory patterns |
| 08 | SkillCatalog / progressive activation | Agent Skills open `SKILL.md` standard |
| 09 | GuardedToolExecutor | jsonschema, Pydantic, Tenacity, OWASP mappings |
| 10 | local tracer / eval suite | OpenTelemetry, LangSmith |
| 11 | TeamRuntime / context/delegation policy | OpenAI Agents SDK patterns, A2A 1.0 |
| 12 | AgentWorkspace / DockerSandboxRunner | container/managed sandbox concepts; OpenAI Agents SDK sandbox direction |
| 13 | BoundedAgentService / SQLiteRunQueue / identity binding | FastAPI, Uvicorn, Postgres, Redis, Docker, A2A server |
| 14 | TaskLedger / LongHorizonHarness | durable workflow/harness concepts; MCP Tasks adjacency |
| 15 | OpenScholar domain + base orchestration | LangGraph, OpenAI, Qdrant, MCP, A2A, FastAPI |

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
- A2A teaching target: protocol 1.0, current Python SDK line exercised by the repository tests.
- LangGraph target: stable 1.x line pinned in `pyproject.toml`.
- LangChain is introduced in stages that actually need its components or integrations rather than as a Stage 03 prerequisite.
- OpenAI provider examples: OpenAI Python 2.x and current GPT-5.6 family guidance.
- Agent Skills: open `SKILL.md` specification at agentskills.io.

Version-specific integrations should have explicit regression or integration tests because framework documentation ages faster than the architecture beneath it.

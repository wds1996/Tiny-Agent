# Tiny-Agent 2026 Modern Agent Competency Map

This document answers one question:

> If a learner completes Tiny-Agent, which major modern Agent engineering competencies should they be able to explain and implement?

## Layer 1 — Model/application boundary

| Competency | Stage | Evidence |
|---|---|---|
| messages/instructions | 00 | theory + minimal API mental model |
| Structured Output / JSON Schema | 00 | schema-constrained control data |
| Function/Tool Calling | 00 | ToolCall -> runtime -> observation |
| model capability/selection | 00 | reasoning/cost/latency trade-offs |
| context/token budgeting | 00, 06A | explicit ContextBudget |
| provider adapters | 01, 02 | normalized Model/StructuredDecisionModel |

## Layer 2 — Agent control flow

| Competency | Stage |
|---|---|
| ReAct / decide-act-observe | 01 |
| bounded stopping | 01, 07 |
| deterministic workflow vs Agent | 02 |
| semantic routing | 02 |
| planner-executor | 02 |
| bounded replanning | 02 |
| explicit state machines | 03 |
| graph orchestration | 03 |
| streaming/checkpoint/interrupt | 03, 06 |

## Layer 3 — Knowledge and context

| Competency | Stage |
|---|---|
| chunking / embeddings / similarity | 04 |
| FAISS / Qdrant | 04 |
| reranking / Agentic RAG | 04 |
| retrieval evaluation | 04, 08 |
| MCP Tools/Resources/Prompts | 05 |
| MCP 2026 stateless core | 05 |
| MCP extensions/Tasks/MRTR/Apps | 05 advanced |
| short/long-term memory | 06 |
| Context Engineering | 06A |
| compaction/provenance/JIT context | 06A |
| Agent Skills / progressive disclosure | 06B |

## Layer 4 — Safety, reliability, authority

| Competency | Stage |
|---|---|
| local schema validation | 07 |
| failure taxonomy/redaction | 07 |
| timeout/cancellation/retry | 07 |
| idempotency reasoning | 06, 07, 10 |
| run-wide budgets / loop detection | 07 |
| principals/least privilege | 07 |
| exact approval binding | 07 |
| prompt-injection boundaries | 07 |
| memory/Skill provenance | 06, 06B |
| workspace path policy | 09A |
| controlled sandbox compute | 09A |
| network/credential separation | 09A |

## Layer 5 — Evaluation and collaboration

| Competency | Stage |
|---|---|
| traces/spans/privacy-aware capture | 08 |
| Tool/trajectory evaluation | 08 |
| deterministic vs LLM judges | 08 |
| offline/online eval | 08 |
| cost/latency/quality regression gates | 08 |
| delegation vs handoff | 09 |
| context projection | 09 |
| fan-out/fan-in | 09 |
| A2A 1.0 interoperability | 09, 10 |

## Layer 6 — Production and long horizon

| Competency | Stage |
|---|---|
| thin service boundary | 10 |
| request/run/thread/identity separation | 10 |
| trusted auth/tenant binding | 10 |
| concurrency/backpressure/deadlines | 10 |
| durable jobs/leases | 10 |
| Postgres/Redis lifecycle | 10 |
| liveness/readiness/shutdown | 10 |
| Docker/Compose topology | 10 |
| task ledger / session handoff | 10A |
| externalized progress/artifacts | 10A |
| evaluator/repair loop | 10A |
| harness/compute rehydration | 09A, 10A |

## Layer 7 — Capstone synthesis

OpenScholar demonstrates how a real application chooses a subset of these mechanisms rather than enabling every capability indiscriminately.

Its core invariants are:

```text
metadata != scientific evidence
memory != evidence
model proposal != policy
retrieval result != evidence sufficiency
citation existence != semantic support
approval != authorization
protocol compatibility != trust
container != perfect sandbox
```

## A+ completion standard

A learner should be able to design a new Agent and answer, before choosing a framework:

1. What decisions genuinely require a model?
2. What is the state machine?
3. Which state is durable, and at what scope?
4. What exact context does each model turn receive?
5. Which capabilities are Tools, which are Skills, and which are external protocols?
6. What evidence/trust classes exist?
7. What authority can the model proposal reach?
8. Which actions require approval and authorization?
9. Where does code/file execution run?
10. How does work survive process/sandbox loss?
11. How is the Agent evaluated beyond final prose?
12. What service identity/tenant owns every durable resource?
13. Why is multi-Agent complexity justified?
14. What happens under overload, timeout, retry, shutdown, and partial side effects?
15. Which production claims remain deployment-specific rather than solved by the library?

If those questions are precise, the learner has moved from “using an Agent framework” to engineering an Agent system.

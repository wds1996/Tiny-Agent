# 2026 Theory Curriculum Audit

This audit records the repository-wide theory review performed after the Stage 00–11 curriculum and modern extension stages were complete.

The review standard is [`theory-writing-standard.md`](theory-writing-standard.md).

## Audit criteria

Every Stage was checked for:

- precise concept boundaries;
- motivation and failure mode;
- mechanism/control/data flow;
- model vs application authority;
- common misconceptions;
- repository-aligned core code snippets;
- worked examples and failure cases;
- humor/intuitive explanation where it improves memory;
- links to earlier/later Stage concepts;
- honest production limitations.

## Results

| Stage | Topic | Audit result |
| --- | --- | --- |
| 00 | LLM / Structured Output / Function Calling | Expanded model selection, token/cost/latency, instruction/context theory |
| 01 | ReAct runtime / provider adapter | Mature; retained |
| 02 | Workflow / routing / planning | Mature reference-quality chapter set; retained |
| 03 | State / graphs / LangGraph | Mature; retained |
| 04 | RAG / retrieval | Existing theory mature; hybrid/RRF/diversity/MMR/query transformation chapter expanded |
| 05 | MCP | Existing core mature; 2026 Tasks/MRTR/Apps/Extensions moved into the main theory narrative |
| 06 | Memory / persistence / HITL | Mature; retained |
| 06A | Context Engineering | Expanded all theory chapters with real ContextBuilder code and worked cases |
| 06B | Agent Skills | Expanded all theory chapters with SKILL.md, SkillCatalog, routing, supply-chain governance and evaluation |
| 07 | Reliability / safety / governance | Mature; retained |
| 08 | Evaluation / observability | Mature; retained |
| 09 | Multi-Agent / A2A | Mature; retained |
| 09A | Workspace / sandbox | Expanded all theory chapters with path, container, credential, network and recovery mechanisms |
| 10 | Production deployment | Expanded all theory chapters: service identity, async/backpressure, Postgres/Redis, secrets, workers, operations, A2A and durable jobs |
| 10A | Long-horizon harness | Expanded all theory chapters with TaskLedger, crash recovery, artifacts/Skills, evaluator/repair and durable-vs-disposable state |
| 11 | OpenScholar capstone | Existing implementation chapters retained; modern production profile expanded into complete Deep-Research composition map |

## What was deliberately not done

The audit did **not** rewrite already mature chapters merely to make every file the same length.

Length is not the quality metric. A chapter is sufficient when the learner can explain the mechanism, inspect aligned code, identify failure modes, and understand what the abstraction does *not* guarantee.

Likewise, the Capstone does not force every subsystem into every short request. Context, Skills, sandbox compute, multi-Agent work, durable jobs, and long-horizon harnesses are composable layers enabled only when task requirements justify them.

## Maintainer rule

New theory should preserve the repository's core invariant:

```text
model / evidence / memory / Skill
        -> influence proposals

application-owned policy
        -> validates / budgets / authorizes

executor / Tool / sandbox
        -> performs allowed work
```

Framework APIs may evolve. This control boundary should remain recognizable.
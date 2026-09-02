# Stage 11 — Capstone: OpenScholar Research Agent

This final stage integrates Stages 00–10 into one portfolio-quality application instead of introducing another isolated framework API.

OpenScholar answers academic questions with **local full-text evidence**, optional **Crossref scholarly discovery**, bounded planning, reviewer/writer coordination, long-term style memory, human approval for durable export, tracing, deterministic evaluation, HTTP serving, MCP/A2A interoperability, and container deployment.

Two implementations are provided:

1. **Base version** — ordinary Python + `asyncio` + Tiny-Agent primitives. The control flow is inspectable and mostly handwritten.
2. **LangGraph version** — the same domain services and policies, but orchestration is expressed as a `StateGraph` with checkpointing and `interrupt` / `Command(resume=...)` for durable HITL.

The comparison is deliberately fair: Evidence, corpus ingestion, Crossref trust labels, memory policy, export authorization, evaluation, reviewer policy, and production adapters are shared. Only orchestration plumbing changes.

## Why an academic research Agent?

A research Agent forces almost every earlier lesson to become concrete:

```text
question
  -> structured plan
  -> bounded subquestions
  -> local RAG + scholarly discovery
  -> evidence trust normalization
  -> grounded synthesis
  -> critic / writer review
  -> memory write policy
  -> optional human-approved export
  -> trace + evaluation
  -> API / MCP / A2A / container
```

It also exposes an important truth: **finding a paper title is not the same as possessing evidence for the paper's claims**. OpenScholar therefore distinguishes local full text from scholarly metadata instead of putting everything into one vaguely named `context` list.

## Architecture

```text
                           +-------------------+
User / HTTP / A2A -------> | OpenScholar        |
                           +---------+---------+
                                     |
                              bounded planning
                                     |
                         +-----------+-----------+
                         |                       |
                         v                       v
                  Local full-text RAG       Crossref search
                  substantive evidence      discovery metadata
                         |                       |
                         +-----------+-----------+
                                     |
                              normalize / dedupe
                                     |
                             evidence sufficiency
                               /             \
                              /               \
                       insufficient          synthesize
                           |                    |
                         abstain          Supervisor
                                             |
                                             v
                                           Critic
                                             |
                                      revision needed?
                                          /       \
                                        no        yes
                                         |         |
                                         |       Writer
                                         |         |
                                         +----+----+
                                              |
                                      memory policy
                                              |
                                      export requested?
                                          /       \
                                        no        yes
                                         |          |
                                         |     human approval
                                         |          |
                                         |     authorization
                                         |          |
                                         +------> report file
                                              |
                                        ResearchReport
                                   + trace + metrics + eval
```

## Stage map

| Earlier stage | Capstone responsibility |
|---|---|
| 00 | structured model/provider boundaries |
| 01 | reason → act → observe mental model |
| 02 | schema-constrained bounded planning |
| 03 | explicit state and LangGraph orchestration |
| 04 | chunking, embeddings, retrieval, evidence |
| 05 | MCP corpus capability boundary |
| 06 | memory, checkpointing, interrupt/resume, HITL |
| 07 | budgets, trust labels, approval vs authorization |
| 08 | tracing, deterministic evals, regression thinking |
| 09 | supervisor → critic → writer delegation |
| 09 A2A | expose OpenScholar as a remote Agent service |
| 10 | bounded FastAPI service and container deployment |

## Repository layout

```text
src/tiny_agent/capstone/
├── models.py
├── corpus.py
├── scholarly.py
├── memory.py
├── heuristic.py
├── openai_adapter.py
├── team.py
├── export.py
├── evaluation.py
├── base_agent.py
└── langgraph_agent.py

src/tiny_agent/integrations/
└── openscholar_api.py

stages/11-capstone-enterprise-agent/
├── README.md
├── data/
│   ├── open_papers.json
│   └── synthetic_corpus.jsonl
├── theory/
│   ├── 01-capstone-system-design.md
│   ├── 02-evidence-and-knowledge-base.md
│   ├── 03-base-implementation.md
│   ├── 04-langgraph-implementation.md
│   ├── 05-memory-hitl-safety.md
│   ├── 06-evaluation-observability.md
│   └── 07-production-mcp-a2a.md
├── code/
│   ├── bootstrap_open_corpus.py
│   ├── base_offline_demo.py
│   ├── base_real_corpus_demo.py
│   ├── langgraph_demo.py
│   ├── langgraph_hitl_demo.py
│   ├── evaluation_demo.py
│   ├── mcp_server.py
│   ├── a2a_server.py
│   └── api_app.py
├── deployment/
│   └── Dockerfile
└── exercises/
    └── review-questions.md
```

## Install

```bash
python -m pip install -e ".[dev,stage11]"
```

The project core remains dependency-light. Stage 11 dependencies are optional because PDF ingestion, LangGraph, FastAPI, MCP, and A2A should not become mandatory for learners studying Stage 00.

## Quick start: deterministic offline version

The repository contains a small synthetic corpus so the complete architecture can be exercised in CI without network calls or API keys.

```bash
python stages/11-capstone-enterprise-agent/code/base_offline_demo.py
```

This uses `HeuristicResearchModel`. It is intentionally not a strong language model; it exists so the **control system** can be inspected independently from model quality.

## Build the real open-paper corpus

The repository stores only a manifest. PDFs are downloaded locally rather than committed to Git.

```bash
python stages/11-capstone-enterprise-agent/code/bootstrap_open_corpus.py
```

This downloads a small set of open arXiv papers, extracts text with `pypdf`, and writes a generated `corpus.jsonl` under `stages/11-capstone-enterprise-agent/generated/`.

Then run:

```bash
python stages/11-capstone-enterprise-agent/code/base_real_corpus_demo.py
```

The default real-corpus demo still uses the deterministic model so it does not require an API key. To experiment with a real model, use `OpenAIResearchModel` and the existing OpenAI adapters after configuring your credentials.

## LangGraph version

```bash
python stages/11-capstone-enterprise-agent/code/langgraph_demo.py
python stages/11-capstone-enterprise-agent/code/langgraph_hitl_demo.py
```

The graph version uses the same corpus, evidence types, memory policy, review team, and exporter. LangGraph owns node/edge state transitions and checkpoint/resume plumbing; it does **not** become the authority for evidence or permissions.

## Evidence contract

OpenScholar intentionally uses two trust classes:

```text
local_fulltext
    -> paper text actually present in the local corpus
    -> may support substantive claims

scholarly_metadata
    -> title/authors/year/venue/DOI discovered through Crossref
    -> useful for discovery and bibliographic facts
    -> NOT proof of paper findings
```

Local retrieval also applies `min_local_score`. Stage 04's brute-force top-k retriever always returns candidates; a zero-similarity chunk must not become “evidence” merely because it occupied rank 1.

## Human approval boundary

Export is a real side effect:

```text
request export
  -> ApprovalRequest
  -> approve / edit / reject
  -> ordinary validation + path authorization
  -> write file
```

The LangGraph implementation performs no side effect before `interrupt()`. A resumed node may execute again from its beginning, so putting a non-idempotent write before `interrupt()` would be a correctness bug.

## Evaluate the Agent

```bash
python stages/11-capstone-enterprise-agent/code/evaluation_demo.py
```

Deterministic checks include:

- completed vs abstained status;
- substantive local evidence count;
- citation labels actually used in the answer;
- hallucinated/unknown citation labels;
- citation coverage;
- required-term recall;
- grounding gate.

Correct prose is not enough if the trajectory fabricated a citation or treated metadata as scientific evidence.

## Serve it

```bash
uvicorn stages.11-capstone-enterprise-agent.code.api_app:app
```

Because Python module names cannot contain hyphens, the more practical command from repository root is:

```bash
python stages/11-capstone-enterprise-agent/code/api_app.py
```

Endpoints include:

```text
POST /v1/research/base
POST /v1/research/langgraph
POST /v1/research/langgraph/{thread_id}/resume
GET  /livez
```

`user_id` in the teaching request body is only correlation metadata. A production service must bind user/tenant identity from authentication middleware instead of trusting a client-provided string.

## MCP and A2A

The same application is exposed at two different boundaries:

```text
MCP
  -> search the OpenScholar corpus as a capability

A2A
  -> ask OpenScholar itself to perform a research task
```

This is the concrete difference between Stage 05 and Stage 09:

> MCP connects an Agent/application to capabilities; A2A connects independent Agent systems.

## Base vs LangGraph

| Question | Base version | LangGraph version |
|---|---|---|
| orchestration | Python control flow | StateGraph |
| parallel retrieval | asyncio | graph node using asyncio |
| state representation | local variables / dataclasses | typed graph state |
| pause/resume | application must build it | checkpoint + interrupt/Command |
| small workflow readability | excellent | extra abstraction |
| complex durable branching | manual state-machine work grows | strong fit |

The conclusion is intentionally **not** “LangGraph wins.” The lesson is:

> Use ordinary code while ordinary code keeps the state machine clear. Use a graph/runtime when durable branching, resumability, inspection, or human interrupts justify the abstraction.

## Run tests

```bash
pytest -q tests/test_capstone.py tests/test_stage11_integrations.py
```

Stage 11 CI also smoke-tests the public examples and container artifact without downloading external papers or calling a paid model.

## Final capstone questions

After finishing this stage, you should be able to explain:

1. Why evidence type is an application-domain concept rather than a prompt convention.
2. Why retrieval success and evidence sufficiency are different gates.
3. Why a human approval decision still needs ordinary authorization.
4. Why long-term memory must not silently become scientific evidence.
5. Why a framework should own orchestration plumbing rather than application truth.
6. Why a correct final answer can still be a failed Agent trajectory.
7. Why HTTP deployment, MCP interoperability, and A2A interoperability are three different boundaries.

If you can explain those seven points and modify both implementations without guessing, Tiny-Agent has achieved its final learning goal.
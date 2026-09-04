# Stage 15 — OpenScholar: Complete Modern Agent Capstone

OpenScholar is the final integration test for Tiny-Agent's complete 2026 learning path.

It is an academic research Agent because that domain forces the architecture to distinguish **discovery from evidence, memory from truth, context from state, model proposals from control policy, and short requests from durable work**.

## What the final system integrates

```text
Stage 00   LLM / Structured Output / Function Calling / context-cost basics
Stage 01   ReAct runtime + provider adapters + Tool interface design
Stage 02   bounded planning / routing / replanning
Stage 03   explicit state + LangGraph
Stage 04   RAG / vector retrieval / reranking / evaluation
Stage 05   MCP 2026 core + extensions concepts
Stage 06   memory / checkpoints / durable HITL
Stage 07  context engineering / compaction / JIT context
Stage 08  Agent Skills / procedural knowledge
Stage 09   reliability / safety / governance
Stage 10   tracing / evaluation / regression
Stage 11   multi-Agent / handoffs / A2A
Stage 12  governed workspace / sandbox compute
Stage 13   production serving / identity / durable jobs
Stage 14  long-horizon harness / task ledger / rehydration
```

## Domain architecture

```text
question
  ↓
remembered user preferences (not evidence)
  ↓
bounded research plan
  ↓
parallel retrieval
  ├── local full text
  └── scholarly metadata discovery
  ↓
trust normalization + score filtering + optional document diversity
  ↓
evidence sufficiency gate
  ├── insufficient -> abstain
  └── sufficient
        ↓
      synthesis
        ↓
 supervisor -> critic -> optional writer
        ↓
 deterministic citation inventory checks
        ↓
 optional semantic citation-support judge
        ↓
 memory write policy
        ↓
 optional human-approved authorized export
        ↓
 ResearchReport + trace + metrics
```

## Two orchestration implementations

### BaseOpenScholarAgent

Ordinary Python/`asyncio` + Tiny-Agent primitives. Excellent for inspecting control flow.

### LangGraphOpenScholarAgent

The same domain concepts with `StateGraph`, checkpointer, and durable `interrupt`/`Command(resume=...)` semantics.

They share domain policy, but durable execution semantics are intentionally **not identical**: the Base version returns `approval_required` and needs application-managed continuation; the LangGraph version can persist and resume the suspended graph.

## Evidence contract

```text
local_fulltext
    -> substantive source text actually ingested

scholarly_metadata
    -> title/authors/year/venue/DOI discovery facts
    -> not proof of findings
```

The deterministic evaluator checks citation-label existence/grounding gates. The optional semantic evaluator separately asks whether the cited evidence actually supports a cited claim at the stated strength.

## Production retrieval path

The original offline `HashEmbeddingModel` remains for reproducible learning and CI.

The upgraded path adds:

```text
OpenAIEmbeddingModel (provider adapter)
        +
QdrantRetriever
        +
RetrieverResearchCorpus
        +
DiversifiedResearchCorpus
```

so the production architecture can use a real neural embedding model, vector database filtering/persistence, and repeated-document diversity without changing `ResearchReport` or the research Agent control flow.

See:

- `src/tiny_agent/integrations/openai_embeddings.py`
- `src/tiny_agent/capstone/production_corpus.py`
- `code/production_retrieval_demo.py`

## Production service boundary

The original teaching API deliberately exposes body-level `user_id` as demo metadata. Do not use that as authentication.

The upgraded production boundary:

```text
HTTP request
-> deployment-specific authenticator
-> AuthenticatedIdentity(subject/roles/tenant)
-> bind trusted metadata
-> BoundedAgentService
-> BaseOpenScholarAgent
```

The request schema contains no identity fields.

See:

- `src/tiny_agent/integrations/openscholar_production.py`
- `code/production_api_app.py`

Durable HITL still belongs to the LangGraph/checkpointer path; a production deployment must additionally bind persisted thread ownership to authenticated identity before resume.

## Quick start

Install:

```bash
python -m pip install -e ".[dev,stage15]"
```

Offline deterministic capstone:

```bash
python stages/15-capstone-enterprise-agent/code/base_offline_demo.py
python stages/15-capstone-enterprise-agent/code/langgraph_demo.py
python stages/15-capstone-enterprise-agent/code/langgraph_hitl_demo.py
python stages/15-capstone-enterprise-agent/code/evaluation_demo.py
```

Build real paper corpus:

```bash
python stages/15-capstone-enterprise-agent/code/bootstrap_open_corpus.py
python stages/15-capstone-enterprise-agent/code/base_real_corpus_demo.py
```

Optional real semantic retrieval (requires OpenAI API key):

```bash
python stages/15-capstone-enterprise-agent/code/production_retrieval_demo.py
```

Production-shaped authenticated/bounded API demo:

```bash
export OPEN_SCHOLAR_DEMO_API_KEY='local-secret'
python stages/15-capstone-enterprise-agent/code/production_api_app.py
```

## Theory order

1. `theory/01-capstone-system-design.md`
2. `theory/02-evidence-and-knowledge-base.md`
3. `theory/03-base-implementation.md`
4. `theory/04-langgraph-implementation.md`
5. `theory/05-memory-hitl-safety.md`
6. `theory/06-evaluation-observability.md`
7. `theory/07-production-mcp-a2a.md`
8. `theory/08-modern-production-profile.md`

## Interoperability

```text
MCP
  -> expose corpus/search capabilities

A2A
  -> expose OpenScholar as an independent remote Agent

HTTP
  -> ordinary application/service client boundary
```

Do not confuse protocol compatibility with authentication or trust.

## What “complete” means here

The repository now contains code paths for every major modern Agent subsystem: model/provider boundary, Tool use, planning, state, RAG, MCP, memory, HITL, context engineering, Skills, safety, evaluation, multi-Agent/A2A, workspace/sandbox, service identity, durable jobs, long-horizon harnesses, and deployment.

The default OpenScholar demo remains intentionally local/offline. Enterprise production still requires deployment-specific choices such as real IAM, durable Postgres checkpointer/Store, managed sandbox infrastructure, data retention/licensing, hardened egress, autoscaling, backups, and operational SLOs.

That distinction is intentional:

> **Tiny-Agent now teaches the complete architecture and provides working reference mechanisms without pretending that one repository can supply every organization's production infrastructure or security policy.**

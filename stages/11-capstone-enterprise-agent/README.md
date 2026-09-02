# Stage 11 — OpenScholar Capstone: Build a Complete Research Agent Twice

Stage 11 is the final integration chapter of Tiny-Agent. It does **not** introduce another pile of decorators. It asks a harder question:

> Can we combine the mechanisms from Stages 00–10 into one inspectable Agent product, then rebuild the same product with a framework without surrendering application control?

The product is **OpenScholar**, an evidence-grounded academic research Agent. It has two implementations:

1. **BaseOpenScholarAgent** — explicit Python orchestration (`asyncio`, dataclasses, Tiny-Agent primitives).
2. **LangGraphOpenScholarAgent** — the same domain services and policies, with `StateGraph`, checkpointing, and `interrupt`/`Command` orchestration.

The point is not to declare a winner. The point is to see exactly what a framework removes, and what it must never be allowed to own.

## Product behavior

```text
ResearchRequest
      |
      v
read governed preferences
      |
      v
structured research plan
      |
      +----------------------+
      |                      |
      v                      v
local full-text RAG      Crossref discovery
(substantive evidence)   (bibliographic metadata)
      |                      |
      +-----------+----------+
                  v
      evidence trust normalization
                  |
                  v
        grounded draft synthesis
                  |
                  v
      supervisor -> critic -> writer
           bounded review team
                  |
                  v
      optional memory write policy
                  |
           export requested?
             /         \
            no         yes
            |           |
            |       human approval
            |           |
            |      path authorization
            |           |
            +-----------+
                  |
                  v
       report + evidence + metrics + trace
```

## Why academic research?

Research naturally forces us to confront nearly every earlier Agent problem: uncertain planning, tools, retrieval, source trust, long context, memory, external APIs, multi-Agent review, human approval, evaluation, and deployment. A toy weather bot can demonstrate function calling; it cannot seriously demonstrate an Agent architecture.

## Stage 00–10 map

| Earlier stage | OpenScholar use |
|---|---|
| 00 Foundations | typed model/tool boundaries and structured data |
| 01 ReAct | model proposes; runtime executes; iterative evidence feedback |
| 02 Planning | schema-constrained bounded research plan |
| 03 State / LangGraph | framework version explicitly models graph state and edges |
| 04 RAG | chunking, embeddings, retrieval, evidence sufficiency |
| 05 MCP | optional corpus-search MCP server |
| 06 Memory / HITL | policy-governed preferences, checkpointed approval/resume |
| 07 Reliability / Safety | budgets, trust labels, redacted failures, least-privilege export |
| 08 Evaluation / Observability | nested traces and deterministic regression checks |
| 09 Multi-Agent / A2A | bounded supervisor/critic/writer review + optional A2A service |
| 10 Production | FastAPI, bounded service boundary, Docker |

## The most important trust rule

```text
local_fulltext
    -> may support substantive claims about the paper

scholarly_metadata
    -> may support title / author / year / DOI / discovery
    -> MUST NOT be treated as proof of a paper's findings
```

A paper title saying *Amazing Agent Beats Everything* is not experimental evidence that it actually did. Metadata is a map to evidence, not evidence-shaped magic dust.

## Repository layout

```text
src/tiny_agent/capstone/
├── models.py              # domain contracts
├── corpus.py              # local full-text knowledge base
├── scholarly.py           # Crossref metadata discovery
├── memory.py              # governed preference memory
├── export.py              # least-privilege durable side effect
├── heuristic.py           # deterministic offline model
├── openai_adapter.py      # real provider composition
├── team.py                # bounded supervisor/critic/writer team
├── evaluation.py          # deterministic capstone evals
├── base_agent.py          # framework-free orchestrator
└── langgraph_agent.py     # framework orchestrator

stages/11-capstone-enterprise-agent/
├── theory/
├── code/
├── data/open_papers.json
├── deployment/Dockerfile
└── exercises/
```

## First run — no key, no network

```bash
python -m pip install -e ".[dev,stage11]"
python stages/11-capstone-enterprise-agent/code/run_base.py
python stages/11-capstone-enterprise-agent/code/run_langgraph.py
python stages/11-capstone-enterprise-agent/code/evaluate_offline.py
```

The offline path uses a synthetic teaching corpus and `HeuristicResearchModel`. It exists so the entire control path can be inspected before API credentials enter the picture.

## Build the real local paper corpus

```bash
python stages/11-capstone-enterprise-agent/code/bootstrap_open_corpus.py --dry-run
python stages/11-capstone-enterprise-agent/code/bootstrap_open_corpus.py
```

The script downloads manifest papers from arXiv on your machine and writes `data/corpus.jsonl`. PDFs and generated corpus files are intentionally excluded from Git. Respect each paper's license and source terms; the repository does not redistribute the PDFs.

The local retriever begins with Tiny-Agent's inspectable feature-hashing retriever. That is a teaching baseline, not a claim that lexical feature hashing is state-of-the-art semantic retrieval. `min_local_score` prevents zero-similarity chunks from being promoted into evidence; for a serious corpus, replace the retriever with Stage 04's FAISS/Qdrant + a real embedding model and recalibrate the threshold with retrieval evaluation.

## Optional live model run

After building the corpus:

```bash
export OPENAI_API_KEY=...
export CROSSREF_MAILTO=you@example.com
python stages/11-capstone-enterprise-agent/code/live_research.py
```

The real-model adapter reuses Tiny-Agent's existing provider-neutral `Model` and `StructuredDecisionModel` boundaries. LangGraph does not become the model API, Crossref does not become the evidence authority, and OpenAI does not become the application policy engine.

## HITL export

```bash
python stages/11-capstone-enterprise-agent/code/hitl_export.py
```

In the LangGraph version, export uses:

```text
interrupt(approval_request)
      |
      | human decision
      v
Command(resume=...)
      |
      v
resolve approval
      |
      v
validate path under export root
      |
      v
write file
```

No file write occurs before `interrupt()`. That matters because an interrupted LangGraph node starts from the beginning when it resumes.

## Protocol extensions

```bash
# MCP capability server (blocks on stdio when run normally)
python stages/11-capstone-enterprise-agent/code/mcp_corpus_server.py

# A2A service: by default builds routes without binding a socket
python stages/11-capstone-enterprise-agent/code/a2a_research_server.py
```

MCP exposes a capability (search the corpus). A2A exposes an Agent (perform a research task). They are deliberately different abstractions.

## Production boundary

`service_app.py` exposes both implementations over FastAPI. `stage10_bounded_service.py` shows the capstone behind Stage 10's process-local concurrency/deadline boundary.

Remember:

```text
FastAPI route       != Agent architecture
Docker              != distributed correctness
request_id          != authenticated identity
approval            != authorization
checkpoint          != long-term memory
metadata            != scientific evidence
multi-Agent         != automatic quality gain
framework           != application policy
```

## Learning order

1. `theory/01-capstone-system-design.md`
2. `theory/02-evidence-and-knowledge-base.md`
3. `theory/03-base-implementation.md`
4. `theory/04-langgraph-implementation.md`
5. `theory/05-memory-governance-and-multi-agent-review.md`
6. `theory/06-evaluation-observability-and-production.md`
7. `theory/07-two-implementations-compared.md`
8. run the examples and exercises.

## Final milestone

You should be able to explain not only **how OpenScholar runs**, but why each responsibility belongs to its current layer—and which responsibilities would still exist if every framework were replaced tomorrow.

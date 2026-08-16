# Stage 04 — RAG & Agentic Retrieval

Stage 04 gives Tiny-Agent access to external knowledge and teaches how retrieval becomes part of a controlled Agent workflow.

The learning order is deliberate:

```text
Document
   -> Chunk
   -> Embedding
   -> cosine / top-k from first principles
   -> framework-free retriever
   -> FAISS local vector index
   -> Qdrant vector database + metadata filtering
   -> LangChain Retriever adapter
   -> reranking
   -> Basic RAG
   -> bounded Agentic RAG
   -> retrieval / grounding evaluation
```

The goal is **not** to memorize `similarity_search()`.

The goal is to understand what is happening underneath it, when retrieval should happen, and what to do when retrieved evidence is weak.

---

# Prerequisites

Complete Stage 00–03, or already understand:

- messages and Function Calling;
- provider-neutral interfaces;
- ReAct and tool observations;
- deterministic Workflow vs Agent;
- structured control decisions;
- Planner–Executor / bounded retry;
- explicit Agent state and LangGraph orchestration.

Stage 04 reuses the same engineering principles:

> **Model output proposes retrieval decisions; application code owns data access, filters, budgets, and execution.**

---

# Learning objectives

After this stage, you should be able to:

1. explain RAG as retrieve → augment → generate;
2. distinguish model parametric memory from runtime external evidence;
3. explain why RAG is not automatically an Agent;
4. chunk documents and explain chunk-size/overlap trade-offs;
5. define an embedding interface and explain vector dimensions;
6. compute cosine similarity from first principles;
7. explain inner product vs cosine similarity and normalization;
8. implement exact brute-force top-k retrieval yourself;
9. use FAISS `IndexFlatIP` for normalized-vector cosine ranking;
10. explain why FAISS is a vector-search library rather than a complete application database;
11. use Qdrant collections, points, payloads, and metadata filters;
12. explain why security/tenant filters must remain application-owned;
13. expose a Tiny-Agent retriever through LangChain `BaseRetriever`;
14. distinguish Retriever from Vector Store;
15. explain candidate retrieval vs reranking;
16. explain dense, sparse, and hybrid retrieval;
17. build Basic two-step RAG;
18. build bounded Agentic RAG with retrieval decisions, query rewriting, and evidence sufficiency;
19. force abstention when evidence remains insufficient;
20. evaluate retrieval separately from generation using metrics such as Recall@k and MRR.

---

# Part A — RAG and retrieval from first principles

Read in this order:

1. [`theory/01-rag-fundamentals.md`](theory/01-rag-fundamentals.md)
2. [`theory/02-chunking-and-embeddings.md`](theory/02-chunking-and-embeddings.md)
3. [`theory/03-vector-search-and-similarity.md`](theory/03-vector-search-and-similarity.md)
4. [`code/embedding_similarity_from_scratch.py`](code/embedding_similarity_from_scratch.py)
5. [`../../src/tiny_agent/retrieval.py`](../../src/tiny_agent/retrieval.py)
6. [`../../tests/test_retrieval.py`](../../tests/test_retrieval.py)

At this point you should understand the retrieval mechanism **without FAISS, Qdrant, or LangChain**.

---

# Part B — FAISS and vector databases

7. [`theory/04-faiss-vs-vector-database.md`](theory/04-faiss-vs-vector-database.md)
8. [`code/faiss_vector_retriever.py`](code/faiss_vector_retriever.py)
9. [`theory/05-qdrant-and-metadata-filtering.md`](theory/05-qdrant-and-metadata-filtering.md)
10. [`code/qdrant_vector_database.py`](code/qdrant_vector_database.py)
11. [`../../src/tiny_agent/retrievers/faiss.py`](../../src/tiny_agent/retrievers/faiss.py)
12. [`../../src/tiny_agent/retrievers/qdrant.py`](../../src/tiny_agent/retrievers/qdrant.py)

The comparison to remember is:

```text
FAISS
  -> dense-vector similarity-search library / local index

Qdrant
  -> vector database with collections, payloads, filters,
     persistence/service boundaries and database operations
```

---

# Part C — Framework integration and reranking

13. [`code/langchain_retriever_adapter.py`](code/langchain_retriever_adapter.py)
14. [`../../src/tiny_agent/retrievers/langchain_adapter.py`](../../src/tiny_agent/retrievers/langchain_adapter.py)
15. [`theory/06-retrieval-and-reranking.md`](theory/06-retrieval-and-reranking.md)
16. [`code/reranking_pipeline.py`](code/reranking_pipeline.py)

LangChain is intentionally introduced **after** the Retriever mechanism.

Use this mental model:

```text
Tiny-Agent Retriever
    query -> ranked SearchResult objects

LangChain BaseRetriever
    query -> Document objects
```

The adapter gives interoperability without changing the underlying retrieval idea.

---

# Part D — Basic RAG to Agentic RAG

17. [`code/basic_rag.py`](code/basic_rag.py)
18. [`theory/07-agentic-rag.md`](theory/07-agentic-rag.md)
19. [`code/agentic_retrieval.py`](code/agentic_retrieval.py)
20. [`code/evidence_answering.py`](code/evidence_answering.py)
21. [`../../src/tiny_agent/rag.py`](../../src/tiny_agent/rag.py)
22. [`../../tests/test_rag.py`](../../tests/test_rag.py)

The capability progression is:

```text
Basic RAG
question -> retrieve -> answer

Agentic RAG
question
   -> need retrieval?
   -> search query
   -> retrieve
   -> evidence sufficient?
       -> yes: answer
       -> no: bounded rewrite + retry
   -> still weak: abstain
```

---

# Part E — Evaluation

23. [`theory/08-rag-evaluation.md`](theory/08-rag-evaluation.md)
24. [`code/retrieval_evaluation.py`](code/retrieval_evaluation.py)
25. [`../../tests/test_stage04_vector_backends.py`](../../tests/test_stage04_vector_backends.py)
26. [`exercises/review-questions.md`](exercises/review-questions.md)

Do not evaluate only the final answer.

Separate:

```text
retrieval quality
    Recall@k / Precision@k / MRR / ranking analysis

from

generation quality
    correctness / groundedness / unsupported claims / abstention
```

---

# Installation

The framework-free core remains lightweight:

```bash
pip install -e ".[dev]"
```

Stage 04 vector/database integrations are optional:

```bash
pip install -e ".[stage04]"
```

For Stage 04 tests:

```bash
pip install -e ".[dev,stage04]"
```

If you want Stage 03 and Stage 04 framework dependencies together:

```bash
pip install -e ".[dev,stage03,stage04]"
```

Current Stage 04 optional dependencies include:

```text
numpy
faiss-cpu
qdrant-client
langchain
```

---

# Important note about embeddings

Tiny-Agent includes:

```python
HashEmbeddingModel
```

for deterministic offline learning and tests.

It is **not a neural semantic embedding model**.

It mostly rewards shared lexical tokens and exists so you can inspect:

```text
text -> vector -> similarity -> top-k
```

without downloading a model or using an API.

For real RAG, plug a proper embedding model into the same `EmbeddingModel` interface and evaluate it on your own retrieval dataset.

If `HashEmbeddingModel` thinks "car" and "automobile" are strangers at a party, that is expected. It was hired to teach vector plumbing, not to pass a linguistics exam.

---

# Stage architecture

The reusable Stage 04 core now looks like:

```text
                     +--------------------+
                     |   EmbeddingModel   |
                     +----------+---------+
                                |
               +----------------+----------------+
               |                                 |
               v                                 v
+-----------------------------+        +---------------------+
| InMemoryVectorRetriever     |        | optional backends   |
| exact brute-force cosine    |        | FAISS / Qdrant      |
+--------------+--------------+        +----------+----------+
               |                                  |
               +----------------+-----------------+
                                |
                                v
                         Retriever protocol
                                |
                  +-------------+-------------+
                  |                           |
                  v                           v
             BasicRAG                 AgenticRAGWorkflow
          retrieve -> answer       decide -> retrieve -> assess
                                      -> rewrite -> answer/abstain
```

LangChain interoperability sits beside the core through an adapter rather than becoming a mandatory dependency of `tiny_agent` imports.

---

# External learning resources

Use external resources as **just-in-time support**, not as a prerequisite wall.

## RAG foundations

- [Lewis et al. — Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401) — the original RAG paper; useful for understanding parametric + non-parametric memory.
- [LangChain Retrieval](https://docs.langchain.com/oss/python/langchain/retrieval) — current retrieval/RAG overview and distinctions between fixed and Agentic retrieval patterns.
- [LangChain Semantic Search tutorial](https://docs.langchain.com/oss/python/langchain/knowledge-base) — guided searchable-knowledge-base example.

## FAISS

- [FAISS official repository](https://github.com/facebookresearch/faiss)
- [FAISS Wiki](https://github.com/facebookresearch/faiss/wiki)
- [MetricType and distances](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances) — especially important for cosine vs inner-product search.
- [FAISS indexes](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes)
- [Guidelines to choose an index](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index)

## Qdrant

- [Qdrant Semantic Search 101 — local mode](https://qdrant.tech/documentation/tutorials-basics/search-beginners-local/)
- [Qdrant Local Quickstart](https://qdrant.tech/documentation/quickstart/)
- [Payload](https://qdrant.tech/documentation/concepts/payload/)
- [Filtering](https://qdrant.tech/documentation/search/filtering/)
- [Qdrant interfaces / Python client](https://qdrant.tech/documentation/interfaces/)

## LangChain Retriever

- [Retriever integrations](https://docs.langchain.com/oss/python/integrations/retrievers)
- [Semantic search / Retriever tutorial](https://docs.langchain.com/oss/python/langchain/knowledge-base)

## Suggested beginner reading order

```text
1. Tiny-Agent RAG fundamentals
2. Tiny-Agent chunking + embeddings
3. Tiny-Agent vector similarity
4. Run embedding_similarity_from_scratch.py
5. FAISS MetricType docs
6. Run faiss_vector_retriever.py
7. Qdrant Semantic Search 101
8. Run qdrant_vector_database.py
9. LangChain Retriever docs
10. Run langchain_retriever_adapter.py
11. Tiny-Agent reranking chapter
12. Basic RAG
13. Agentic RAG
14. Retrieval evaluation
```

Framework/database APIs evolve quickly. If a third-party tutorial conflicts with current official documentation or Tiny-Agent's tested dependency range, prefer the current official documentation.

---

# Runnable examples

Framework-free:

```bash
python stages/04-agentic-rag/code/embedding_similarity_from_scratch.py
python stages/04-agentic-rag/code/reranking_pipeline.py
python stages/04-agentic-rag/code/basic_rag.py
python stages/04-agentic-rag/code/agentic_retrieval.py
python stages/04-agentic-rag/code/evidence_answering.py
python stages/04-agentic-rag/code/retrieval_evaluation.py
```

With Stage 04 optional dependencies:

```bash
python stages/04-agentic-rag/code/faiss_vector_retriever.py
python stages/04-agentic-rag/code/qdrant_vector_database.py
python stages/04-agentic-rag/code/langchain_retriever_adapter.py
```

---

# What this stage deliberately does not claim

Stage 04 is not a complete enterprise-search platform.

Still deferred or intentionally simplified:

- production PDF/OCR/document ingestion pipelines;
- neural embedding provider selection/benchmarking;
- large-scale ANN index tuning;
- production Qdrant deployment/backup/security operations;
- sophisticated BM25/hybrid engines;
- cross-encoder/LLM reranker integrations;
- citation rendering UI;
- production prompt-injection defenses;
- full RAG observability/evaluation platform;
- access-control architecture.

Those topics appear in later reliability/evaluation/production stages or can be added as focused extensions.

---

# Key interview statements

You should be able to say these precisely:

> **RAG is runtime retrieval of external evidence followed by generation; it is not synonymous with a vector database.**

> **A Retriever is a query-to-evidence interface; a Vector Store is one possible storage/search implementation behind a Retriever.**

> **FAISS is primarily a dense-vector similarity-search library; a vector database adds database concerns such as payloads, filtering, collections, persistence, and service operations.**

> **For cosine search with FAISS inner product, normalize database and query vectors first.**

> **Metadata filters express constraints that should not be delegated to embedding similarity, especially tenant/security/version constraints.**

> **Agentic RAG adds model-driven retrieval decisions, query rewriting, and evidence checks, but application code must own retriever access, budgets, and stopping conditions.**

> **Retrieval and generation should be evaluated separately; a generator cannot rerank a relevant chunk that retrieval never returned.**

---

# Milestone

Stage 04 is complete when you can:

1. implement exact vector retrieval without a framework;
2. explain cosine similarity and normalized inner-product search;
3. use FAISS and explain what it does *not* provide;
4. use Qdrant local mode with payload filtering;
5. adapt a custom retriever into LangChain;
6. explain candidate retrieval, hybrid retrieval, and reranking;
7. implement Basic RAG;
8. implement bounded Agentic RAG with query rewriting and evidence sufficiency;
9. abstain when evidence is insufficient;
10. measure retrieval quality with a small deterministic evaluation set.

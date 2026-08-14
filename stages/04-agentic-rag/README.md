# Stage 04 — RAG & Agentic Retrieval

## Why this stage exists

LLMs do not automatically have reliable access to private, local, or current knowledge. Retrieval-Augmented Generation (RAG) gives a system access to external evidence. Agentic RAG adds another layer: the Agent decides when to retrieve, what source to use, whether the evidence is sufficient, and whether the query should be rewritten.

This stage teaches retrieval in two layers:

```text
retrieval mechanism first
        ->
vector index/database implementation
        ->
framework integrations
        ->
Agentic retrieval control
```

The objective is not merely to call `similarity_search()`. Learners should understand what embeddings, vector similarity, indexing, top-k, metadata filtering, reranking, and retrieval evaluation actually mean before a framework hides those details.

## Tools taught in this stage

### FAISS — local educational vector index

FAISS will be used first because it makes the vector-search mechanism easy to inspect without requiring a database service.

Learners will cover:

- embedding vectors;
- similarity search;
- cosine similarity / inner-product intuition;
- building a local index;
- adding/querying vectors;
- mapping vector results back to document chunks;
- limitations of an in-process vector index.

FAISS is used here primarily as a **mechanism-learning tool**, not as the final enterprise storage recommendation.

### Qdrant — service-style vector database

After the local FAISS example, the stage will introduce Qdrant to demonstrate what a real vector database adds:

- persistent collections;
- metadata/payload storage;
- filtering;
- collection/index management;
- remote/client-server access;
- operational separation between Agent service and retrieval service.

This creates a useful comparison:

```text
FAISS
  -> local index, minimal concepts, easy to inspect

Qdrant
  -> persistent vector database, metadata/filtering, service boundary
```

### LangChain retrieval components — integration layer

After learners understand raw retrieval, selected LangChain components will be introduced for:

- document loaders/splitters where useful;
- vector-store adapters;
- retriever interfaces;
- composing retrieval components with later LangGraph workflows.

The tutorial will always show the raw mechanism before the framework wrapper.

## Planned topics

- document parsing;
- chunking strategies;
- embeddings;
- vector similarity;
- FAISS local indexing;
- Qdrant collections and payloads;
- vector databases;
- metadata filtering;
- top-k retrieval;
- reranking;
- hybrid retrieval;
- LangChain retriever/vector-store abstractions;
- ordinary RAG vs Agentic RAG;
- retrieval routing;
- query rewriting;
- evidence sufficiency checks;
- grounded answering;
- retrieval evaluation.

## Planned code artifacts

```text
code/
├── embedding_similarity_from_scratch.py
├── faiss_vector_retriever.py
├── qdrant_vector_database.py
├── langchain_retriever_adapter.py
├── reranking_pipeline.py
├── basic_rag.py
├── agentic_retrieval.py
└── evidence_answering.py
```

## Planned theory

```text
theory/
├── 01-rag-fundamentals.md
├── 02-chunking-and-embeddings.md
├── 03-vector-search-and-similarity.md
├── 04-faiss-vs-vector-database.md
├── 05-qdrant-and-metadata-filtering.md
├── 06-retrieval-and-reranking.md
├── 07-agentic-rag.md
└── 08-rag-evaluation.md
```

## Learning progression

```text
Document
   |
   v
Chunk
   |
   v
Embedding
   |
   v
Vector similarity from first principles
   |
   v
FAISS local index
   |
   v
Qdrant persistent vector database
   |
   v
Retriever abstraction / LangChain integration
   |
   v
Agent decides whether/how to retrieve
```

## Milestone

Build an Agent that can decide whether external retrieval is needed, search the correct knowledge source, retry with a rewritten query when evidence is weak, and produce an evidence-grounded answer. The learner should also be able to explain the practical difference between a local FAISS index and a service-style vector database such as Qdrant.

## Key question

> Should retrieval happen for every user message, and what does a vector database actually add beyond nearest-neighbor search over embeddings?

# Stage 04 — RAG & Agentic Retrieval

## Why this stage exists

LLMs do not automatically have reliable access to private, local, or current knowledge. Retrieval-Augmented Generation (RAG) gives a system access to external evidence. Agentic RAG adds another layer: the Agent decides when to retrieve, what source to use, whether the evidence is sufficient, and whether the query should be rewritten.

## Planned topics

- document parsing;
- chunking strategies;
- embeddings;
- vector databases;
- metadata filtering;
- top-k retrieval;
- reranking;
- hybrid retrieval;
- ordinary RAG vs Agentic RAG;
- retrieval routing;
- query rewriting;
- evidence sufficiency checks;
- grounded answering;
- retrieval evaluation.

## Planned code artifacts

```text
code/
├── basic_rag.py
├── vector_retriever.py
├── reranking_pipeline.py
├── agentic_retrieval.py
└── evidence_answering.py
```

## Planned theory

```text
theory/
├── 01-rag-fundamentals.md
├── 02-chunking-and-embeddings.md
├── 03-retrieval-and-reranking.md
├── 04-agentic-rag.md
└── 05-rag-evaluation.md
```

## Milestone

Build an Agent that can decide whether external retrieval is needed, search the correct knowledge source, retry with a rewritten query when evidence is weak, and produce an evidence-grounded answer.

## Key question

> Should retrieval happen for every user message, or should the Agent decide when retrieval is actually necessary?

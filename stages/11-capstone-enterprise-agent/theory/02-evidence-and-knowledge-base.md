# 02 — Evidence Architecture and the Local Knowledge Base

Research Agents fail spectacularly when “retrieved text” is treated as one undifferentiated truth bucket.

## 1. Two evidence classes

```python
EvidenceKind = Literal[
    "local_fulltext",
    "scholarly_metadata",
]
```

`local_fulltext` is text extracted from papers we actually indexed. `scholarly_metadata` is bibliographic discovery returned by Crossref.

## 2. Why metadata is not findings

Suppose Crossref returns:

```text
Title: A Perfect Agent That Never Hallucinates
Year: 2026
DOI: ...
```

We may safely say a work with that title was discovered. We may **not** say its experiments prove perfect factuality without reading evidence that supports that claim.

This is the same trust-boundary lesson from RAG, MCP, and prompt-injection safety: data may inform control, but data does not automatically become authority.

## 3. Corpus bootstrap lifecycle

The repository stores only `data/open_papers.json`. On demand:

```text
manifest
  -> download PDF locally
  -> pypdf text extraction
  -> CorpusDocument
  -> corpus.jsonl
  -> chunk_text
  -> embeddings
  -> InMemoryVectorRetriever
```

Generated PDFs and corpus files are ignored by Git. This keeps the repository lightweight and avoids redistributing third-party PDFs.

## 4. Why start with HashEmbeddingModel?

Because this is still a learning repository. Feature hashing makes every retrieval step inspectable and deterministic.

It is lexical, not a modern semantic embedding model. For production research search, replace the retriever with Stage 04's FAISS/Qdrant + a real embedding model, then rerun retrieval evaluation. The Agent contract does not need to change.

## 5. Do not promote score-zero chunks into evidence

A top-k retriever can return a result even when its similarity is effectively zero. OpenScholar therefore has `min_local_score`; only chunks passing that application-level threshold count toward the substantive-evidence gate.

The threshold itself is backend-specific and must be recalibrated when you change embedding/retrieval systems. The lesson is the gate, not the magic number.

## 6. Evidence normalization

Multiple subqueries can retrieve the same chunk. `normalize_evidence()` fingerprints source/text, removes duplicates, applies a global evidence budget, and renumbers surviving items `[E1]`, `[E2]`, ... . The model never gets to invent which evidence IDs exist.

## 7. Evidence sufficiency gate

```python
local_count = sum(e.kind == "local_fulltext" for e in evidence)
if local_count < config.min_local_evidence:
    status = "insufficient_evidence"
```

Abstention is a feature. A research Agent that confidently fabricates when retrieval fails is just autocomplete wearing a lab coat.

# Chunking and Embeddings

RAG usually cannot throw an entire knowledge base into one prompt. We first turn documents into retrievable units.

```text
Document
   -> chunks
   -> vectors
   -> searchable index
```

Two design questions dominate this step:

1. What should one chunk contain?
2. How should a chunk be represented for retrieval?

---

## 1. Chunking is not just `text[:500]`

A chunk is a retrievable unit of evidence.

If chunks are too small:

```text
"The refund period is"
"30 days for unopened"
"items purchased online."
```

The evidence has been turned into confetti.

If chunks are too large:

```text
entire 80-page policy manual -> one chunk
```

retrieval can find the manual but cannot precisely identify the useful passage, and the generator gets a suitcase full of irrelevant text.

A good chunk preserves enough local meaning while staying focused enough for retrieval.

---

## 2. Overlap protects boundaries

Suppose a fact crosses a boundary:

```text
chunk A: ... refunds are allowed within
chunk B: 30 days if the product is unopened ...
```

A small overlap can preserve the complete statement in at least one chunk.

Tiny-Agent's teaching helper uses token windows:

```python
from tiny_agent import chunk_text

chunks = chunk_text(
    text,
    document_id="refund-policy",
    chunk_size=80,
    overlap=10,
    metadata={"source": "refund-policy-v7"},
)
```

The implementation is intentionally simple. Production chunking may need:

- headings and sections;
- sentence boundaries;
- code blocks;
- tables;
- PDFs and page numbers;
- tokenizer-aware limits;
- semantic boundaries;
- parent/child chunk relationships.

---

## 3. Metadata is part of retrieval design

Do not store only the text.

Useful metadata may include:

```python
{
    "source": "refund-policy-v7.pdf",
    "page": 12,
    "department": "sales",
    "language": "en",
    "effective_date": "2026-07-01",
}
```

Why?

Because sometimes similarity is not enough.

A query may need:

```text
semantic relevance
AND
language == "en"
AND
effective_date is current
```

Embeddings are not a replacement for business filters.

---

# 4. What is an embedding?

An embedding maps an object, often text, into a vector:

```text
"Qdrant supports payload filtering"
        |
        v
[0.13, -0.04, 0.78, ..., 0.21]
```

A useful semantic embedding model places texts with similar meaning near each other in vector space.

For example, ideally:

```text
"How do I cancel my order?"
```

should be close to:

```text
"Order cancellation instructions"
```

even if the exact words are not identical.

---

## 5. Our teaching embedding is deliberately not magical

Tiny-Agent includes:

```python
HashEmbeddingModel
```

It uses deterministic feature hashing over tokens.

That means it is mostly lexical:

```text
shared words -> more similar
```

It does **not** truly understand that:

```text
car
```

and:

```text
automobile
```

can mean similar things.

Why use it at all?

Because it lets us inspect the entire retrieval pipeline offline:

```text
text
 -> vector
 -> cosine similarity
 -> top-k
```

without downloading a model or paying for an embedding API.

Think of it as the training wheels on the bicycle. Useful for learning balance; not how you win the Tour de France.

---

## 6. Provider-neutral embedding boundary

Tiny-Agent uses an interface:

```python
class EmbeddingModel(Protocol):
    @property
    def dimension(self) -> int:
        ...

    def embed_documents(self, texts):
        ...

    def embed_query(self, text):
        ...
```

The retriever should not care whether vectors come from:

- a hosted API;
- a sentence-transformer model;
- a local GPU service;
- a deterministic test embedding.

This is the same architectural idea used earlier for `Model` and `StructuredDecisionModel`.

---

## 7. Dimension must stay consistent

If your collection is built with 768-dimensional document vectors, querying it with a 1536-dimensional vector makes no mathematical sense.

```text
[768 values]
    vs
[1536 values]
```

is not a valid dot product.

This sounds obvious, but embedding-model migrations make it a real production concern.

The index schema and embedding model version belong together.

---

## 8. Query and document embedding can be asymmetric

Some embedding systems use different task instructions or encoders for:

```text
document embedding
```

and:

```text
query embedding
```

That is why Tiny-Agent exposes two methods instead of only:

```python
embed(text)
```

The interface leaves room for models where query/document treatment differs.

---

## 9. Chunk size is an empirical parameter

There is no universal law:

```text
chunk_size = 512
```

because someone on a blog used 512.

Choose it based on:

- document structure;
- expected question granularity;
- embedding model behavior;
- retrieval metrics;
- context budget;
- answer requirements.

Then evaluate it.

"It feels about right" is acceptable for a first demo, not for a production benchmark.

---

## Completion check

You should be able to explain:

1. Why chunking quality affects retrieval quality.
2. Why overlap can help boundary facts.
3. Why metadata is not redundant with embeddings.
4. What semantic embeddings are intended to represent.
5. Why Tiny-Agent's hash embedding is only a teaching/test model.
6. Why query and document embeddings may use different methods.

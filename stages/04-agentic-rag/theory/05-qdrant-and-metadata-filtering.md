# Qdrant and Metadata Filtering

Qdrant gives us a concrete example of what a vector database adds beyond nearest-neighbor math.

The core data model is straightforward:

```text
Collection
   |
   +-- Point
       ├── id
       ├── vector
       └── payload
```

---

## 1. Collection

A collection groups points that share vector configuration.

For example:

```python
client.create_collection(
    collection_name="policies",
    vectors_config=models.VectorParams(
        size=embedding_model.dimension,
        distance=models.Distance.COSINE,
    ),
)
```

The vector dimension and distance metric are part of the collection's retrieval contract.

Changing embedding models is therefore not merely changing one Python function. It can require a migration/re-indexing plan.

---

## 2. Point

A point connects three things:

```text
identity + vector + payload
```

Example:

```python
models.PointStruct(
    id="...",
    vector=[...],
    payload={
        "source": "refund-policy-v7.pdf",
        "department": "sales",
        "language": "en",
        "text": "Refunds are accepted within 30 days...",
    },
)
```

Tiny-Agent stores the chunk text and metadata in payload so search results can be reconstructed as `DocumentChunk` objects.

---

## 3. Payload is not decorative

Payload lets your retrieval policy express facts that should not be left to embeddings.

Suppose your corpus contains:

```text
Policy 2024
Policy 2025
Policy 2026
```

They may all be semantically similar.

But the application may require:

```text
version == 2026
```

Trying to hope the embedding "understands which policy is legally current" is a terrible authorization/versioning strategy.

Use metadata.

---

## 4. Filtering

Qdrant can combine vector search with payload conditions.

Tiny-Agent builds an equality filter like:

```python
models.Filter(
    must=[
        models.FieldCondition(
            key="department",
            match=models.MatchValue(value="legal"),
        )
    ]
)
```

and passes it to:

```python
client.query_points(
    collection_name="policies",
    query=query_vector,
    query_filter=query_filter,
    limit=top_k,
)
```

Official references:

- [Qdrant Filtering](https://qdrant.tech/documentation/search/filtering/)
- [Qdrant Payload](https://qdrant.tech/documentation/concepts/payload/)
- [Qdrant Local Quickstart](https://qdrant.tech/documentation/quickstart/)

---

## 5. Metadata filters can be security boundaries

Imagine a multi-tenant product:

```text
customer A documents
customer B documents
```

A query from customer A must not retrieve customer B's documents just because their vectors are similar.

Conceptually:

```text
semantic similarity
AND
tenant_id == current_tenant
```

That filter should be application-owned policy derived from authenticated identity, not a free-form suggestion from the LLM.

Do **not** let the model invent:

```python
{"tenant_id": "whatever-I-feel-like"}
```

and treat it as authorization.

Stage 07 will formalize permission boundaries, but RAG needs the idea now.

---

## 6. Filter before or after vector search?

In a database with native filtered vector search, filtering can participate in the retrieval operation.

A simplistic FAISS wrapper might instead:

```text
search top 10 globally
    -> remove wrong department
    -> maybe only 1 result remains
```

That can hurt recall.

Another brute-force implementation could filter the candidate set first and then rank only allowed chunks.

The correct design depends on backend capabilities and scale.

This is one reason database-native filtering matters.

---

## 7. Payload indexes matter at scale

Qdrant's documentation recommends creating payload indexes for fields frequently used in filters.

Why?

Because a filter is not magically free.

If you repeatedly ask:

```text
where department == "legal"
```

then indexing that field can make filtering substantially more efficient.

Again, "vector database" still obeys ordinary database engineering laws. Adding embeddings did not repeal indexing.

---

## 8. Local mode vs remote service

For learning/tests:

```python
client = QdrantClient(":memory:")
```

For a real service:

```python
client = QdrantClient(url="http://localhost:6333")
```

or a secured remote/cloud endpoint.

A production deployment must additionally consider:

- authentication;
- TLS/network boundaries;
- backups;
- replication;
- capacity;
- monitoring;
- payload schema/indexes;
- retention and deletion.

Stage 04 teaches retrieval semantics, not the full database operations course.

---

## 9. Qdrant does not generate good embeddings for you by definition

A vector database stores/searches vectors. Retrieval quality still depends heavily on:

- chunking;
- embedding model;
- query formulation;
- filters;
- top-k;
- reranking;
- corpus quality.

Buying a better filing cabinet does not improve badly written documents inside it.

---

## Completion check

You should be able to explain:

1. Collection vs Point vs Payload.
2. Why vector dimension belongs to collection/index design.
3. Why metadata filtering cannot simply be delegated to semantic similarity.
4. Why tenant/security filters must be application-owned.
5. Why payload indexes matter.
6. Local in-memory Qdrant vs remote production Qdrant.

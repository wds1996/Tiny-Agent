# FAISS vs a Vector Database

A beginner often hears:

```text
FAISS
Qdrant
vector database
```

and mentally files them under:

> "Three ways to store embeddings. Probably interchangeable."

That mental model is too coarse.

---

## 1. FAISS is primarily a similarity-search library

FAISS provides efficient algorithms and indexes for searching dense vectors.

Its central object is an **index**:

```python
index = faiss.IndexFlatIP(dimension)
index.add(vectors)
scores, ids = index.search(query, k)
```

It is extremely useful, but the index itself is not your complete application database.

You still need to decide how to manage things such as:

- original text;
- arbitrary document metadata;
- application IDs;
- authorization data;
- document deletion/versioning;
- persistence and backup;
- service APIs;
- concurrent writers;
- operational monitoring.

Official reference:

- [FAISS project / Wiki](https://github.com/facebookresearch/faiss/wiki)

---

## 2. Notice what our FAISS adapter stores

Tiny-Agent's adapter keeps:

```text
FAISS index
    -> vectors and vector positions

Python list
    -> DocumentChunk objects
```

When FAISS returns index position `7`, application code maps:

```text
7 -> chunks[7]
```

That mapping is an application responsibility in this minimal design.

This is an important lesson hidden by many high-level wrappers.

---

## 3. A vector database adds database responsibilities

A system such as Qdrant organizes vectors as persisted/queryable records with associated payload.

Conceptually:

```text
Point
├── id
├── vector
└── payload
    ├── source
    ├── language
    ├── department
    └── text
```

Then retrieval can express:

```text
nearest vectors
AND language == "en"
AND department == "legal"
```

without pretending those business constraints are encoded in semantic geometry.

---

## 4. Comparison

| Concern | FAISS | Service-style vector DB such as Qdrant |
|---|---|---|
| Dense similarity search | Core strength | Core strength |
| Local in-process use | Excellent | Local client mode is available, but production is commonly service-based |
| Arbitrary payload/metadata | Application-managed | Native payload records |
| Metadata filtering | Not the central FAISS abstraction | Native filtering |
| Collections | Application-managed | Native concept |
| CRUD/service API | Build/manage yourself | Database API |
| Persistence/backup/ops | Application concern | Database/storage concern |
| Exact/ANN index algorithms | Rich FAISS ecosystem | Database-managed vector indexes/search |

The table does **not** mean Qdrant is always better.

It means they solve different scopes of the problem.

---

## 5. When FAISS is a great choice

Use a local FAISS index when:

- the corpus fits comfortably in one process/machine;
- you want an inspectable prototype;
- metadata policy is simple;
- extremely low integration overhead matters;
- you are experimenting with vector-search algorithms;
- another datastore already owns the documents/metadata.

For an educational project, this is perfect.

You can see the mechanism without first deploying a service.

---

## 6. When a vector database starts earning its lunch

A service-style vector database becomes more attractive when you need:

- durable shared retrieval state;
- payload filtering;
- multiple application processes;
- operational collection management;
- remote access;
- document updates/deletes;
- indexes managed independently of the Agent process;
- access-control or tenancy metadata;
- scaling and monitoring as infrastructure.

At this point, "just keep a Python list next to FAISS" begins to look like a database slowly trying to hatch from your codebase.

If you keep adding persistence, filters, CRUD, networking, migrations and backups around FAISS, congratulations: you may be accidentally writing your own database.

---

## 7. But Qdrant local mode is still useful for learning

Qdrant Client supports an in-memory local mode:

```python
from qdrant_client import QdrantClient

client = QdrantClient(":memory:")
```

Tiny-Agent uses this in tests so learners can practice:

- collections;
- vector insertion;
- payload;
- filters;
- queries;

without Docker or a cloud account.

Official tutorial:

- [Qdrant Semantic Search 101](https://qdrant.tech/documentation/tutorials-basics/search-beginners-local/)

Do not confuse this convenience mode with the production architecture of a remote persistent Qdrant service.

---

## 8. Retrieval policy still belongs to your application

Moving vectors into Qdrant does not answer:

```text
Should I retrieve at all?
Which collection?
Which tenant?
Which metadata filter?
How many candidates?
Should I rerank?
Is the evidence sufficient?
```

Those are Agent/workflow decisions.

The database executes a retrieval request; it does not define your product policy.

---

## Completion check

You should be able to explain:

1. Why FAISS is not a full vector database by itself.
2. What application responsibilities exist around a FAISS index.
3. What payload/filtering adds.
4. Why Qdrant local mode is useful but not the same as a production remote service.
5. When a lightweight local index can be better than adding database infrastructure.

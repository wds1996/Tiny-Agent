# Qdrant 与 Metadata Filtering

Qdrant 很适合用来理解：vector database 比 nearest-neighbor math 多了什么。

核心 data model：

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

Collection 把共享 vector configuration 的 point 组织在一起：

```python
client.create_collection(
    collection_name="policies",
    vectors_config=models.VectorParams(
        size=embedding_model.dimension,
        distance=models.Distance.COSINE,
    ),
)
```

Vector dimension 与 distance metric 都属于 collection retrieval contract。

因此换 embedding model 往往意味着 migration/re-index，而不是“改一下模型名就完事”。

---

## 2. Point

Point 把三件事连起来：

```text
identity + vector + payload
```

例如：

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

Tiny-Agent 把 chunk text/metadata 放入 payload，从而能把 query result 重新构造成 `DocumentChunk`。

---

## 3. Payload 不是装饰

假设 corpus 同时有：

```text
Policy 2024
Policy 2025
Policy 2026
```

它们 embedding 可能都很像，但 application policy 要求：

```text
version == 2026
```

“希望 embedding 自己理解哪个 policy 在法律上仍有效”是非常糟糕的 versioning/authorization 策略。

这种约束应放 metadata。

---

## 4. Filtering

Qdrant 可以把 vector search 与 payload condition 组合：

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

再传给：

```python
client.query_points(
    collection_name="policies",
    query=query_vector,
    query_filter=query_filter,
    limit=top_k,
)
```

官方资料：

- [Qdrant Filtering](https://qdrant.tech/documentation/search/filtering/)
- [Qdrant Payload](https://qdrant.tech/documentation/concepts/payload/)
- [Qdrant Local Quickstart](https://qdrant.tech/documentation/quickstart/)

---

## 5. Metadata filter 可以是 security boundary

多租户场景：

```text
customer A documents
customer B documents
```

A 的 query 绝不能仅因为 vector 很相似就拿到 B 的文档。

应表达成：

```text
semantic similarity
AND
tenant_id == current_tenant
```

这个 tenant filter 应由 authenticated identity 推导，而不是让 model 自由生成。

错误：

```python
{"tenant_id": "whatever-I-feel-like"}
```

然后把它当 authorization。

Stage 07 会把 permission boundary 系统化，但 RAG 在这里就必须建立这个概念。

---

## 6. Filter before vs after vector search

Native filtered vector search 可以让 filter 参与 retrieval。

简陋 FAISS wrapper 可能只能：

```text
search top 10 globally
    -> remove wrong department
    -> maybe only 1 result remains
```

这样可能严重伤 recall。

另一种 brute-force 方案可以先过滤 allowed candidates，再 rank。

具体设计取决于 backend capability 与规模，这也是 database-native filtering 的价值之一。

---

## 7. Payload index 在规模上很重要

Qdrant 官方建议：经常被过滤的 payload field 应建立 index。

例如频繁：

```text
where department == "legal"
```

filter 并不是魔法免费操作。

Vector database 仍然遵守普通 database engineering：embedding 并没有废除 indexing。

---

## 8. Local mode vs remote service

学习/测试：

```python
client = QdrantClient(":memory:")
```

真实 service：

```python
client = QdrantClient(url="http://localhost:6333")
```

生产还要考虑：

- authentication；
- TLS/network boundary；
- backup；
- replication；
- capacity；
- monitoring；
- payload schema/index；
- retention/deletion。

Stage 04 教 retrieval semantics，不假装顺手教完整数据库运维。

---

## 9. Qdrant 不会自动让 embedding 变好

Vector database 负责 store/search vector。Retrieval quality 仍取决于：

- chunking；
- embedding model；
- query formulation；
- filter；
- top-k；
- reranking；
- corpus quality。

换一个更高级的文件柜，并不会让柜子里写得很差的文件突然更准确。

---

## 完成检查

你应该能解释：

1. Collection vs Point vs Payload；
2. vector dimension 为什么属于 collection/index design；
3. metadata filtering 为什么不能交给 semantic similarity；
4. tenant/security filter 为什么必须 application-owned；
5. payload index 为什么重要；
6. local in-memory Qdrant vs remote production Qdrant。
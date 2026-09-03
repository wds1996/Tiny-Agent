# Chunking 与 Embeddings

RAG 通常不能把整个知识库直接塞进一个 prompt。首先要把文档变成可检索单元：

```text
Document
   -> chunks
   -> vectors
   -> searchable index
```

两个核心设计问题：

1. 一个 chunk 应该包含什么？
2. 一个 chunk 应该如何表示以便 retrieval？

---

## 1. Chunking 不只是 `text[:500]`

Chunk 是 retrievable unit of evidence。

太小：

```text
"The refund period is"
"30 days for unopened"
"items purchased online."
```

证据被切成了五彩纸屑。

太大：

```text
80-page policy manual -> one chunk
```

检索只能找到“整本手册”，无法精准定位 passage，generator 还会收到大量无关文本。

好的 chunk 要保留足够 local meaning，同时足够 focused。

---

## 2. Overlap 保护 boundary fact

如果一个事实跨边界：

```text
chunk A: ... refunds are allowed within
chunk B: 30 days if the product is unopened ...
```

适当 overlap 可让完整事实至少出现在一个 chunk 中。

Tiny-Agent 的教学 helper：

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

Production chunking 还可能考虑：

- heading/section；
- sentence boundary；
- code block；
- table；
- PDF page number；
- tokenizer-aware limit；
- semantic boundary；
- parent/child chunk。

---

## 3. Metadata 是 retrieval design 的一部分

不要只存 text。

例如：

```python
{
    "source": "refund-policy-v7.pdf",
    "page": 12,
    "department": "sales",
    "language": "en",
    "effective_date": "2026-07-01",
}
```

因为很多 retrieval 需求其实是：

```text
semantic relevance
AND
language == "en"
AND
effective_date is current
```

Embedding 不能替代 business filter。

---

## 4. 什么是 embedding

Embedding 把对象（通常是文本）映射成 vector：

```text
"Qdrant supports payload filtering"
        |
        v
[0.13, -0.04, 0.78, ..., 0.21]
```

好的 semantic embedding model 希望让语义相近文本在 vector space 中更接近。

例如：

```text
"How do I cancel my order?"
```

应接近：

```text
"Order cancellation instructions"
```

即使词面并不完全一致。

---

## 5. Tiny-Agent 的教学 embedding 故意不“神奇”

Tiny-Agent 提供：

```python
HashEmbeddingModel
```

它基于 token 做 deterministic feature hashing，更多体现 lexical overlap：

```text
shared words -> more similar
```

它并不真正理解 `car` 与 `automobile` 的语义关系。

为什么还要用？因为它让你可以完全离线观察：

```text
text
 -> vector
 -> cosine similarity
 -> top-k
```

它更像自行车辅助轮：适合学平衡，不适合拿去环法夺冠。

---

## 6. Provider-neutral embedding boundary

Tiny-Agent 定义：

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

Retriever 不应该关心 vector 来自：

- hosted API；
- sentence-transformer；
- local GPU service；
- deterministic test embedding。

这和前面的 `Model` / `StructuredDecisionModel` boundary 是同一设计思想。

---

## 7. Dimension 必须一致

如果 collection 用 768 维 document vectors 构建，却用 1536 维 query vector 搜索，数学上都不是合法 dot product。

因此 embedding model migration 往往与 index schema/re-indexing 绑定，而不是简单换一行 Python。

---

## 8. Query 与 document embedding 可以 asymmetric

某些 embedding 系统会对：

```text
document embedding
```

与：

```text
query embedding
```

使用不同 instruction 或 encoder。

所以 Tiny-Agent 分开暴露 `embed_documents()` 与 `embed_query()`，而不是只设计一个 `embed(text)`。

---

## 9. Chunk size 是 empirical parameter

没有宇宙常数：

```text
chunk_size = 512
```

只是因为某篇博客用了 512。

应该基于：

- document structure；
- question granularity；
- embedding behavior；
- retrieval metrics；
- context budget；
- answer requirement。

然后用数据评估。

---

## 完成检查

你应该能解释：

1. chunking 为什么影响 retrieval；
2. overlap 为什么能保护 boundary fact；
3. metadata 为什么不与 embedding 重复；
4. semantic embedding 想表达什么；
5. HashEmbeddingModel 为什么只适合教学/测试；
6. query/document embedding 为什么可能使用不同方法。
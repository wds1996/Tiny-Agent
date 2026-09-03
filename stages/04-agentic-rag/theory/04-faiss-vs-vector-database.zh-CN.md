# FAISS vs Vector Database

初学者经常把：

```text
FAISS
Qdrant
vector database
```

都归进一个抽屉：“反正都是存 embedding 的。”

这个模型太粗。

---

## 1. FAISS 首先是 similarity-search library

FAISS 的核心对象是 **index**：

```python
index = faiss.IndexFlatIP(dimension)
index.add(vectors)
scores, ids = index.search(query, k)
```

它非常强，但 index 本身不是完整 application database。

应用仍要自行管理：

- original text；
- arbitrary metadata；
- application IDs；
- authorization data；
- document delete/versioning；
- persistence/backup；
- service API；
- concurrent writer；
- operational monitoring。

参考：

- [FAISS project / Wiki](https://github.com/facebookresearch/faiss/wiki)

---

## 2. 看 Tiny-Agent FAISS adapter 就能看懂这个边界

最小设计中：

```text
FAISS index
    -> vectors + vector positions

Python list
    -> DocumentChunk objects
```

FAISS 返回位置 `7` 后，application 做：

```text
7 -> chunks[7]
```

这个 mapping 是 application responsibility。

很多高层 wrapper 会把它藏起来，所以自己写一遍很有价值。

---

## 3. Vector database 增加 database responsibilities

Qdrant 这类系统把 vector 作为可持久化、可查询 record，并关联 payload：

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

于是 retrieval 可以表达：

```text
nearest vectors
AND language == "en"
AND department == "legal"
```

不需要幻想 embedding geometry 会自动编码所有业务约束。

---

## 4. 对比

| Concern | FAISS | Qdrant 等 service-style vector DB |
|---|---|---|
| Dense similarity search | 核心能力 | 核心能力 |
| Local in-process use | 很适合 | 有 local mode，但生产常是 service |
| Arbitrary payload/metadata | application-managed | native payload |
| Metadata filtering | 非核心抽象 | native filtering |
| Collections | application-managed | native concept |
| CRUD/service API | 自己构建 | database API |
| Persistence/backup/ops | application concern | database/storage concern |
| Exact/ANN algorithm | 丰富 FAISS ecosystem | database-managed vector index/search |

这不表示 Qdrant 永远“更高级”，只是 scope 不同。

---

## 5. FAISS 什么时候非常合适

适合：

- corpus 能放在单机/单进程；
- prototype 要求可检查；
- metadata policy 简单；
- 希望 integration overhead 极低；
- 正在实验 vector-search algorithm；
- documents/metadata 已由另一个 datastore 管理。

对教学项目尤其合适：不用先部署数据库就能看到机制。

---

## 6. Vector database 什么时候开始值得引入

当你需要：

- durable shared retrieval state；
- payload filtering；
- multiple application processes；
- collection operations；
- remote access；
- document updates/deletes；
- index 独立于 Agent process；
- tenancy/access metadata；
- scaling/monitoring。

如果你不断给 FAISS 外面补 persistence、CRUD、filter、network、migration、backup，恭喜，你可能正在亲手孵化一个数据库。

---

## 7. Qdrant local mode 对学习仍然很好

```python
from qdrant_client import QdrantClient

client = QdrantClient(":memory:")
```

Tiny-Agent 用它做 tests/tutorial，因此不用 Docker/cloud account 就能练：

- collection；
- insertion；
- payload；
- filter；
- query。

官方教程：

- [Qdrant Semantic Search 101](https://qdrant.tech/documentation/tutorials-basics/search-beginners-local/)

但 local mode 不等于 remote persistent production architecture。

---

## 8. Retrieval policy 仍归 application

把 vector 搬进 Qdrant 并不会替你回答：

```text
Should I retrieve?
Which collection?
Which tenant?
Which metadata filter?
How many candidates?
Should I rerank?
Is evidence sufficient?
```

Database 执行 retrieval request；它不定义产品策略。

---

## 完成检查

你应该能解释：

1. 为什么 FAISS 本身不是完整 vector database；
2. FAISS index 周围还需要哪些 application responsibility；
3. payload/filtering 带来什么；
4. Qdrant local mode 与 production remote service 的区别；
5. 什么情况下 lightweight local index 反而更合适。
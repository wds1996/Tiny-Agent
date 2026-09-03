# Stage 04 — RAG 与 Agentic Retrieval

Stage 04 让 Tiny-Agent 获得访问外部知识的能力，并学习如何把 retrieval 放进一个受控的 Agent workflow。

教学顺序刻意从底层开始：

```text
Document
   -> Chunk
   -> Embedding
   -> 从第一性原理理解 cosine / top-k
   -> framework-free retriever
   -> FAISS local vector index
   -> Qdrant vector database + metadata filtering
   -> LangChain Retriever adapter
   -> reranking
   -> Basic RAG
   -> bounded Agentic RAG
   -> retrieval / grounding evaluation
```

目标不是背 `similarity_search()`，而是理解它下面到底发生了什么、何时该检索、以及检索证据很弱时系统应该怎么办。

---

# 前置要求

完成 Stage 00–03，或至少理解：

- messages 与 Function Calling；
- provider-neutral interfaces；
- ReAct 与 Tool observation；
- deterministic Workflow vs Agent；
- structured control decision；
- Planner–Executor / bounded retry；
- explicit Agent state 与 LangGraph orchestration。

本阶段继续沿用同一条工程原则：

> **Model output 可以提出 retrieval decision；application code 才拥有 data access、filter、budget 与 execution。**

---

# 学习目标

完成本阶段后，你应该能够：

1. 解释 RAG = retrieve → augment → generate；
2. 区分模型 parametric memory 与 runtime external evidence；
3. 解释为什么 RAG 不自动等于 Agent；
4. 设计 chunk，并说明 chunk size / overlap 的取舍；
5. 定义 embedding interface，并解释 vector dimension；
6. 从公式实现 cosine similarity；
7. 区分 inner product 与 cosine，以及 normalization 的作用；
8. 自己实现 exact brute-force top-k retrieval；
9. 用 FAISS `IndexFlatIP` 在 normalized vectors 上实现 cosine ranking；
10. 解释为什么 FAISS 是 vector-search library，而不是完整 application database；
11. 使用 Qdrant collection、point、payload 与 metadata filter；
12. 解释 security/tenant filter 为什么必须 application-owned；
13. 把 Tiny-Agent Retriever 适配成 LangChain `BaseRetriever`；
14. 区分 Retriever 与 Vector Store；
15. 区分 candidate retrieval 与 reranking；
16. 解释 dense、sparse、hybrid retrieval；
17. 构建 Basic two-step RAG；
18. 构建 bounded Agentic RAG：retrieval decision、query rewrite、evidence sufficiency；
19. evidence 仍不足时强制 abstain；
20. 用 Recall@k、MRR 等指标把 retrieval evaluation 与 generation evaluation 分开。

---

# Part A — 从第一性原理学 RAG 与 retrieval

按顺序：

1. [RAG Fundamentals](theory/01-rag-fundamentals.zh-CN.md)
2. [Chunking 与 Embeddings](theory/02-chunking-and-embeddings.zh-CN.md)
3. [Vector Search 与 Similarity](theory/03-vector-search-and-similarity.zh-CN.md)
4. [`code/embedding_similarity_from_scratch.py`](code/embedding_similarity_from_scratch.py)
5. [`../../src/tiny_agent/retrieval.py`](../../src/tiny_agent/retrieval.py)
6. [`../../tests/test_retrieval.py`](../../tests/test_retrieval.py)

到这里，你应该能在完全不依赖 FAISS、Qdrant、LangChain 的情况下解释 retrieval。

---

# Part B — FAISS 与 vector database

7. [FAISS vs Vector Database](theory/04-faiss-vs-vector-database.zh-CN.md)
8. [`code/faiss_vector_retriever.py`](code/faiss_vector_retriever.py)
9. [Qdrant 与 Metadata Filtering](theory/05-qdrant-and-metadata-filtering.zh-CN.md)
10. [`code/qdrant_vector_database.py`](code/qdrant_vector_database.py)
11. [`../../src/tiny_agent/retrievers/faiss.py`](../../src/tiny_agent/retrievers/faiss.py)
12. [`../../src/tiny_agent/retrievers/qdrant.py`](../../src/tiny_agent/retrievers/qdrant.py)

必须记住：

```text
FAISS
  -> dense-vector similarity-search library / local index

Qdrant
  -> vector database：collection + payload + filter + persistence/service boundary
```

---

# Part C — Framework integration 与 reranking

13. [`code/langchain_retriever_adapter.py`](code/langchain_retriever_adapter.py)
14. [`../../src/tiny_agent/retrievers/langchain_adapter.py`](../../src/tiny_agent/retrievers/langchain_adapter.py)
15. [Retrieval 与 Reranking](theory/06-retrieval-and-reranking.zh-CN.md)
16. [`code/reranking_pipeline.py`](code/reranking_pipeline.py)

LangChain 故意放在 Retriever 机制之后。

心智模型：

```text
Tiny-Agent Retriever
    query -> ranked SearchResult objects

LangChain BaseRetriever
    query -> Document objects
```

Adapter 提供 interoperability，但不改变 retrieval 的基本语义。

---

# Part D — Basic RAG 到 Agentic RAG

17. [`code/basic_rag.py`](code/basic_rag.py)
18. [Agentic RAG](theory/07-agentic-rag.zh-CN.md)
19. [`code/agentic_retrieval.py`](code/agentic_retrieval.py)
20. [`code/evidence_answering.py`](code/evidence_answering.py)
21. [`../../src/tiny_agent/rag.py`](../../src/tiny_agent/rag.py)
22. [`../../tests/test_rag.py`](../../tests/test_rag.py)

能力演进：

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

23. [RAG Evaluation](theory/08-rag-evaluation.zh-CN.md)
24. [`code/retrieval_evaluation.py`](code/retrieval_evaluation.py)
25. [`../../tests/test_stage04_vector_backends.py`](../../tests/test_stage04_vector_backends.py)
26. [复习题](exercises/review-questions.zh-CN.md)

不要只看 final answer。至少拆成：

```text
retrieval quality
    Recall@k / Precision@k / MRR / ranking analysis

vs

generation quality
    correctness / groundedness / unsupported claims / abstention
```

---

# 安装

Framework-free core：

```bash
pip install -e ".[dev]"
```

Stage 04 optional integration：

```bash
pip install -e ".[stage04]"
```

Stage 04 tests：

```bash
pip install -e ".[dev,stage04]"
```

同时安装 Stage 03/04：

```bash
pip install -e ".[dev,stage03,stage04]"
```

当前 Stage 04 optional dependencies：

```text
numpy
faiss-cpu
qdrant-client
langchain
```

---

# 关于 embeddings 的重要说明

Tiny-Agent 提供：

```python
HashEmbeddingModel
```

它用于 deterministic offline learning/test，**不是 neural semantic embedding model**。

它主要奖励 lexical token overlap，目的是让你离线观察：

```text
text -> vector -> similarity -> top-k
```

而不用下载模型或调用 embedding API。

真实 RAG 应把真正 embedding model 接到同一个 `EmbeddingModel` interface 后，再在自己的 retrieval dataset 上评估。

如果 `HashEmbeddingModel` 觉得 `car` 和 `automobile` 互不认识，不要惊讶。它是来教 vector plumbing 的，不是来参加语言学奥赛的。

---

# Stage architecture

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

LangChain interoperability 通过 adapter 放在 core 旁边，而不是让 `tiny_agent` 的基础 import 强依赖 LangChain。

---

# 外部学习资源

## RAG foundations

- [Lewis et al. — Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)
- [LangChain Retrieval](https://docs.langchain.com/oss/python/langchain/retrieval)
- [LangChain Semantic Search tutorial](https://docs.langchain.com/oss/python/langchain/knowledge-base)

## FAISS

- [FAISS official repository](https://github.com/facebookresearch/faiss)
- [FAISS Wiki](https://github.com/facebookresearch/faiss/wiki)
- [MetricType and distances](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances)
- [FAISS indexes](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes)
- [Guidelines to choose an index](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index)

## Qdrant

- [Qdrant Semantic Search 101](https://qdrant.tech/documentation/tutorials-basics/search-beginners-local/)
- [Qdrant Local Quickstart](https://qdrant.tech/documentation/quickstart/)
- [Payload](https://qdrant.tech/documentation/concepts/payload/)
- [Filtering](https://qdrant.tech/documentation/search/filtering/)
- [Qdrant interfaces](https://qdrant.tech/documentation/interfaces/)

## LangChain Retriever

- [Retriever integrations](https://docs.langchain.com/oss/python/integrations/retrievers)
- [Semantic search / Retriever tutorial](https://docs.langchain.com/oss/python/langchain/knowledge-base)

建议初学顺序：

```text
1. Tiny-Agent RAG fundamentals
2. chunking + embeddings
3. vector similarity
4. embedding_similarity_from_scratch.py
5. FAISS MetricType docs
6. faiss_vector_retriever.py
7. Qdrant Semantic Search 101
8. qdrant_vector_database.py
9. LangChain Retriever docs
10. langchain_retriever_adapter.py
11. reranking
12. Basic RAG
13. Agentic RAG
14. retrieval evaluation
```

---

# 可运行示例

Framework-free：

```bash
python stages/04-agentic-rag/code/embedding_similarity_from_scratch.py
python stages/04-agentic-rag/code/reranking_pipeline.py
python stages/04-agentic-rag/code/basic_rag.py
python stages/04-agentic-rag/code/agentic_retrieval.py
python stages/04-agentic-rag/code/evidence_answering.py
python stages/04-agentic-rag/code/retrieval_evaluation.py
```

Optional dependencies：

```bash
python stages/04-agentic-rag/code/faiss_vector_retriever.py
python stages/04-agentic-rag/code/qdrant_vector_database.py
python stages/04-agentic-rag/code/langchain_retriever_adapter.py
```

---

# 本阶段明确不宣称什么

Stage 04 不是完整 enterprise-search platform。以下仍被简化或留到后面：

- production PDF/OCR/document ingestion；
- neural embedding provider benchmark；
- large-scale ANN tuning；
- production Qdrant deployment/backup/security；
- sophisticated BM25/hybrid engine；
- cross-encoder/LLM reranker；
- citation rendering UI；
- production prompt-injection defense；
- full RAG observability/evaluation platform；
- access-control architecture。

---

# 面试必须能说清楚

> **RAG 是 runtime retrieval external evidence + generation，不等于 vector database。**

> **Retriever 是 query-to-evidence interface；Vector Store 只是 Retriever 背后的一种 storage/search implementation。**

> **FAISS 主要是 dense-vector similarity-search library；vector database 还加入 payload、filter、collection、persistence 与 service operation。**

> **FAISS 用 inner product 做 cosine ranking 时，database/query vector 都要先 normalize。**

> **Metadata filter 表达 embedding similarity 不该负责的约束，尤其 tenant/security/version。**

> **Agentic RAG 增加 model-driven retrieval decision、query rewrite 与 evidence check，但 retriever access、budget、stopping condition 仍归 application。**

> **Retrieval 与 generation 要分开评估；candidate retrieval 没返回相关 chunk，reranker/generator 后面都救不回来。**

---

# Milestone

Stage 04 完成标准：

1. 不用框架实现 exact vector retrieval；
2. 解释 cosine 与 normalized inner-product search；
3. 会用 FAISS，并知道它不负责什么；
4. 用 Qdrant local mode + payload filtering；
5. 把 custom retriever 适配到 LangChain；
6. 解释 candidate retrieval、hybrid retrieval、reranking；
7. 实现 Basic RAG；
8. 实现 bounded Agentic RAG + query rewrite + evidence sufficiency；
9. evidence 不足时 abstain；
10. 用小型 deterministic evaluation set 评估 retrieval。
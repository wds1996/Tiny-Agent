# Stage 04 复习题与练习

请先运行 Stage 04 示例，再做这些题。尽量先不翻笔记。

---

# Part A — 概念检查

1. 为什么 RAG 不等于 vector database？
2. 为什么 Retriever 比 Vector Store 更一般？
3. 为什么普通 two-step RAG 仍可以是 deterministic Workflow，而不是 Agent？
4. chunk overlap 解决什么问题？
5. 为什么 very large chunk 即使包含答案也可能损害 retrieval？
6. metadata 为什么不与 embeddings 重复？
7. cosine similarity 与 inner product 有什么区别？
8. normalized inner-product search 为什么可以复现 cosine ranking？
9. `top_k=5` 到底保证了什么？
10. `HashEmbeddingModel` 为什么不适合 production semantic embedding？
11. embedding-model migration 时，哪些 application/index state 必须同步迁移？
12. FAISS 不是完整 vector database，为什么仍然很有价值？
13. Qdrant payload 比单纯 vector 多了什么？
14. tenant/authorization filter 为什么不能直接来自任意 LLM output？
15. candidate retrieval 与 reranking 各自优化什么？
16. dense 与 sparse retrieval 为什么互补？
17. `top_k` 增大为什么可能让 generation 更差？
18. 什么使 retrieval 变得 Agentic？
19. query rewriting 为什么必须有 budget？
20. 为什么 `insufficient_evidence` 有时是最佳结果？
21. retrieved document 为什么必须当作 untrusted data？
22. retrieval quality 与 grounded answer quality 为什么要分开评估？
23. Recall@k 测什么？
24. MRR 奖励什么？
25. 为什么 evaluation set 应包含正确行为是 abstention 的问题？

---

# Part B — Trace pipeline

给定：

```text
question
  -> embedding
  -> FAISS top 20
  -> metadata post-filter
  -> rerank top 5
  -> answer
```

回答：

1. 如果唯一 allowed document 在 FAISS 排名第 25，会发生什么？
2. database-native filtered vector search 如何改变这个 failure mode？
3. 哪一层应该 enforce `tenant_id`？
4. 哪一层适合偏好“更新但仍 allowed”的 policy version？
5. 哪些 metrics 能判断 first-stage retriever 是否 bottleneck？

---

# Part C — Coding exercises

## Exercise 1 — Better chunker

扩展 `chunk_text()`：优先按 paragraph boundary 切分，必要时再 fallback 到 token window。

要求：

- preserve source metadata；
- stable chunk IDs；
- test empty paragraphs；
- 说明 paragraph chunking 如何改变 retrieval behavior。

## Exercise 2 — Thresholded retrieval

为 `InMemoryVectorRetriever` 增加 optional `min_score`。

思考：

- threshold 应在 Retriever 还是 RAG Workflow？
- 不同 embedding model 的 score 能直接比较吗？
- 你会如何调 threshold？

## Exercise 3 — Keyword retriever

实现最小 lexical retriever：

```python
query -> token overlap -> ranked SearchResult
```

比较它与 `HashEmbeddingModel` retrieval 的 failure mode。

## Exercise 4 — Reciprocal Rank Fusion

融合 lexical/vector ranking：

```python
for ranking in rankings:
    for rank, document in enumerate(ranking, start=1):
        score[document] += 1 / (60 + rank)
```

测试：同时在多个 ranking 靠前的 document 应被提升。

## Exercise 5 — Qdrant filter policy

Qdrant demo 增加：

```text
tenant-a
tenant-b
```

写测试证明：当 application 提供 authenticated tenant filter 后，tenant-a query 永远不能拿到 tenant-b evidence。

然后解释为什么让 LLM 自己决定这个 filter 是 security bug。

## Exercise 6 — Agentic source routing

让 `AgenticRAGWorkflow` 在两个 application-owned retriever 中选：

```text
product_docs
engineering_docs
```

Model 只能输出 schema-constrained source enum；application 把 enum 映射成真实 Retriever。

不要允许 model 提供任意 URL/database connection string。

## Exercise 7 — Detect rewrite loops

构造 scripted decision：

```text
query A -> query B -> query A
```

确认 workflow 能 stop，而不是无限循环。

## Exercise 8 — Retrieval evaluation

创建至少 10 组 query/relevant-chunk，比较：

- Recall@1；
- Recall@3；
- MRR；
- average retrieval latency。

然后修改 chunk size，再比较。

---

# Part D — 面试题

### Q1. FAISS 和 Qdrant 有什么区别？

强答案要讲 scope：

```text
FAISS -> dense-vector similarity-search/index library
Qdrant -> vector database/service with vectors + payload + filters + collection/database operations
```

### Q2. RAG 为什么能降低幻觉？是否一定不会幻觉？

RAG 可以引入 external grounding，但仍可能因为 bad retrieval、irrelevant evidence、prompt injection、unsupported generation 出错。它降低某些 hallucination failure mode，不是数学保证。

### Q3. Agentic RAG 比普通 RAG 多什么？

应提到：conditional retrieval、source/query decision、bounded rewrite、evidence sufficiency，以及带来的 cost/latency/reliability trade-off。

### Q4. 为什么 `top_k` 不能越大越好？

应提到：recall 与 irrelevant context 的取舍、token cost、latency、contradiction、injection surface。

### Q5. Final answer 错了，如何定位 RAG？

建议顺序：

```text
inspect parsing/chunks
-> inspect retrieval ranking
-> test reranking/filtering
-> test generator with oracle evidence
-> inspect final groundedness
```

---

# Completion challenge

不用 LangChain prebuilt RAG helper，自己构建一个 small knowledge Agent：

1. chunk 3–5 个 local text document；
2. 通过 Tiny-Agent `EmbeddingModel` interface embedding；
3. 用 Qdrant local mode 存储/搜索；
4. 使用至少一个 application-owned metadata filter；
5. structured decision 判断是否需要 retrieval；
6. 最多一次 query rewrite；
7. evidence insufficient 时 abstain；
8. 返回 query history 与 evidence IDs；
9. 至少 10 个问题上评估 Recall@3。

如果每一行代码、每一个 trust/control boundary 都能解释清楚，Stage 04 才真正学完。
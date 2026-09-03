# Vector Search 与 Similarity

当 document/query 都变成 vector 后，retrieval 就变成 ranking problem：

```text
query vector
    -> 与 document vectors 比较
    -> 按 similarity 排序
    -> 返回 top-k
```

---

## 1. Cosine similarity

对向量 `x`、`y`：

```text
cosine(x, y) = dot(x, y) / (||x|| * ||y||)
```

直觉：

- 接近 `1`：方向相近；
- 接近 `0`：方向大致无关；
- 接近 `-1`：方向相反。

Tiny-Agent 直接实现公式：

```python
from tiny_agent import cosine_similarity

score = cosine_similarity(
    [1.0, 0.0],
    [0.8, 0.2],
)
```

---

## 2. 为什么 normalization 很重要

若向量已 L2-normalized：

```text
||x|| = ||y|| = 1
```

则：

```text
cosine(x, y) = dot(x, y)
```

因此 FAISS 可以在 database/query vector 都 normalize 后，用 inner-product search 实现 cosine-style ranking。

官方参考：

- [MetricType and distances](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances)

Tiny-Agent FAISS adapter：

```python
faiss.normalize_L2(matrix)
index = faiss.IndexFlatIP(dimension)
index.add(matrix)
```

Query 也要 normalize。

---

## 3. Inner product 不自动等于 cosine

常见误解：

```text
IndexFlatIP == cosine similarity
```

不准确。

没有 normalization 时，inner product 还受 vector magnitude 影响。

本阶段正确关系是：

```text
normalized vectors
+
inner-product search
=
cosine-similarity ranking
```

---

## 4. Top-k 是 ranking，不是真理

如果返回：

```text
1. chunk A  score=0.83
2. chunk B  score=0.78
3. chunk C  score=0.63
```

`top_k=3` 只表示：

> 在当前 scoring system 下，返回最高的三个 candidate。

不表示：

> 这三个 passage 一定 relevant，更不表示 sufficient。

所以后面还可能需要：

- metadata filter；
- score threshold；
- reranking；
- evidence-sufficiency check。

---

## 5. 先学 exact search

100 个 chunk 的教学 corpus，最简单可靠 baseline 就是 brute force：

```python
for chunk_vector in all_vectors:
    score = cosine(query_vector, chunk_vector)

sort_by_score()
return top_k
```

Tiny-Agent `InMemoryVectorRetriever` 就这么做。

价值在于：

- inspectable；
- exact；
- deterministic；
- 可作为 optimized index 的比较 baseline。

---

## 6. 那为什么还要 FAISS

因为 corpus 大后，逐 vector 扫描成本会上升。

FAISS 提供高效 vector index / similarity-search algorithm；有 exact index，也有用 recall 换 speed/memory 的 approximate index。

Stage 04 从：

```python
faiss.IndexFlatIP
```

开始，因为 Flat exact search 最容易理解。

我们不会一上来就背 IVF/PQ/HNSW。还没学会开车就先研究赛车尾翼，是 vector-search 学习的经典绕路方式。

官方资料：

- [FAISS Wiki](https://github.com/facebookresearch/faiss/wiki)
- [FAISS indexes](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes)
- [Guidelines to choose an index](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index)

---

## 7. Exact vs approximate nearest-neighbor

### Exact

```text
比较所有 candidates
-> 在当前 metric 下得到 exact ranking
-> corpus 越大 compute 越高
```

### Approximate

```text
利用 index/search structure
-> 只检查更少 candidates
-> 更快/更可扩展
-> 可能漏掉真实 nearest neighbor
```

真正的问题不是“哪个 index 名字更高级”，而是：

> 你的 recall、latency、memory、update pattern、scale 需要什么？

---

## 8. Similarity score 是 backend/model-specific

不要直接把：

```text
FAISS score 0.81
```

与另一个 reranker 的 `0.81`，或另一 embedding model 的 `0.81` 当同一尺度。

Score 的定义、分布、normalization、calibration 都可能不同。

Threshold 必须在自己的 retrieval dataset 上验证。

---

## 9. 一个略荒唐的比喻

Vector search 像让夜店门口保安根据你的描述给排队的人排序：

> 哪些人最像我要找的人？

他能 rank，但 ranking 不等于身份证明。

`top_k=5` 是“这五个最像”，不是“这五个一定正确”。Reranking 与 evidence check 才是下一轮审问。

---

## 完成检查

你应该能解释：

1. cosine similarity vs inner product；
2. normalized inner product 为什么可以做 cosine ranking；
3. top-k 为什么不是 relevance guarantee；
4. exact vs ANN；
5. 为什么先学 brute force 与 `IndexFlatIP`；
6. similarity threshold 为什么必须评估而不是猜。
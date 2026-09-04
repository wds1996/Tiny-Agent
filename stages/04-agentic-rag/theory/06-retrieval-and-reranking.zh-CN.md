# Retrieval、Hybrid Search、Query Transformation、Diversity 与 Reranking

成熟 retrieval pipeline 很少让一个 scoring function 负责全部工作。通常会分开 **candidate recall** 与 **final evidence selection**：

```text
query
  -> one or more candidate retrievers
  -> fuse / filter
  -> diversify
  -> rerank
  -> small evidence set for the model
```

如果唯一的检索策略只是把 `top_k` 从 10 调到 100，那不是 retrieval strategy，只是换了个更大的桶。

---

## 1. Candidate generation vs final ranking

类比选餐厅：

```text
Candidate generation:
找出附近 30 家卖面条的店。

Final ranking:
在这 30 家里综合饮食限制、价格、评价、步行距离排序。
```

如果让最昂贵的 judge 深度检查地球上所有餐厅，晚饭可能要等到下周。

Retrieval 同理：

```text
cheap/high-recall retrieval
        ↓
small candidate set
        ↓
slower/high-precision reranker
```

---

## 2. Dense retrieval

Dense retrieval 比较 embedding vectors。

优势：

- semantic similarity；
- paraphrase；
- 同义/相关概念不同表述。

弱点可能包括：

- exact identifier；
- rare name；
- version string；
- `ERR-4927` 这种 error code；
- embedding model 表达不好的术语。

Dense retrieval 不是“理解万物的 AI search”，只是一个 learned similarity signal。

---

## 3. Sparse / lexical retrieval

BM25 等 sparse system 强调词面证据，特别适合：

```text
invoice_id=AB-9917
CVE-2026-1234
function_name_exact_match
```

因为 exact token 比“对发票的哲学理解”更重要。

Dense/sparse 的 failure mode 不同，因此 hybrid retrieval 有机会利用互补性。

---

## 4. Hybrid retrieval

```text
               dense retriever
              /               \
query -------                   -> rank fusion -> candidates
              \               /
               sparse retriever
```

不要因为两个 retriever 看起来更 enterprise 就上两个。要评估它们是否真的找回了不同 relevant item。

诊断表可以是：

```text
query type          dense hit?   sparse hit?
paraphrase             yes          maybe
exact product code     maybe         yes
rare acronym            no           yes
semantic concept        yes          maybe
```

Hybrid 的复杂度只有在 union 实际提高 recall 时才值得。

---

## 5. Reciprocal Rank Fusion（RRF）

Dense cosine 与 BM25 raw score 不同尺度：

```text
cosine = 0.81
BM25   = 17.4
```

直接相加没有可靠意义。

RRF 用 **rank position** 融合：

```text
score(document) += 1 / (k + rank)
```

```python
def rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return [doc for doc, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


dense = ["D3", "D1", "D8"]
sparse = ["D8", "D4", "D3"]
print(rrf([dense, sparse]))
```

多个 ranking 都支持的 document 会累积 credit，而无需先校准 raw score。

RRF 是很好理解的 default idea，但不是 universal optimum，仍需评估参数与 retriever quality。

---

## 6. Filtering 发生在“relevance 获胜”之前

Filtering 回答：

> 这个 item 是否允许/适用于当前 request？

Ranking 回答：

> 在允许的 item 中，哪个最 relevant？

例如：

```text
tenant_id == authenticated tenant  -> authorization/filter
version == current product         -> applicability filter
semantic similarity                -> rank
freshness / source quality         -> rerank feature
```

Semantic similarity 无法修复 authorization failure。跨租户 document 即使 score=0.99，仍然是错误租户。

---

## 7. Reranking

Reranker 接收更小 candidate set，使用更昂贵或 task-specific signal。

可能是：

- lexical/business heuristic；
- cross-encoder relevance model；
- 小 candidate set 上的 LLM relevance judge；
- freshness/authority feature；
- domain-specific quality signal。

Toy lexical reranker：

```python
def overlap_score(query: str, text: str) -> int:
    q = set(query.lower().split())
    t = set(text.lower().split())
    return len(q & t)

reranked = sorted(
    candidates,
    key=lambda item: overlap_score(query, item.chunk.text),
    reverse=True,
)
```

它不是 production relevance model，只是把 two-stage architecture 展开给你看。

---

## 8. Diversity：top-k chunks 不等于 top-k independent sources

常见失败：

```text
E1 paper-A chunk 4
E2 paper-A chunk 5
E3 paper-A chunk 6
E4 paper-A chunk 7
```

四个 passage 实际只来自一个 underlying document，不能被误当成四个独立来源。

简单 document cap：

```python
def diversify(results, top_k=4, max_per_document=1):
    counts = {}
    selected = []
    for result in results:
        doc = result.chunk.metadata["document_id"]
        if counts.get(doc, 0) >= max_per_document:
            continue
        counts[doc] = counts.get(doc, 0) + 1
        selected.append(result)
        if len(selected) == top_k:
            break
    return selected
```

Stage 15 的 `DiversifiedResearchCorpus` 使用了这个思想。

但 diversity 只是 heuristic。有些问题确实需要同一长文档多个 passage，所以 policy 要按任务调。

---

## 9. MMR 直觉：relevance vs redundancy

Maximum Marginal Relevance 风格的选择在两者间平衡：

```text
relevance to query
        vs
similarity to already selected items
```

概念式：

```text
MMR(candidate)
= λ * relevance(candidate, query)
- (1-λ) * redundancy(candidate, selected)
```

高 `λ` 更重纯 relevance；低 `λ` 更重 diversity。

更一般的结论是：

> Final context selection 应优化整个 evidence **set**，而不是只独立优化每个 item。

---

## 10. Query transformation

用户用词可能和 corpus 不匹配：

```text
User: "Why did my thing fail yesterday?"
Corpus: "payment settlement timeout"
```

可能有用的 transformation：

- rewrite 成 domain terminology；
- acronym/alias expansion；
- multi-part question decomposition；
- 多个 complementary search；
- exact identifier route 到 sparse search。

但 transformation 会产生 intent drift，因此必须 bounded：

```text
original query
-> at most N rewrites/subqueries
-> retrieve
-> evaluate evidence
-> stop or abstain
```

一个不确定的 Agent 不该整个下午都在写越来越诗意的 search query。

---

## 11. More context 不总是更好

初学者策略：

```text
retrieval weak
-> top_k = 100
```

结果 generator 收到 100 个大多不相关的 chunk。

恭喜：你把 retriever 的 uncertainty 转换成了 generator 的 confusion。

Candidate `k` 可以为了 recall 较大，但经过 filter/rerank/diversify 后，最终 model context 通常应小得多。

---

## 12. Worked example

Query：

```text
"What changed in error ERR-4927 retry behavior?"
```

Pipeline：

```text
sparse search
  -> exact ERR-4927 references

dense search
  -> documents about retry/backoff behavior

RRF
  -> merge complementary candidates

metadata filter
  -> current product/version only

diversify
  -> avoid five chunks from one release note

rerank
  -> prioritize passages explicitly describing changed behavior

final 4 passages
  -> answer model
```

每一层有不同责任，比一个神秘 `search()` score 更容易 debug。

---

## 13. 如何评估 pipeline

分层 measure：

```text
candidate Recall@k
MRR / nDCG / rank analysis
filter correctness
source/document diversity
reranker improvement
final evidence precision
answer groundedness
latency and cost
```

Candidate retrieval 没召回 relevant document，reranker 救不了；evidence 在 context assembly 前消失，generator 也引用不了。

---

## 完成检查

你应该能解释：

1. candidate retrieval vs reranking；
2. dense vs sparse failure mode；
3. hybrid search 什么时候值得；
4. RRF 为什么避免混用不同 raw score；
5. filtering vs relevance ranking；
6. document diversity 与 MMR；
7. query rewrite/decomposition 为什么要 bounded；
8. candidate `k` 与 final context size 为什么是两个 decision；
9. 哪个 metric 对应诊断哪个 pipeline stage。
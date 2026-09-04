# RAG Evaluation

RAG 至少有两个大类失败位置：

```text
retrieval quality
        |
        v
generation quality
```

Final answer 错了，必须知道是哪一层出问题。否则就像汤难喝以后先换冰箱——也许是食材，也许是菜谱，不能靠玄学调参。

---

## 1. 构建 evaluation dataset

一个小型样本可以包含：

```python
{
    "question": "Which backend supports payload filtering?",
    "relevant_chunk_ids": ["qdrant-filtering"],
    "reference_answer": "Qdrant supports payload-based filtering."
}
```

Retrieval evaluation 最关键的 label 往往是：

```text
哪些 chunk 算 relevant evidence？
```

Answer evaluation 还可能需要：

- reference answer；
- required fact；
- forbidden unsupported claim；
- acceptable abstention case。

---

## 2. Recall@k

Recall@k 问：

> top-k 里是否包含 relevant evidence？

一个 query 只有一个 required chunk 时：

```text
relevant chunk in top 5 -> hit
missing from top 5      -> miss
```

Across dataset：

```python
recall_at_k = hits / total_queries
```

Reranker 只能处理 candidate retrieval 已经拿回来的文档，因此 first-stage recall 很重要。

---

## 3. Precision@k

Precision@k 问：

> retrieved set 中有多少比例 relevant？

Top 5 中 2 relevant + 3 irrelevant：

```text
precision@5 = 2 / 5
```

Irrelevant context 会增加 token/cost，也会干扰 generation，因此 precision 同样重要。

---

## 4. MRR

Mean Reciprocal Rank 奖励第一个 relevant item 尽量靠前。

```text
rank 1 -> 1/1 = 1.0
rank 2 -> 1/2 = 0.5
rank 5 -> 1/5 = 0.2
```

然后对 query 求平均。

当“一个强 evidence 尽早出现”特别重要时，MRR 很有用。

---

## 5. nDCG

当多个 result 有 graded relevance 时，nDCG 同时考虑：

- relevance degree；
- ranking position。

第一天不需要把所有 metric 都集齐。没人理解的一大串 metric 不会自动让项目更科学。

---

## 6. 分组件评估

至少概念上做三类实验：

### Retrieval-only

```text
query -> retriever -> ranked chunk IDs
```

测 retrieval metrics。

### Generation with oracle evidence

直接给 generator 已知正确 evidence。

如果这样仍答错，retrieval 就不是主问题。

### End-to-end RAG

```text
question -> retrieval -> generation -> final answer
```

看产品级表现。

这种分解让 failure 可诊断。

---

## 7. Groundedness / faithfulness

不能只问“答案听起来是否正确”，还要问：

```text
答案中的 factual claims 是否被 retrieved evidence 支持？
```

可能的 evaluation：

- deterministic required-fact checks；
- citation/support checks；
- human grading；
- carefully designed LLM-as-judge。

Stage 10 会系统讲 evaluator design。

核心区别：

> **Answer correctness 与 evidence support 是两个性质。**

一个幸运猜对但没有 evidence support 的 answer，今天可能正确，明天仍然危险。

---

## 8. 评估 abstention

如果 corpus 没答案，grounded Agent 应该可能 abstain。

因此 dataset 必须包含：

```text
correct behavior = insufficient_evidence
```

同时测：

- evidence absent 时 false answer；
- evidence present 时 unnecessary abstention。

否则 benchmark 会偷偷奖励 confident guessing。

---

## 9. 评估 Agentic retrieval decision

Agentic RAG 还应测：

- retrieval-needed classification accuracy；
- unnecessary retrieval rate；
- rewrite frequency；
- rewrite success rate；
- average retrieval calls/task；
- retries 增加的 latency/cost；
- evidence-sufficiency accuracy。

一个每题搜 17 次才能多涨一点 accuracy 的 Agent，不一定是 production win。

---

## 10. Tiny deterministic metric 示例

```python
def recall_at_k(retrieved_ids, relevant_ids, k):
    relevant = set(relevant_ids)
    if not relevant:
        return 1.0

    retrieved = set(retrieved_ids[:k])
    return len(retrieved & relevant) / len(relevant)
```

教学项目中，这种可检查的小代码往往比一开始就藏进大 evaluation framework 更有价值。

---

## 11. 用数据调参，不用 folklore

这些参数最终都应在 representative evaluation set 上比较：

```text
chunk_size
overlap
top_k
embedding model
metadata filters
reranker
rewrite budget
```

不要把某个 tutorial 的：

```text
chunk_size=512
top_k=4
```

升级为自然常数。

---

## 完成检查

你应该能解释：

1. 为什么 retrieval/generation 要分开评估；
2. Recall@k 与 Precision@k；
3. MRR 奖励什么；
4. oracle-evidence generation test 为什么有用；
5. groundedness vs correctness；
6. abstention 为什么也要有 evaluation case；
7. Agentic RAG 多出哪些 metrics。
# Retrieval, Hybrid Search, and Reranking

A mature retrieval pipeline often has two different jobs:

```text
Stage A: retrieve a broad candidate set
Stage B: rerank the candidates more carefully
```

That separation is useful because the cheapest way to find 50 plausible passages may not be the best way to decide which 5 deserve final context space.

---

## 1. Candidate generation vs final ranking

Imagine choosing a restaurant in a city.

Candidate generation:

```text
"Show me 30 nearby places that serve noodles."
```

Reranking:

```text
"Among these 30, which best fits tonight's budget, dietary needs, reviews, and walking distance?"
```

If you ask the expensive judge to carefully inspect every restaurant on Earth, dinner may happen next Tuesday.

Retrieval systems make the same trade-off.

---

## 2. Dense retrieval

Dense retrieval compares embedding vectors.

Strengths:

- semantic similarity;
- paraphrases;
- concepts expressed with different words.

Potential weaknesses:

- exact identifiers;
- rare names;
- version strings;
- codes such as `ERR-4927`;
- terms the embedding model represents poorly.

---

## 3. Sparse / lexical retrieval

Keyword or BM25-style retrieval focuses more directly on terms.

It can be excellent when the query contains:

```text
invoice_id=AB-9917
```

because the exact token matters more than a philosophical discussion of what invoices mean.

Dense and sparse retrieval fail differently.

That motivates **hybrid retrieval**.

---

## 4. Hybrid retrieval

A simple architecture is:

```text
              dense retriever
             /               \
query ------                    -> fuse rankings -> rerank
             \               /
              sparse retriever
```

The point is not to use two retrievers because two sounds impressive.

Use hybrid retrieval when evaluation shows complementary recall.

---

## 5. Reciprocal Rank Fusion intuition

One common rank-fusion idea gives each result credit based on its rank rather than trying to directly compare incompatible raw scores.

Conceptually:

```text
RRF score(doc) += 1 / (constant + rank)
```

Why useful?

Because:

```text
cosine score = 0.81
BM25 score   = 17.4
```

cannot be sensibly added without calibration.

Ranks are easier to combine.

---

## 6. Reranking

A reranker takes retrieved candidates and assigns a more task-specific order.

Examples:

- lexical overlap rules;
- business-priority features;
- cross-encoder relevance models;
- LLM-based ranking for small candidate sets;
- freshness/authority adjustments.

Conceptually:

```text
top 30 candidates
   -> expensive relevance judge
   -> best 5 evidence chunks
```

---

## 7. Tiny demo reranker

A toy lexical reranker can be written in a few lines:

```python
def overlap_score(query: str, text: str) -> int:
    query_terms = set(query.lower().split())
    text_terms = set(text.lower().split())
    return len(query_terms & text_terms)

reranked = sorted(
    candidates,
    key=lambda item: overlap_score(query, item.chunk.text),
    reverse=True,
)
```

This is not a production relevance model.

It is useful because the architecture is visible:

```text
retrieve first
rerank second
```

---

## 8. Metadata filtering and reranking solve different problems

Filtering says:

```text
This candidate is allowed / applicable.
```

Reranking says:

```text
Among allowed candidates, this one is more relevant.
```

Examples:

```text
tenant_id == current tenant   -> filter
version == current version    -> filter
semantic relevance            -> rank
freshness preference          -> rerank feature
```

Do not use a relevance model to repair an authorization mistake.

---

## 9. More context is not always better

A common beginner strategy is:

```text
Retrieval looks weak?
Set top_k = 100!
```

Now the answer model receives 100 chunks, most irrelevant.

Congratulations: the retriever's uncertainty has been converted into the generator's confusion.

Large `top_k` can increase recall but also:

- increase latency/token cost;
- dilute useful evidence;
- increase contradictory passages;
- enlarge prompt-injection surface.

Choose candidate and final-context sizes separately.

---

## 10. Query rewriting

Sometimes the user's wording is not ideal for the corpus.

User:

```text
"Why did my thing fail yesterday?"
```

Knowledge base terminology:

```text
"payment settlement timeout"
```

An Agent can rewrite a retrieval query while preserving user intent.

But query rewriting needs a budget and stop condition; otherwise an uncertain Agent can spend its afternoon inventing increasingly poetic search queries.

Tiny-Agent limits rewrites explicitly.

---

## Completion check

You should be able to explain:

1. Candidate retrieval vs reranking.
2. Dense vs sparse retrieval strengths.
3. Why hybrid retrieval can improve recall.
4. Why rank fusion can be easier than mixing raw scores.
5. Filtering vs reranking.
6. Why increasing `top_k` blindly can hurt generation quality.
7. Why query rewriting should be bounded.

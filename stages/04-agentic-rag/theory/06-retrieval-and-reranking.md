# Retrieval, Hybrid Search, Query Transformation, Diversity, and Reranking

A mature retrieval pipeline rarely asks one scoring function to do everything. It separates **candidate recall** from **final evidence selection**.

```text
query
  -> one or more candidate retrievers
  -> fuse / filter
  -> diversify
  -> rerank
  -> small evidence set for the model
```

If your only retrieval knob is `top_k=100`, you do not yet have a retrieval strategy. You have a larger bucket.

---

## 1. Candidate generation vs final ranking

Imagine choosing a restaurant.

Candidate generation:

```text
Find 30 nearby places serving noodles.
```

Final ranking:

```text
Among those, rank by dietary needs, price, reviews, and walking distance.
```

If you ask the expensive judge to deeply inspect every restaurant on Earth, dinner may happen next Tuesday.

Retrieval uses the same two-stage idea:

```text
cheap/high-recall retrieval
        ↓
small candidate set
        ↓
slower/high-precision reranker
```

---

## 2. Dense retrieval

Dense retrieval compares embedding vectors.

Strengths:

- semantic similarity;
- paraphrases;
- related concepts expressed with different words.

Weaknesses can include:

- exact identifiers;
- rare names;
- version strings;
- error codes such as `ERR-4927`;
- terms poorly represented by the embedding model.

Dense retrieval is not "AI search that understands everything." It is one learned similarity signal.

---

## 3. Sparse / lexical retrieval

Sparse systems such as BM25 reward lexical term evidence.

They can be excellent for:

```text
invoice_id=AB-9917
CVE-2026-1234
function_name_exact_match
```

because the exact token matters more than a philosophical understanding of invoices.

Dense and sparse retrieval often fail differently. That complementarity motivates hybrid retrieval.

---

## 4. Hybrid retrieval

Conceptual architecture:

```text
               dense retriever
              /               \
query -------                   -> rank fusion -> candidates
              \               /
               sparse retriever
```

Do not deploy two retrievers because two looks more enterprise. Evaluate whether they recover different relevant items.

A useful diagnostic table is:

```text
query type          dense hit?   sparse hit?
paraphrase             yes          maybe
exact product code     maybe         yes
rare acronym            no           yes
semantic concept        yes          maybe
```

Hybrid retrieval earns its complexity when the union improves recall on your data.

---

## 5. Reciprocal Rank Fusion (RRF)

Dense cosine scores and BM25 scores live on different scales:

```text
cosine = 0.81
BM25   = 17.4
```

Adding them directly has no meaningful interpretation without calibration.

RRF combines **rank positions** instead:

```text
score(document) += 1 / (k + rank)
```

Minimal implementation:

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

Documents supported by multiple rankings accumulate credit without requiring raw-score calibration.

RRF is a useful default idea, not a universal optimum. Evaluate fusion parameters and retriever quality.

---

## 6. Filtering happens before "relevance wins"

Filtering answers:

> Is this item allowed/applicable to the request?

Ranking answers:

> Among allowed items, which appears most relevant?

Examples:

```text
tenant_id == authenticated tenant  -> authorization/filter
version == current product         -> applicability filter
semantic similarity                -> rank
freshness / source quality         -> rerank feature
```

Never use semantic similarity to repair an authorization failure. A cross-tenant document with score `0.99` is still the wrong tenant.

---

## 7. Reranking

A reranker sees a smaller candidate set and applies a more expensive or task-specific signal.

Possible rerankers:

- lexical/business heuristics;
- cross-encoder relevance models;
- LLM relevance judgments for small candidate sets;
- freshness/authority features;
- domain-specific quality signals.

A toy lexical reranker makes the architecture visible:

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

This is not a production relevance model. Its job is to expose the two-stage mechanism.

---

## 8. Diversity: top-k chunks are not top-k independent sources

A common failure:

```text
E1 paper-A chunk 4
E2 paper-A chunk 5
E3 paper-A chunk 6
E4 paper-A chunk 7
```

The Agent now has four passages, but only one underlying document. Counting them as four independent sources creates false confidence.

A simple document cap can help:

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

Stage 15 uses this idea in `DiversifiedResearchCorpus`.

Diversity is a heuristic. Some questions legitimately require several passages from one long document, so tune policy to the task.

---

## 9. MMR intuition: relevance vs redundancy

Maximum Marginal Relevance (MMR)-style selection balances:

```text
relevance to query
        vs
similarity to already selected items
```

Conceptually:

```text
MMR(candidate)
= λ * relevance(candidate, query)
- (1-λ) * redundancy(candidate, selected)
```

High `λ` favors pure relevance; lower `λ` promotes diversity.

The important lesson is broader than one formula:

> Final context selection should optimize the **set**, not only each item independently.

---

## 10. Query transformation

The user's language may not match the corpus.

```text
User: "Why did my thing fail yesterday?"
Corpus: "payment settlement timeout"
```

Useful transformations include:

- rewrite into domain terminology;
- expand acronyms/aliases;
- decompose a multi-part question;
- generate multiple complementary searches;
- route exact identifiers to sparse search.

But transformation can drift away from user intent.

Bound it:

```text
original query
-> at most N rewrites/subqueries
-> retrieve
-> evaluate evidence
-> stop or abstain
```

An uncertain Agent should not spend its afternoon composing increasingly poetic search queries.

---

## 11. More context is not always better

Beginner strategy:

```text
retrieval looks weak
-> set top_k = 100
```

Now the generator receives 100 chunks, most irrelevant.

Congratulations: the retriever's uncertainty has been converted into the generator's confusion.

Large candidate `k` can improve recall, but final model context should usually be much smaller after filtering/reranking/diversification.

---

## 12. Worked example

Query:

```text
"What changed in error ERR-4927 retry behavior?"
```

Pipeline:

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

Each layer has a different responsibility. That is easier to debug than one mysterious `search()` score.

---

## 13. How to evaluate the pipeline

Measure components separately:

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

A reranker cannot rescue a relevant document that candidate retrieval never returned.

Likewise, a generator cannot cite evidence that disappeared before context assembly.

---

## Completion check

You should be able to explain:

1. candidate retrieval vs reranking;
2. dense vs sparse failure modes;
3. when hybrid search is justified;
4. why RRF avoids mixing incompatible raw scores;
5. filtering vs relevance ranking;
6. document diversity and MMR intuition;
7. why query rewriting/decomposition must be bounded;
8. why candidate `k` and final context size are separate decisions;
9. which metric diagnoses each pipeline stage.

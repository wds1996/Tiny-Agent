# Vector Search and Similarity

Once documents and queries are vectors, retrieval becomes a ranking problem:

```text
query vector
    -> compare with document vectors
    -> rank by similarity
    -> return top-k
```

---

## 1. Cosine similarity

For vectors `x` and `y`:

```text
cosine(x, y) = dot(x, y) / (||x|| * ||y||)
```

Intuition:

- close to `1`: same direction;
- close to `0`: roughly unrelated directions;
- close to `-1`: opposite directions.

Tiny-Agent implements the formula directly:

```python
from tiny_agent import cosine_similarity

score = cosine_similarity(
    [1.0, 0.0],
    [0.8, 0.2],
)
```

---

## 2. Why normalization matters

If vectors are L2-normalized:

```text
||x|| = ||y|| = 1
```

then:

```text
cosine(x, y) = dot(x, y)
```

That is why FAISS can perform cosine-style ranking with inner product after normalizing both database and query vectors.

Official FAISS reference:

- [MetricType and distances](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances)

Tiny-Agent's FAISS adapter therefore does:

```python
faiss.normalize_L2(matrix)
index = faiss.IndexFlatIP(dimension)
index.add(matrix)
```

and also normalizes the query before search.

---

## 3. Inner product is not automatically cosine similarity

A common mistake is:

```text
IndexFlatIP == cosine similarity
```

Not quite.

Without normalization, inner product also depends on vector magnitude.

The correct relationship for our example is:

```text
normalized vectors
+
inner-product search
=
cosine-similarity ranking
```

---

## 4. Top-k means ranking, not truth

Suppose the system returns:

```text
1. chunk A  score=0.83
2. chunk B  score=0.78
3. chunk C  score=0.63
```

`top_k=3` means:

> Return the three highest-ranked candidates under this scoring system.

It does **not** mean:

> These three passages are definitely relevant and sufficient.

Top-k is a candidate-selection parameter.

This is why later stages of a retrieval pipeline may include:

- metadata filtering;
- thresholds;
- reranking;
- evidence-sufficiency checks.

---

## 5. Exact search first

For a beginner corpus with 100 chunks, the easiest correct baseline is brute force:

```python
for chunk_vector in all_vectors:
    score = cosine(query_vector, chunk_vector)

sort_by_score()
return top_k
```

Tiny-Agent's `InMemoryVectorRetriever` does exactly that.

This baseline is valuable because it is:

- easy to inspect;
- exact;
- deterministic;
- easy to compare against optimized indexes.

---

## 6. Then why FAISS?

Because scanning every vector becomes expensive as the collection grows.

FAISS provides vector indexes and efficient similarity-search algorithms. Some indexes are exact; others trade some recall for speed/memory efficiency.

The Stage 04 first FAISS example uses:

```python
faiss.IndexFlatIP
```

because Flat search is easy to reason about and exact.

We deliberately do **not** begin with IVF/PQ/HNSW tuning.

Learning approximate-nearest-neighbor acronyms before understanding top-k similarity is the vector-search version of buying a race-car spoiler before learning to drive.

Official references:

- [FAISS Wiki](https://github.com/facebookresearch/faiss/wiki)
- [FAISS indexes](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes)
- [Guidelines to choose an index](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index)

---

## 7. Exact vs approximate nearest-neighbor search

Conceptually:

### Exact

```text
compare against all candidates
-> best possible ranking under the metric
-> more compute as corpus grows
```

### Approximate

```text
use an index/search structure
-> inspect fewer candidates
-> faster/scalable
-> may miss some true nearest neighbors
```

The right question is not:

> Which index sounds most advanced?

It is:

> What recall, latency, memory, update pattern, and scale does this application need?

---

## 8. Similarity score semantics are backend-specific

Do not casually compare:

```text
FAISS score 0.81
```

with:

```text
some reranker score 0.81
```

or a different embedding model's score.

Scores can have different meanings, distributions, normalization, and calibration.

Thresholds should be validated on your own retrieval dataset.

---

## 9. A slightly ridiculous analogy

Vector search is like asking a nightclub bouncer:

> "Which people in this line look most like the description I gave you?"

The bouncer can rank the line.

But ranking is not the same as proving identity.

`top_k=5` means "these five look most similar", not "these five are definitely the people you wanted".

Reranking and evidence checks are the second round of questioning.

---

## Completion check

You should be able to explain:

1. Cosine similarity vs inner product.
2. Why normalized inner product can implement cosine ranking.
3. Why top-k is not a relevance guarantee.
4. Exact vs approximate nearest-neighbor search.
5. Why Stage 04 starts with brute force and `IndexFlatIP`.
6. Why similarity thresholds require evaluation rather than guessing.

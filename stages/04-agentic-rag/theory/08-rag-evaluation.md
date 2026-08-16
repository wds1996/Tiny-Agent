# RAG Evaluation

A RAG system can fail in at least two broad places:

```text
retrieval quality
        |
        v
generation quality
```

If the final answer is wrong, we need to know which layer failed.

Otherwise debugging becomes the culinary equivalent of tasting a bad soup and replacing the refrigerator.

Maybe the ingredients were wrong. Maybe the recipe was wrong. Measure both.

---

## 1. Build an evaluation dataset

A useful small dataset can contain:

```python
{
    "question": "Which backend supports payload filtering?",
    "relevant_chunk_ids": ["qdrant-filtering"],
    "reference_answer": "Qdrant supports payload-based filtering."
}
```

For retrieval evaluation, the most important label is often:

```text
Which chunks count as relevant evidence?
```

For answer evaluation, you may also need:

- reference answers;
- required facts;
- forbidden unsupported claims;
- acceptable abstention cases.

---

## 2. Recall@k

Recall@k asks:

> Did the top-k retrieved set contain the relevant evidence?

For one question with one required chunk:

```text
relevant chunk appears in top 5 -> hit
missing from top 5              -> miss
```

Across a dataset:

```python
recall_at_k = hits / total_queries
```

High recall is important before reranking because a reranker cannot rescue a relevant document that was never retrieved.

---

## 3. Precision@k

Precision@k asks:

> How much of the retrieved set is relevant?

If top 5 contains:

```text
2 relevant chunks
3 irrelevant chunks
```

then:

```text
precision@5 = 2 / 5
```

In RAG, irrelevant context can increase cost and distract generation, so precision matters too.

---

## 4. MRR

Mean Reciprocal Rank rewards putting the first relevant result near the top.

For one query:

```text
first relevant result at rank 1 -> 1/1 = 1.0
rank 2                           -> 1/2 = 0.5
rank 5                           -> 1/5 = 0.2
```

Then average across queries.

MRR is useful when one strong evidence item near the top is especially important.

---

## 5. nDCG

When multiple results have graded relevance, normalized discounted cumulative gain (nDCG) can capture both:

- how relevant results are;
- how high they appear in the ranking.

You do not need nDCG on day one.

Start with metrics that match your task and labels.

A metric collection that no one understands is not automatically more scientific.

---

## 6. Evaluate components separately

Run at least these experiments conceptually:

### Retrieval-only

```text
query -> retriever -> ranked chunk IDs
```

Measure retrieval metrics.

### Generation with oracle evidence

Give the generator known-correct evidence.

If it still answers badly, retrieval is not the main problem.

### End-to-end RAG

```text
question -> retrieval -> generation -> final answer
```

This tells you product-level performance.

The separation makes failures diagnosable.

---

## 7. Groundedness / faithfulness

A useful answer should not merely sound plausible.

Ask:

```text
Are the answer's factual claims supported by retrieved evidence?
```

Possible evaluation approaches include:

- deterministic required-fact checks;
- citation/support checks;
- human grading;
- carefully designed LLM-as-judge evaluation.

Stage 08 will study evaluator design in depth.

For now, the key principle is:

> Answer correctness and evidence support are distinct properties.

A lucky unsupported answer can be correct today and unsafe tomorrow.

---

## 8. Evaluate abstention

If the corpus lacks the answer, a grounded Agent may need to abstain.

So include test cases where:

```text
correct behavior = insufficient_evidence
```

Measure:

- false answers when evidence is absent;
- unnecessary abstention when evidence is present.

Otherwise your benchmark silently rewards confident guessing.

---

## 9. Evaluate Agentic retrieval decisions

For Agentic RAG also measure:

- retrieval-needed classification accuracy;
- unnecessary retrieval rate;
- rewrite frequency;
- rewrite success rate;
- average retrieval calls per task;
- latency/cost added by retries;
- evidence-sufficiency accuracy.

An Agent that improves answer quality by performing 17 searches per question may not be a production win.

---

## 10. Tiny deterministic metric example

```python
def recall_at_k(retrieved_ids, relevant_ids, k):
    relevant = set(relevant_ids)
    if not relevant:
        return 1.0

    retrieved = set(retrieved_ids[:k])
    return len(retrieved & relevant) / len(relevant)
```

For a small tutorial dataset, simple code like this is often better than hiding evaluation inside a large framework.

You should be able to inspect exactly what is being measured.

---

## 11. Tune with data, not folklore

Parameters such as:

```text
chunk_size
overlap
top_k
embedding model
metadata filters
reranker
rewrite budget
```

should ultimately be compared on a representative evaluation set.

Do not copy:

```text
chunk_size=512
top_k=4
```

from a tutorial and promote those numbers to universal constants of nature.

---

## 12. Completion check

You should be able to explain:

1. Why retrieval and generation need separate evaluation.
2. Recall@k and Precision@k.
3. What MRR rewards.
4. Why oracle-evidence generation tests are useful.
5. Groundedness vs answer correctness.
6. Why abstention needs evaluation cases.
7. Which additional metrics Agentic RAG introduces.

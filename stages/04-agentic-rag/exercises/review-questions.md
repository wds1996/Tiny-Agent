# Stage 04 Review Questions and Exercises

Use these after you have run the Stage 04 examples. Try to answer without looking at the notes first.

---

# Part A — Concept checks

1. Why is RAG not the same thing as a vector database?
2. Why is a Retriever more general than a Vector Store?
3. Why can a normal two-step RAG pipeline still be a deterministic Workflow rather than an Agent?
4. What problem does chunk overlap solve?
5. Why can a very large chunk hurt retrieval even if it contains the answer?
6. Why is metadata not redundant with embeddings?
7. What is the difference between cosine similarity and inner product?
8. Why does normalized inner-product search reproduce cosine ranking?
9. What does `top_k=5` actually guarantee?
10. Why is `HashEmbeddingModel` unsuitable as a production semantic embedding model?
11. What application state must remain synchronized with an embedding-model migration?
12. Why is FAISS useful even though it is not a full vector database?
13. What does Qdrant payload add beyond the vector itself?
14. Why should tenant/authorization filters not come directly from arbitrary LLM output?
15. Candidate retrieval vs reranking: what is each stage optimizing for?
16. Why can dense and sparse retrieval complement each other?
17. Why can increasing `top_k` make generation worse?
18. What makes retrieval "Agentic"?
19. Why must query rewriting have a budget?
20. Why is `insufficient_evidence` sometimes the best possible result?
21. Why should retrieved documents be treated as untrusted data?
22. Retrieval quality vs grounded answer quality: why evaluate both separately?
23. What does Recall@k measure?
24. What does MRR reward?
25. Why should an evaluation set include questions whose correct behavior is abstention?

---

# Part B — Trace the pipeline

Given:

```text
question
  -> embedding
  -> FAISS top 20
  -> metadata post-filter
  -> rerank top 5
  -> answer
```

Answer:

1. What happens if the only allowed document was ranked 25th by FAISS?
2. How might database-native filtered vector search change that failure mode?
3. Which stage should enforce `tenant_id`?
4. Which stage should prefer a fresher but still allowed policy version?
5. Which metrics would tell you whether the first-stage retriever is the bottleneck?

---

# Part C — Coding exercises

## Exercise 1 — Better chunker

Extend `chunk_text()` so it can split on paragraph boundaries before falling back to token windows.

Requirements:

- preserve source metadata;
- preserve stable chunk IDs;
- test empty paragraphs;
- explain how paragraph chunks change retrieval behavior.

## Exercise 2 — Thresholded retrieval

Add an optional `min_score` to `InMemoryVectorRetriever`.

Questions:

- Should the threshold live in the Retriever or the RAG Workflow?
- Are scores from different embedding models directly comparable?
- How would you tune the threshold?

## Exercise 3 — Keyword retriever

Implement a tiny lexical retriever:

```python
query -> token overlap -> ranked SearchResult
```

Then compare its errors against `HashEmbeddingModel` retrieval.

## Exercise 4 — Reciprocal Rank Fusion

Fuse rankings from your lexical and vector retrievers.

Pseudo-code:

```python
for ranking in rankings:
    for rank, document in enumerate(ranking, start=1):
        score[document] += 1 / (60 + rank)
```

Test that documents appearing near the top of both rankings are promoted.

## Exercise 5 — Qdrant filter policy

Add two tenants to the Qdrant demo:

```text
tenant-a
tenant-b
```

Write a test proving a tenant-a query can never retrieve tenant-b evidence when the application supplies the authenticated tenant filter.

Then explain why allowing the LLM to choose this filter would be a security bug.

## Exercise 6 — Agentic source routing

Extend `AgenticRAGWorkflow` to choose between two application-owned retrievers:

```text
product_docs
engineering_docs
```

The model may output only a schema-constrained source enum.

The application maps the enum to a real Retriever instance.

Do not let the model provide arbitrary URLs or database connection strings.

## Exercise 7 — Detect rewrite loops

Create scripted decisions:

```text
query A -> query B -> query A
```

Confirm the workflow stops instead of looping forever.

## Exercise 8 — Retrieval evaluation

Create at least 10 query/relevant-chunk examples and compare:

- Recall@1;
- Recall@3;
- MRR;
- average retrieval latency.

Then change chunk size and compare results.

---

# Part D — Interview-style questions

### Q1. FAISS 和 Qdrant 有什么区别？

A strong answer should mention scope, not brand names:

```text
FAISS -> dense-vector similarity-search/index library
Qdrant -> vector database/service with vectors + payload + filters + collection/database operations
```

### Q2. RAG 为什么能降低幻觉？是不是一定不会幻觉？

A strong answer should say retrieval can provide external grounding, but the system can still fail through bad retrieval, irrelevant evidence, prompt injection, or unsupported generation. RAG reduces some failure modes; it does not mathematically eliminate hallucination.

### Q3. Agentic RAG 比普通 RAG 强在哪里？

Mention conditional retrieval, source/query decisions, bounded rewriting, evidence sufficiency, and the cost/latency/reliability trade-off.

### Q4. 为什么不能把 `top_k` 调得越大越好？

Mention recall vs irrelevant context, token cost, latency, contradictions, and injection surface.

### Q5. 如果最终答案错了，你怎么定位 RAG 的问题？

A strong debugging sequence is:

```text
inspect parsing/chunks
-> inspect retrieval ranking
-> test reranking/filtering
-> test generator with oracle evidence
-> inspect final groundedness
```

---

# Completion challenge

Without using LangChain's prebuilt RAG helpers, build a small knowledge Agent that:

1. chunks 3–5 local text documents;
2. embeds them through the Tiny-Agent `EmbeddingModel` interface;
3. stores/searches them with Qdrant local mode;
4. applies one application-owned metadata filter;
5. lets a structured decision choose whether retrieval is needed;
6. allows at most one query rewrite;
7. abstains when evidence is insufficient;
8. reports query history and evidence IDs;
9. evaluates Recall@3 on at least 10 questions.

If you can explain every line and every boundary, Stage 04 has done its job.

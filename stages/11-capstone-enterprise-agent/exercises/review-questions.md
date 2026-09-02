# Stage 11 — Review, Coding, and Interview Exercises

## Concept checks

1. Why is `scholarly_metadata` not automatically evidence for a paper's substantive claims?
2. Why can a top-1 retrieval result still be unusable evidence?
3. What does `min_local_score` protect against, and why must it be recalibrated after changing embedding models?
4. Why does OpenScholar return `insufficient_evidence` instead of always asking the model to answer?
5. What is the difference between `request_id`, `run_id`, `thread_id`, and `user_id`?
6. Why can a user preference stored in long-term memory affect style but not become a research citation?
7. Why is `ApprovalDecision(outcome="approve")` not sufficient to authorize `../../outside.md`?
8. Why does the LangGraph export node place `interrupt()` before the file write?
9. What application rules remain necessary even if LangGraph successfully checkpoints every node?
10. Why is the reviewer/writer system still bounded even though reflection may improve quality?

## Base vs LangGraph

11. Draw the base control flow using only Python concepts (`if`, `for`, functions, `asyncio`).
12. Draw the equivalent LangGraph nodes and conditional edges.
13. Which state values should be checkpointed? Which runtime objects should never enter graph state?
14. Under what requirements does the LangGraph implementation become materially better than the base version?
15. Under what requirements would the base implementation remain the better engineering choice?
16. How would you implement durable HITL without LangGraph?
17. Why is wrapping `base_agent.run()` in one graph node not a meaningful framework comparison?

## Evidence and RAG coding exercises

18. Replace `HashEmbeddingModel` with a real embedding provider while preserving the `Retriever` boundary.
19. Add a Qdrant-backed corpus index and metadata filters for year/source.
20. Build a labeled retrieval set and measure Recall@k before changing `min_local_score`.
21. Add a reranker and report whether end-to-end grounding actually improves.
22. Add section/page locators to PDF chunks so citations can be more precise.
23. Add a third evidence type for verified abstracts. Define exactly which claims it may support.
24. Detect duplicate papers returned by local corpus and Crossref using DOI/arXiv identifiers.

## Memory / safety coding exercises

25. Implement a durable `ResearchMemoryStore` backed by LangGraph Store/Postgres.
26. Add memory expiry and provenance.
27. Add an authenticated `Principal` to the HTTP adapter; remove trust in body-level `user_id`.
28. Require a reviewer role before report export approval can be accepted.
29. Add signed/expiring approval grants bound to exact export arguments.
30. Add an idempotency key to report export and explain the difference from exclusive file creation.
31. Treat an uploaded paper containing prompt-injection text as a regression case. Prove it cannot change export policy.

## Multi-Agent exercises

32. Measure critic/writer quality gain against the single-writer baseline.
33. Add an independent citation verifier Agent. What context should it receive?
34. Explain why a reviewer Agent should not inherit every tool of the research Agent.
35. Add parallel specialist review (grounding + style) and design the fan-in policy.
36. Create a failure case where critic and writer disagree. Who owns the final decision?

## Evaluation exercises

37. Create a five-question regression set with expected evidence document IDs.
38. Add a deterministic metric for citation precision.
39. Add retrieval Recall@k and connect it to the Stage 08 `EvaluationSuite`.
40. Introduce one hallucinated citation and make the regression gate fail.
41. Add an LLM judge for explanation quality, then calibrate it against human labels.
42. Compare base vs LangGraph latency and total model/Agent calls using the same dataset.
43. Design a hard safety gate that cannot be averaged away by a high prose-quality score.

## Production exercises

44. Put `BoundedAgentService` in front of OpenScholar and configure request/queue deadlines.
45. Replace `InMemorySaver` with a durable Postgres checkpointer.
46. Replace local memory with a durable Store and explain why it is still different from the checkpointer.
47. Add Redis rate limiting keyed by authenticated principal/tenant.
48. Add `/readyz` checks for the durable dependencies.
49. Containerize a Qdrant-backed version and reason about replica/pool multiplication.
50. Design a durable long-running research job API (`POST /runs`, status polling/SSE, cancellation).

## MCP / A2A exercises

51. Explain why MCP `search_corpus` is a capability, while A2A OpenScholar is an independent Agent.
52. Add an MCP Resource for corpus metadata without flattening it into a Tool.
53. Make another Tiny-Agent instance call the OpenScholar A2A service.
54. Add caller authentication to the A2A service. Why is the Agent Card not authorization?
55. Let OpenScholar internally consume an MCP search server while remaining opaque to the A2A caller.

## Architecture interview prompts

56. “Why didn't you just use LangGraph from day one?”
57. “How do you prevent retrieved papers from prompt-injecting the Agent into a dangerous action?”
58. “How do you know a correct-looking answer is actually grounded?”
59. “What happens if the process crashes while waiting for export approval?”
60. “How does your architecture change when moving from one process to five replicas?”
61. “What is the difference between RAG knowledge, long-term memory, and graph checkpoint state?”
62. “Why use multiple Agents for review? How would you prove the extra cost is justified?”
63. “How would you swap OpenAI for another provider?”
64. “Where would you put authentication, authorization, rate limiting, and audit logs?”
65. “If Crossref is down, what degrades and what continues working?”
66. “What would you change first before calling OpenScholar production-ready for real scientific work?”

## Final project challenge

Create your own forked capstone with a different domain—legal research, an open textbook, product documentation, or a codebase—and preserve the same discipline:

```text
explicit evidence types
bounded planning
retrieval evaluation
model-as-proposal
memory governance
human approval
least privilege
traceability
regression tests
base implementation
framework implementation
production boundary
```

If changing the domain forces you to change trust rules, that is a feature. Domain semantics belong to the application, not to the framework.
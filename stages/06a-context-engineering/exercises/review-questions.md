# Review questions

1. Why is model context smaller in meaning than application state?
2. Why should output/runtime reserves be subtracted before optional context selection?
3. Which context items should fail closed rather than be silently dropped?
4. Why is compaction derived state rather than original truth?
5. Give one failure caused by sending too much history.
6. Give one failure caused by aggressive summarization.
7. How are RAG, dynamic tool exposure, Agent Skills, and workspace file reads all examples of progressive disclosure?
8. Why does a large context window not eliminate prompt-injection risk?
9. Design a context policy for a research Agent with 50 papers, 20 memories, 80 tools, and 15 skills.
10. Create an eval comparing full-history, last-N, summary+recent, and retrieval-based context policies on quality/token/cost metrics.

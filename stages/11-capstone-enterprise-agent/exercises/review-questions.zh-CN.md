# Stage 11 — 复习、编程与面试练习

## 一、概念检查

1. 为什么 `scholarly_metadata` 不能自动作为论文 substantive claim 的证据？
2. 为什么 top-1 retrieval result 仍然可能完全不能作为 evidence？
3. `min_local_score` 防止什么问题？为什么更换 embedding model 后必须重新校准？
4. 为什么 OpenScholar 会返回 `insufficient_evidence`，而不是无论如何都要求模型回答？
5. `request_id`、`run_id`、`thread_id` 与 `user_id` 分别表示什么？
6. 为什么 long-term memory 中保存的 user preference 可以影响 style，却不能变成 research citation？
7. 为什么 `ApprovalDecision(outcome="approve")` 仍然不足以授权 `../../outside.md`？
8. 为什么 LangGraph export node 要把 `interrupt()` 放在 file write **之前**？
9. 即使 LangGraph 成功 checkpoint 每一个 node，application 仍然必须自行维护哪些 rule？
10. reviewer / writer system 为什么仍然必须 bounded，即使 reflection 可能提升质量？

## 二、Base vs LangGraph

11. 只使用 Python 概念（`if`、`for`、functions、`asyncio`）画出 Base control flow。
12. 画出等价 LangGraph nodes 与 conditional edges。
13. 哪些 state value 应该 checkpoint？哪些 runtime object 永远不应该进入 graph state？
14. 在什么 requirement 下，LangGraph implementation 相比 Base version 会产生实质优势？
15. 在什么 requirement 下，Base implementation 反而仍是更合理的 engineering choice？
16. 如果完全不用 LangGraph，你会如何实现 durable HITL？
17. 为什么只把 `base_agent.run()` 包进一个 graph node，不能构成有意义的 framework comparison？

## 三、Evidence / RAG 编程练习

18. 用真实 embedding provider 替换 `HashEmbeddingModel`，同时保持 `Retriever` boundary 不变。
19. 增加 Qdrant-backed corpus index，并支持 year / source metadata filters。
20. 构建 labeled retrieval set，在修改 `min_local_score` 之前测量 Recall@k。
21. 增加 reranker，并报告 end-to-end grounding 是否真的提高。
22. 为 PDF chunk 增加 section / page locator，使 citation 更精确。
23. 增加第三类 evidence：verified abstract。必须明确规定它可以支撑哪些 claim、不能支撑哪些 claim。
24. 使用 DOI / arXiv identifier 检测 local corpus 与 Crossref 返回的 duplicate paper。

## 四、Memory / Safety 编程练习

25. 实现基于 LangGraph Store / Postgres 的 durable `ResearchMemoryStore`。
26. 为 memory 增加 expiry 与 provenance。
27. 给 HTTP adapter 增加 authenticated `Principal`，移除对 body-level `user_id` 的信任。
28. 只有 reviewer role 才能接受 report export approval。
29. 增加 signed / expiring approval grant，并绑定 exact export arguments。
30. 为 report export 增加 idempotency key，并解释它与 exclusive file creation 的区别。
31. 把一篇包含 prompt-injection 文本的 uploaded paper 加进 regression set，证明它无法修改 export policy。

## 五、Multi-Agent 练习

32. 用 single-writer baseline 对比 critic / writer team 的质量提升，并测量额外 cost / latency。
33. 增加一个独立 citation-verifier Agent。它应该看到哪些 context？哪些 context 不应该看到？
34. 为什么 reviewer Agent 不应该继承 research Agent 的全部 Tool？
35. 增加 parallel specialist review（grounding + style），设计 fan-in policy。
36. 创建一个 critic 与 writer 意见冲突的 failure case。最终 decision authority 属于谁？

## 六、Evaluation 练习

37. 创建 5 个问题的 regression set，并指定 expected evidence document IDs。
38. 增加 citation precision 的 deterministic metric。
39. 增加 retrieval Recall@k，并接入 Stage 08 `EvaluationSuite`。
40. 人为加入一个 hallucinated citation，使 regression gate 必须 fail。
41. 为 explanation quality 增加 LLM judge，并使用 human labels 校准。
42. 使用同一个 dataset 比较 Base vs LangGraph 的 latency、总 model calls 与 Agent calls。
43. 设计一个 hard safety gate，不能被高 prose-quality score 通过 weighted average 抵消。

## 七、Production 练习

44. 在 OpenScholar 前加入 `BoundedAgentService`，配置 request / queue deadline。
45. 用 durable Postgres checkpointer 替换 `InMemorySaver`。
46. 用 durable Store 替换 local memory，并解释为什么 Store 仍然不等于 checkpointer。
47. 增加 Redis rate limiting，并以 authenticated principal / tenant 作为作用域；不要把 client-supplied identity 当作 key authority。
48. 为 durable dependencies 增加 `/readyz` checks。
49. containerize Qdrant-backed version，并分析 replica / worker / pool multiplication。
50. 设计 durable long-running research job API：`POST /runs`、status polling / SSE、cancellation。

## 八、MCP / A2A 练习

51. 为什么 MCP `search_corpus` 是 capability，而 A2A OpenScholar 是 independent Agent？
52. 增加一个用于 corpus metadata 的 MCP Resource，不要为了方便把所有东西都压成 Tool。
53. 让另一个 Tiny-Agent instance 调用 OpenScholar A2A service。
54. 为 A2A service 增加 caller authentication。为什么 Agent Card 不是 authorization？
55. 让 OpenScholar 内部消费 MCP search server，同时对 A2A caller 保持内部 topology opaque。

## 九、架构面试题

56. “为什么不从第一天就直接使用 LangGraph？”
57. “怎么防止 retrieved paper 通过 prompt injection 驱动 Agent 执行危险操作？”
58. “一个答案看起来正确时，你怎么证明它真的 grounded？”
59. “进程在等待 export approval 时 crash 会发生什么？”
60. “从一个 process 扩展到五个 replica 后，架构会发生哪些变化？”
61. “RAG knowledge、long-term memory 与 graph checkpoint state 有什么区别？”
62. “为什么用多个 Agent 做 review？怎么证明额外 cost 值得？”
63. “如果把 OpenAI 换成另一个 provider，哪些 layer 应该改变，哪些不应该？”
64. “authentication、authorization、rate limiting 与 audit log 分别应该放在哪里？”
65. “Crossref 宕机时，哪些能力 degraded，哪些仍然能够继续工作？”
66. “如果真的用于科学研究，在称 OpenScholar production-ready 之前，你第一批会改什么？”

## 十、最终项目挑战

把 Capstone fork 成另一个领域，例如：

- legal research；
- open textbook；
- product documentation；
- codebase research。

但必须保留同一套工程纪律：

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

如果更换 domain 后迫使你重新定义 trust rule，这反而说明设计是正确的。

**Domain semantics 本来就属于 application，而不是 framework。**
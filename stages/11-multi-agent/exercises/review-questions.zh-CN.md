# Stage 11 复习题与练习

> Language: [English](review-questions.md) | 简体中文

完成理论和 runnable examples 后使用。

---

# Part A — 核心概念

1. 使用 multiple Agents 最强的理由是什么？不要只说“任务复杂”，请从 responsibility/context/Tool/authority/ownership transfer/parallelism/deployment/interoperability 解释。
2. 为什么包含四次 model call 的 deterministic workflow 仍可能只是一个 workflow，而不是四 Agent system？
3. 举三个 plain function/workflow 明显优于 Multi-Agent 的例子。
4. 两个 Agent 能否共用同一个 foundation model 仍具有不同 architecture boundary？为什么？
5. 一个 workflow 能否使用两个不同 model，却仍不构成 Multi-Agent？为什么？

---

# Part B — Delegation vs Handoff

6. 解释 `manager -> specialist as Tool` 与 `triage -> handoff -> specialist` 的语义差异，重点说明 conversation ownership。
7. 为什么 `delegate()` 后 `state.active_agent` 不变？
8. 为什么 failed `handoff()` 要保持 source Agent active？
9. Manager 委派 researcher、拿回报告并自己写 final answer，这是 handoff 吗？
10. Support Agent 把 customer conversation 转给 billing，billing 直接继续对话，属于哪一种？

---

# Part C — Context / State

11. Forward complete application state 给每个 specialist 有哪些风险？至少四项。
12. 解释 `ContextEnvelope.shared`、`private_by_agent`、`ContextPolicy.allowed_shared_keys`。
13. Full state 有 question/customer_id/api_key/legal_notes/billing_token，为 research/billing/writer 设计最小 projection。
14. Handoff 中 conversation history 与 runtime state 有什么区别？
15. 为什么 non-negotiable constraint 应保持 structured，而不是全部压进 LLM summary？

---

# Part D — Coordination / Parallelism

16. 什么时候 fan-out/fan-in 有用？
17. 为什么 `retrieve -> read -> write conclusion` 三步不能无条件并行？
18. `asyncio.gather()` 解决什么，不解决什么 coordination problem？
19. 为什么 Tiny-Agent launch 前先 validate 整个 fan-out batch？
20. 三个 worker 有一个失败时，比较 fail-fast/partial/retry/fallback policy。
21. `asyncio.gather()` 中 completion order 与 result order 有什么区别？

---

# Part E — Loop / Failure

22. Tool loop 与 handoff loop 区别？
23. `triage -> billing -> triage -> billing...` 为什么危险？
24. Exact repeated-edge detector 还会漏掉哪些 semantic loop？
25. 不使用 OS lock，举一个 deadlock-like Multi-Agent dependency。
26. 三个 Agent 使用同 model/evidence/prompt assumption，为什么可能产生 correlated error，而非 independent verification？

---

# Part F — Governance

27. 为什么 model-generated destination 只是 proposal？
28. 分别用 MCP 与 A2A 解释 `discovery != authorization`。
29. 为什么 delegation 不能成为 privilege escalation path？
30. Low-privilege manager 不能 delete production，却能调用 Admin Agent delete，存在什么 policy problem？
31. 为什么 Agent identity 不能替代 authenticated end-user/application Principal？
32. 为什么 remote Agent output 应视为 untrusted external content？

---

# Part G — A2A 1.0

33. A2A 主要解决 MCP 不主要解决的什么问题？
34. A2A Client 与 A2A Server/Remote Agent 的角色？
35. 什么是 Agent Card？
36. 为什么 Agent Skill 不必对应一个 internal Tool？
37. `Message` 与 `Artifact` 区别？
38. 什么是 `Part`？
39. 为什么 A2A 需要 stateful Task，而不是所有 interaction 都当同步 function call？
40. 举 interrupted/terminal Task states 并解释价值。
41. A2A 1.0 相比 0.3-era，Agent Card 哪个重要 shape 发生改变？
42. 为什么文档必须 pin A2A teaching target version？

---

# Part H — MCP vs A2A

43. 自己完成表格：main boundary、discovery unit、remote implementation 是否 opaque、long-running Task 是否 core、typical example。
44. 画出：`Your Agent --A2A--> Remote Research Agent --MCP--> Search Server`，解释共存原因。

---

# Part I — OpenAI Agents SDK Mapping

45. `Agent.as_tool()` 在 architecture 上表示什么？
46. SDK handoff 与 `Agent.as_tool()` 差异？
47. handoff input filtering 为什么重要？
48. 什么情况下 code orchestration 优于让 LLM 选 next Agent？
49. Offline 构造两个 Agent object：refund specialist as Tool；同一 specialist as handoff destination；不做 live model call。

---

# Part J — Coding Exercises

50. 增加 `max_failed_agent_calls` coordination budget：run-scoped、exhausted 后禁止新 work、deterministic tests。
51. 给 `ContextPolicy` 增加“对选定 Agent 禁用 private context”的 option，不改变 global default。
52. 增加 structured delegation contract：

```python
@dataclass(frozen=True)
class DelegationTask:
    goal: str
    constraints: tuple[str, ...]
    expected_output: str
```

解释为什么比 free-form string 更能保留 constraint。
53. 增加 worker timeout，但不要复制 Stage 09 retry policy；思考 timeout 应属于哪个层。
54. Fan-out failure mode 返回 partial result + explicit failure record。
55. 增加 evaluator 检查 handoff scenario 最终 expected active Agent。
56. 增加 forbidden Agent edge evaluator。
57. 用 Stage 10 tracer protocol 给 `delegate()` / `handoff()` 加 span，默认不 capture raw delegation task text。

---

# Part K — Architecture Exercises

58. Customer support（FAQ/billing/refund/account security）：比较 one Agent all Tools、manager+specialists、triage+handoffs，讨论 context/authority/latency/failure。
59. Research report 需要 retrieval/statistical analysis/legal review/writing：哪些应该 deterministic node、specialist Agent、哪些可并行？注意并不是每个名词都必须变成 Agent。
60. Production change request：设计 manager、code-review specialist、deployment specialist、human approval、permission boundary、rollback；解释 delegation 为什么不能提升 caller production authority。

---

# Part L — Evaluation Exercises

61. 比较：Single Agent quality=.87 latency=700ms cost=.012；Multi-Agent quality=.90 latency=1600ms cost=.031。哪个更好？还需要什么 product context？
62. 为 handoff system 提出 metrics：route/handoff accuracy、failed/repeated handoffs、resolution quality、cost/latency 等。
63. 为什么 Multi-Agent 与 single baseline 应尽量使用同一 test cases？
64. 怎样检测 manager delegation 到 worker execution 间的 constraint loss？
65. Team 提高 final correctness，但偶尔使用 forbidden Agent edge，能否由 weighted average 抵消？为什么？

---

# Part M — Interview Questions

66. 什么是 Multi-Agent system？请与 multiple LLM calls 区分。
67. 什么时候你不会使用 Multi-Agent？
68. Supervisor vs handoff？
69. 怎样避免 Agent loop？
70. Agent 之间怎样共享 context？
71. 怎样保护 Agent-to-Agent delegation？
72. 什么是 A2A？与 MCP 区别？
73. 怎样证明 Multi-Agent 值得新增复杂度？强回答必须有 measured baseline，而不是“架构看起来很高级”。

---

# Final Self-check

不看笔记解释：

```text
workflow vs multi-Agent
delegation vs handoff
manager vs active specialist
context projection
fan-out vs fan-in
coordination budget
handoff loop
Agent authority boundary
A2A Agent Card / Message / Task / Part / Artifact
A2A vs MCP
OpenAI Agent.as_tool vs handoff
multi-Agent vs single-Agent evaluation
```

如果这些都清楚，你学到的就不再是“怎么创建更多 Agent object”，而是怎样设计**coordination boundary**。

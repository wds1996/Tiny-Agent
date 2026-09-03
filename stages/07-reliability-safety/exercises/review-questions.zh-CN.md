# Stage 07 复习、编程与面试练习

> Language: [English](review-questions.md) | 简体中文

完成所有 Stage 07 示例后再做这些题。目标不是记 class name，而是能解释：**每一个 runtime control 为什么存在，以及它保护的是哪条边界。**

---

# Part A — 核心概念

1. 为什么应该把 model output 看作 untrusted program input，而不是自带 authority 的 instruction？
2. 为什么 `except Exception as exc: return str(exc)` 在 Agent runtime 中危险？
3. Tool failure 后，哪些信息可以安全交给模型？哪些信息只应该进入 engineering log？
4. 举三个 retryable operational failure，以及三个通常不应该 retry 的 failure。
5. 用 payment 或 email 例子解释 `retryable failure != retry-safe operation`。
6. 为什么 idempotency key 能让 network retry 更安全？
7. 为什么 `asyncio.CancelledError` 通常应继续传播，而不是变成普通 Tool failure？
8. timeout 一个 async task 与 timeout 一个跑在线程中的 sync function 有什么区别？
9. 为什么 child process 可以 terminate，而 Python 通常无法安全 hard-kill worker thread？
10. 为什么 subprocess 仍然不自动等于 secure sandbox？

---

# Part B — Validation

11. Structured Output 已经限制 model generation，为什么还要 local validation？
12. malformed Tool arguments 与 malformed application-owned Tool schema 有什么区别？
13. 为什么 `additionalProperties: false` 对 high-risk Tool 很有价值？
14. Python 中 `bool` 是 `int` 的 subclass，为什么 strict Tool boundary 仍不应该把 `True` 当整数参数接受？
15. 什么情况下适合 dynamic JSON Schema validation，而不是 Pydantic model？
16. 什么情况下 strict Pydantic model 比 dynamic JSON Schema 更方便？
17. strict mode 防什么？什么情况下 coercion 又可能是有意设计？
18. 为什么 schema validation 成功不意味着 authorization 成功？
19. 举一个语法上完全合法、但 business policy 应拒绝的 ToolCall。
20. 为什么 model-generated SQL/shell/HTML/path 还需要针对下游语法与安全语境的 validation？

---

# Part C — Retry / Backoff / Fallback

21. 从 0.5 秒开始、上限 4 秒，画出 exponential backoff sequence。
22. 多个 Agent worker 共用 dependency 时，为什么 jitter 有用？
23. 什么是 thundering herd？
24. 为什么既需要 per-tool attempt limit，也需要 run-wide retry budget？
25. retry 与 fallback 的区别是什么？
26. 为什么 silent fallback 会让 evaluation 和 incident debugging 更困难？
27. 一个 read-only search API 返回 503，是否应该 retry？你还需要知道哪些事实？
28. `send_email()` timeout 了，是否应该 retry？什么设计能让答案更安全？
29. Tool 抛出 `PermissionError`，为什么通常不应该 retry？
30. Tool 抛出 unexpected `TypeError`，为什么 runtime 不应自动把它归类为 input error？

---

# Part D — Budget 与 Loop

31. 为什么只有 `max_steps` 不是完整 resource budget？
32. 列出 Agent run 至少五种需要 budget 的资源。
33. 为什么 budget 应在 operation **之前**检查，而不是执行后？
34. LLM application 中的 Denial of Wallet 是什么？
35. 为什么一个无恶意的 model bug 也可能产生和攻击者相同的 resource-consumption pattern？
36. Tiny-Agent exact repeated-call detector 能抓住什么？
37. 举两个它抓不住的 loop pattern。
38. 为 Planner–Executor 设计一个 no-progress detector，假设 `remaining_tasks` 应持续下降。
39. 为什么 semantic loop detection 可能产生 false positive？
40. cost/tool budget 耗尽时，user-facing Agent 应怎样结束或降级？

---

# Part E — Permission 与 Governance

41. 用 MCP 解释 capability discovery 与 authorization 的区别。
42. 为什么 `Principal` 必须来自 authenticated application context，而不是 LLM？
43. 什么是 default deny？
44. 当新 MCP server 意外多暴露几个 Tool 时，为什么 default deny 很重要？
45. 用自己的话解释 OWASP 的 excessive functionality、excessive permissions、excessive autonomy。
46. 为什么 `run_shell(command: str)` 的 capability surface 远大于 `restart_service(service_id)`？
47. 已经有人类 approval，为什么仍然需要 role authorization？
48. 为什么 `approved=True` 不是一个足够好的 review representation？
49. 把 approval 绑定 Tool + arguments，怎样降低 time-of-check/time-of-use 风险？
50. Reviewer 批准 staging deployment，之后模型把 argument 改成 production，runtime 应怎样处理？
51. 为什么 downstream service/database 仍然必须 enforcement 自己的 permission？
52. 一个 read-only Agent 如果连接数据库时使用 superuser credential，为什么即使 Tool code 只写 SELECT 也是 architecture failure？

---

# Part F — Prompt Injection 与 Trust

53. direct prompt injection 与 indirect prompt injection 有什么区别？
54. 举一个涉及 RAG 的 indirect injection 例子。
55. 再举一个涉及 MCP Resource 或 Tool result 的例子。
56. 为什么 `<untrusted>...</untrusted>` delimiter 不能形成硬 security boundary？
57. 一个可绕过的 regex/keyword injection detector 为什么仍有价值？
58. 为什么这种 detector 永远不能成为唯一 permission check？
59. 解释 Agent 中的 data plane 与 control plane。
60. retrieved text 属于哪一类？Tool allowlist 属于哪一类？
61. 为什么 retrieved document 即使写成“系统指令”，也不应该有权重写 permission policy？
62. 当 LLM 真的被恶意 instruction 影响时，least privilege 如何限制损害？
63. 为什么 RAG 本身并不能防 prompt injection？
64. 为什么 credential 通常应该留在 Tool adapter，而不是 model context？

---

# Part G — Sandboxing

65. `asyncio.to_thread()` 提供了哪些执行性质？又**没有**提供哪些安全性质？
66. child process 比 worker thread 多了哪一项重要 control？
67. 普通用户启动的 subprocess 仍可能访问什么？
68. 列出至少六种 serious untrusted-code sandbox 可能需要的 control。
69. 为什么 network egress control 可能与 filesystem isolation 同样重要？
70. ephemeral workspace 为什么有用？
71. 即使在 sandbox 中，为什么也应该最小化 secret？
72. 什么情况下 generic shell Tool 可以被 justify？你会要求哪些 control？

---

# Part H — 编程练习

## Exercise 1 — 增加 External Request Budget

扩展 `ExecutionBudget` / `BudgetLedger`，增加“external requests 最大次数”，并与 Tool call 次数分开。

要求：

- deterministic tests；
- request 前检查；
- 清晰 model-safe exhaustion reason；
- tests 中不要依赖真实 wall-clock sleep。

## Exercise 2 — 带 Idempotency Metadata 的 Retry

创建 mock `create_order` Tool，包含 `idempotency_key` argument。

演示：

```text
first attempt applies order but loses response
second attempt receives same key
no duplicate order is created
```

然后解释为什么该 operation 可以标记 `retry_safe=True`。

## Exercise 3 — No-progress Detector

为下面 state 构建 detector：

```python
{"remaining_tasks": 3}
```

当连续 N 次 workflow transition 都没有改善时停止。

同时测试：

- legitimate temporary plateau；
- true no-progress loop。

## Exercise 4 — Expiring Approval

扩展 `ApprovalGrant`，加入 application-owned expiry timestamp，或 issued-at + TTL。

回答：

- 应使用哪种 clock？
- expiry 是否会让 grant 自动变成 cryptographically trustworthy？
- production approval record 还需要什么？

## Exercise 5 — Resource Version Binding

Approval 除了绑定 Tool arguments，还绑定 resource version：

```text
report_id = r-7
version = 12
```

如果 review 后 report 已变为 version 13，拒绝 execution。

## Exercise 6 — 按 Route 缩小 Permission

利用 Stage 02 routing：

```text
research route
    -> read-only Tools

operations route
    -> operational Tools
```

不要把所有 route 的 Tool union 暴露给每条路径。

## Exercise 7 — MCP Allowlist

连接一个 mock MCP server，它暴露 5 个 Tool，但对某一 Agent role 只注册/允许 2 个。

解释：

```text
discovered tools
!=
model-visible tools
!=
executable tools
```

## Exercise 8 — Output Sanitization

创建包含 HTML 的 Tool result，展示 web UI 应怎样 escape/render，而不是把 model/Tool text 当作 raw DOM 插入。

## Exercise 9 — Process Boundary

扩展 `sandbox_boundary.py`，让 child process：

- 接收固定 input file；
- 只向 temp directory 写入；
- 有 timeout；
- timeout 后被 kill；
- 清理 workspace。

然后列出它仍然**没有**提供的关键 isolation guarantee。

## Exercise 10 — Guarded ReAct Adapter

构建一个 **async** ReAct runtime，把所有 Tool execution 委托给 `GuardedToolExecutor`。

保持职责分离：

```text
Agent loop
    -> model/tool feedback

Guarded executor
    -> validation/permission/budget/retry/timeout
```

不要在 Agent loop 里复制一遍 policy logic。

---

# Part I — 面试题

73. “你会怎样让一个 LLM Agent 安全使用公司内部 Tool？”
74. “Structured Outputs 已保证合法 JSON，为什么还要 validation？”
75. “怎样判断一个失败 ToolCall 是否应该 retry？”
76. “timeout 和 cancellation 有什么区别？”
77. “为什么 `asyncio.wait_for(asyncio.to_thread(...))` 无法杀掉一个卡死 native library call？”
78. “怎样防止 Agent 无限烧钱？”
79. “怎样检测 Agent loop？”
80. “为什么 `max_steps` 不够？”
81. “Tool-using Agent 怎样实现 least privilege？”
82. “什么是 Excessive Agency？”
83. “什么是 indirect prompt injection？”
84. “RAG 能防 prompt injection 吗？”
85. “怎样防御 retrieved document 里的恶意 instruction？”
86. “HITL approval 与 authorization 有什么区别？”
87. “怎样防止 reviewed ToolCall 在 approval 后被篡改？”
88. “什么条件才能把一个执行环境叫 sandbox？”
89. “你会把 shell Tool 暴露给 LLM 吗？在什么条件下？”
90. “Tool failure 时，既不向模型泄露 secret，又要支持工程排错，应该记录什么？”

---

# Part J — Architecture Challenge

设计一个 production-oriented Agent，能够：

```text
search internal documents
read customer records
send an email
restart a service
```

对每个 Tool 定义：

- JSON schema；
- model-visible description；
- allowed roles；
- 是否需要 HITL；
- exact approval payload；
- timeout；
- retry policy；
- retry-safe / idempotency reasoning；
- global budget impact；
- credential scope；
- audit event；
- external-content trust assumption；
- sandbox/isolation requirement。

最后回答：

> **假设模型已经被 indirect prompt injection 完全操纵，在你的 deterministic policy 下，它最多还能造成多大损害？**

这个问题，是检验 Agent architecture 是否真的实现 least privilege 的最好问题之一。

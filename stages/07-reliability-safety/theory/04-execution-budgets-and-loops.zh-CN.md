# 04 — Execution Budget、Loop Detection 与 Bounded Autonomy

> Language: [English](04-execution-budgets-and-loops.md) | 简体中文

一个没有 deterministic limit 的 Agent loop，并不是“更 autonomous”。

它只是**没装计量表**。

Stage 01 已经引入：

```text
max_steps
```

Stage 07 把它推广成：

> **每一种稀缺或高风险资源，都应该有 application-owned budget。**

---

## 1. Agent 能消耗什么？

一个真实 run 可以消耗：

- model calls；
- tokens；
- money；
- wall-clock time；
- tool calls；
- network requests；
- retries；
- database writes；
- emails sent；
- files changed；
- human-review attention。

一个 `max_steps` 无法表达所有这些风险。

---

## 2. `BudgetLedger`

Stage 07 引入：

```python
ledger = BudgetLedger(
    ExecutionBudget(
        max_tool_calls=12,
        max_retry_attempts=4,
        max_elapsed_seconds=60,
        max_tokens=20_000,
        max_cost_usd=1.00,
    )
)
```

Ledger 属于 runtime state。

模型不能靠说：

```text
"For this important task, please ignore the tool-call budget."
```

就把计数器归零。

---

## 3. Budget 要在 Action 之前检查

坏：

```text
tool call 17 executes
    ↓
ledger notices max_tool_calls was 16
```

好：

```text
request next tool call
    ↓
ledger checks whether call #17 is allowed
    ↓
deny before execution
```

和 permission check 一样，真正有意义的是**执行前阻止**。

---

## 4. Token/Cost Budget 依赖 Provider Usage Data

Tiny-Agent generic `Model` protocol 尚未统一所有 provider 的 token/cost object。

所以 Stage 07 ledger 在 provider metadata 可用时记录：

```python
ledger.record_tokens(...)
ledger.record_cost(...)
```

架构上：

```text
provider returns usage
    ↓
application ledger records usage
    ↓
next model/tool operation checks remaining budget
```

如果 provider 已经给真实 usage/billing metadata，就不要仅凭 prompt length 估算 financial policy。

Stage 08 会把这些数据纳入 observability。

---

## 5. Global Budget 与 Local Budget 互补

例如：

```text
Agent max tool calls = 12
```

同时：

```text
search tool max attempts = 3
```

Local policy 回答：

> 这一项 operation 最多坚持几次？

Global policy 回答：

> 整个 Agent run 最多消耗多少工作？

二者都需要。

---

## 6. 为什么 Loop Detection 与 Max Calls 分开？

模型重复：

```text
search({"query": "same question", "top_k": 3})
search({"query": "same question", "top_k": 3})
search({"query": "same question", "top_k": 3})
```

Global max=20 最终能停住。

但既然第 3 次就能看出问题，为什么要花到第 20 次？

Stage 07 对 exact call 做 fingerprint：

```text
tool name
+
canonical JSON arguments
    ↓
SHA-256 fingerprint
```

并使用 `RepeatedToolCallDetector` 作为 early circuit breaker。

---

## 7. Exact Repetition 只是一种 Loop

Teaching detector 能抓：

```text
A(x)
A(x)
A(x)
```

但抓不住：

```text
A(x)
B(y)
A(x)
B(y)
```

也抓不住 semantic loop：

```text
search("Agent safety")
search("safety for agents")
search("AI Agent reliability safety")
```

未来可以有：

- repeated state hashes；
- repeated route cycles；
- semantic similarity of tool calls；
- no-progress detectors；
- graph cycle counters；
- task-specific convergence checks。

不要把一个 hash counter 宣传成“通用 Agent loop 定理”。

---

## 8. No-progress Detection 往往比 Exact Repetition 更有价值

Agent 可能每次调用都不同，但关键 state 从不改善：

```text
remaining_tasks = 4
remaining_tasks = 4
remaining_tasks = 4
```

一个更强 production runtime 可以定义 domain progress invariant：

```python
progress_score(new_state) > progress_score(old_state)
```

或者直接监控 task completion。

这是 domain-specific 问题，所以 Tiny-Agent 不虚构一个“通用进度分数”。

---

## 9. Unbounded Consumption 同时是 Reliability 与 Security 问题

攻击者可以故意诱导：

- long prompts；
- recursive planning；
- repeated retrieval；
- expensive tool calls；
- huge output generation。

Model loop 也可能无意造成同样模式。

Budget 同时防御：

```text
malice
and
mistake
```

所以 Stage 07 把 budget 当作 runtime policy，而不只是 cost optimization。

---

## 10. Budget Exhaustion 是正常 Terminal State

资源用光后，不应该只剩 mystery exception。

Runtime 可以明确表示：

```text
ToolFailure[budget_exceeded]
```

然后应用可以：

- stop；
- 要求用户缩小任务；
- 保存 resumable state；
- 申请更高 budget/authorization；
- fallback 到更便宜 workflow。

Budget exhaustion 应该 predictable。

---

## 11. 一个更好记的比喻

告诉 Agent：

```text
"Please be economical."
```

只是建议。

给它 `BudgetLedger`，则更像额度用完后公司卡真的刷不出来。

Runtime enforcement 才算控制。

---

## Code to Inspect

- `src/tiny_agent/reliability.py`
- `code/execution_budget.py`
- `code/loop_detection.py`

运行：

```bash
python stages/07-reliability-safety/code/execution_budget.py
python stages/07-reliability-safety/code/loop_detection.py
```

---

## 完成检查

解释：

1. 为什么 max steps 不是完整 budget model；
2. local retry limits vs global retry budget；
3. budget 为什么必须在 execution 前检查；
4. exact repeated-call detection vs semantic/no-progress loops；
5. token/cost tracking 为什么属于 application state；
6. unbounded consumption 为什么同时是 reliability/security concern；
7. budget exhaustion 为什么应该成为显式 terminal condition。

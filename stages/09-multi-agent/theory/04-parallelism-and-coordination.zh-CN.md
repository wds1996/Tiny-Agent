# 04 — Parallelism、Coordination 与 Failure Mode

> Language: [English](04-parallelism-and-coordination.md) | 简体中文

即使所有 Agent 都跑在同一个 Python process 里，只要多个 worker 能独立运行、失败、冲突或转移 control，Multi-Agent 就开始出现“distributed-systems-shaped”问题。

Coordination 因此成为一等设计问题。

---

## 1. Fan-out / Fan-in

```text
              -> Agent A -\
manager ------> Agent B ---> aggregate
              -> Agent C -/
```

适用于独立 subtask，例如 quality/cost/risk analysis、independent retrieval strategies、multiple domain reviews。

---

## 2. Concurrency != Free Speed

并行可能降低 wall-clock latency，但增加 model calls、API pressure、cost、rate-limit risk、memory pressure 与 fan-in complexity。

三个 worker 各花 `$0.02`，可能 latency 下降但成本变成 3 倍。是否值得，应由 Stage 08 metrics 回答。

---

## 3. `asyncio.gather()` 不是 Supervisor

```python
results = await asyncio.gather(a(), b(), c())
```

只解决 scheduling/collection，不解决：subtask 是否正确、output 是否可信、冲突如何处理、worker 失败怎么办、是否接受 partial result、谁负责 final answer。

Fan-in 是 application responsibility。

---

## 4. Parallel Batch 要先整体 Prevalidate

坏：先 reserve A，再发现 B forbidden，最后没人启动，但预算已经消耗。

好：

```text
validate all edges/Agents
check parallel limit
check total budget
-> reserve batch
-> launch
```

这是一个小型 transactional design principle。

---

## 5. Worker Failure Policy

```text
quality -> success
cost    -> failure
risk    -> success
```

可选：

- fail fast：所有 component 都必须成功；
- partial result：允许部分价值；
- retry specialist：必须满足 Stage 07 retry-safe 规则；
- fallback specialist：backup contract compatible。

答案属于 application，不属于“multi-Agent”这个形容词。

---

## 6. Coordination Loop

Tool loop 会升级成 Agent loop：

```text
A -> B -> A -> B -> ...
```

或 supervisor/researcher 反复互相甩回去。

使用：max Agent calls、max handoffs、repeated-edge limit、wall-clock/token/cost budget、no-progress detection。

---

## 7. Deadlock-like Behavior

```text
Agent A: 需要 B 的结论
Agent B: 需要 A 的结论
```

没有 OS mutex，却仍无法 progress。

已知 dependency 应用显式 DAG/workflow，不要指望两个 conversational Agent 靠礼貌沟通自己走出循环依赖。

---

## 8. Duplicate Work

两个 specialist 可能重复 expensive search。这有时是 intentional diversity，也可能只是浪费。

Stage 08 trace 可以发现并判断这个成本是否换来了有价值 diversity。

---

## 9. Conflicting Results

```text
Agent A: release is safe
Agent B: release is unsafe
```

不要简单“两个 Agent 多数投票”——两票也没有多数的神奇真理。

需要 evidence comparison、domain precedence、deterministic rule、third reviewer 或 human approval。

多个自信语言模型发生分歧，不会因为把 confidence 平均一下就生成事实。

---

## 10. Diversity vs Correlated Failure

三个 Agent 若使用同 model、prompt、evidence、assumption，错误很可能高度相关，并不构成 independent verification。

真正 diversity 可来自不同 evidence/tool/instruction/model family、adversarial review role、deterministic validator。

但 diversity 也增加复杂度，必须测量。

---

## 11. Aggregation 保留 Provenance

不要只说：

```text
"Experts say X."
```

应保留：

```text
quality_agent -> finding A
risk_agent    -> finding B
cost_agent    -> finding C
```

便于 debug/eval。

---

## 12. Ordering Semantics

`asyncio.gather()` 返回 input order，即使 completion order 不同。

这有利 deterministic test，但 streaming/cancellation/early-stop/first-success race 仍可能依赖 completion order。

```text
result ordering != execution ordering
```

---

## 13. Cancellation

Parent cancel 时，production 应定义：cancel child work（能取消时）、停止新 delegation、保留 trace/audit、清理 resource。

Stage 09 不声称已经解决 full distributed cancellation，留到 Stage 10 infrastructure。

---

## 14. Long-running Remote Agent

分钟/小时级 remote Agent 不适合普通 function-call 心智模型，需要 task ID、status、input-required、auth-required、completed/failed/canceled、artifact delivery、stream/push update。

A2A 正式建模这些概念。

---

## 15. Coordination Observability

关注：

```text
agent_calls
handoffs
unique_agents
failed_agent_calls
parallel_width
coordination_latency
coordination_cost
handoff_loop_rate
```

并与 simpler baseline 比较。

没有这些 measurement 的 Multi-Agent optimization，很多时候只是“架构占星术”。

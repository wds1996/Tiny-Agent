# Stage 02 练习 — Planning、Routing 与 Deterministic Workflow

这些题测试的是 architecture judgment，不是 API memorization。

## Part A — Core Concepts

不看笔记回答：

1. Workflow 与 Agent 在 control flow 上的差别是什么？
2. Workflow 能包含 LLM call 与 Tool 吗？举例。
3. Agent 能把 deterministic workflow 当成一个 Tool 调用吗？为什么这通常是好设计？
4. “deterministic when possible, agentic when useful” 在实际工程里是什么意思？
5. 为什么 autonomy 更多不自动意味着 system 更好？
6. 哪些 signal 表明 fixed Workflow 比 ReAct 更合适？
7. 哪些 signal 表明 dynamic Agent 值得引入？

## Part B — Routing

8. Router 应决定什么？什么应该保留为 application-owned dispatch？
9. 什么情况下 `RuleRouter` 优于 LLM Router？
10. 为什么 LLM route 应 constrained 到 allowlist / enum？
11. 为什么 free-form routing prose 比 structured route object 弱？
12. route category overlap 为什么即使面对强 model 也会制造错误？
13. 什么是 hybrid router？画出流程。
14. 为什么 `confidence: 0.97` 不应直接解释成 calibrated 97% correctness probability？
15. Routing 如何缩小 downstream permission / Tool surface？

## Part C — Planning

16. ReAct 中已经隐式发生了什么 planning？
17. explicit Planner 额外提供了什么？
18. 为什么 Plan 应描述 high-level milestone，而不是提前列出所有 ToolCall？
19. 什么使 PlanStep 太粗？什么又使它太细？
20. 为什么 Plan output 应是 structured application data？
21. 为什么 model-generated Plan 必须 execution 前 validation？
22. task decomposition 与 planning 有什么区别？
23. long Plan 为什么容易 stale？

## Part D — Planner–Executor

24. 列出 Planner responsibility。
25. 列出 Executor responsibility。
26. 列出 Workflow / orchestrator responsibility。
27. 为什么 Workflow 是独立 responsibility，而不是“随便 glue 一下”？
28. Stage 01 `AgentRuntime` 能否作为 Step Executor？解释 hierarchy。
29. 为什么 Executor 通常应该 scoped 到一个 PlanStep？
30. 为什么 Executor 需要 selected completed result？
31. long-running task 中为什么这些 completed result 最终必须 filter / summarize？
32. 为什么 syntactically valid Plan 不能授予执行 permission？

## Part E — Replanning

33. 给出三个 legitimate replanning trigger。
34. 为什么每个 successful step 后都 replan 往往是 design smell？
35. 为什么 Replanner 应生成 remaining work，而不是盲目重复全部 Plan？
36. `max_plan_steps`、`max_total_steps`、`max_replans` 分别控制什么 failure mode？
37. 为什么 unlimited replanning 也是 infinite-loop risk？
38. Tiny-Agent 中 safe `StepFailure` 与 unexpected Python exception 有什么区别？
39. 为什么 unexpected exception detail 不应进入 model-backed Replanner prompt？

## Part F — Architecture Classification

对每个 requirement 选择**最简单合理 pattern**并说明原因。

可选：

```text
single LLM call
deterministic workflow
router
planner-executor
ReAct Agent
```

### Case 1

PDF upload 永远需要：

```text
parse -> normalize -> chunk -> embed -> index
```

### Case 2

free-form support request 必须进入三个成熟 Workflow 之一：

```text
billing / technical / general
```

### Case 3

API event 已经明确包含：

```text
event_type="REFUND_REQUESTED"
```

是否还应该让 LLM 再 classify 一次？

### Case 4

research task 的 major milestone 随 request 变化，但每个 milestone 内又可能需要多次 adaptive search。

使用 Stage 01 + Stage 02 component 设计两层 architecture。

### Case 5

deployment pipeline 永远执行：

```text
tests
-> build image
-> scan
-> human approval
-> deploy
```

LLM 在哪里可能有价值，但又不应该拥有 pipeline order？

### Case 6

incident Plan 要读取 primary logs，但服务不可用，存在 fallback archive。

什么应该 trigger？哪些已经成功的 work 不应该自动 rerun？

## Part G — Coding Exercises

### Exercise 1 — Improve Deterministic Routing

扩展 `../code/deterministic_router.py`，加入 `account` route。

要求：

- stable deterministic signal 必须先于 fallback；
- 至少 5 个 test / example；
- 说明 `account`、`billing`、`technical` 的 overlap。

### Exercise 2 — Hybrid Router

实现：

```text
known event fields
-> deterministic route
otherwise
-> LLMRouter
```

记录多少 request 真正需要 LLM call。

比较与 LLM-only router 的 expected latency / cost。

### Exercise 3 — Routing Dataset

创建 30 条 labeled support message：

```json
{
  "input": "...",
  "expected_route": "billing"
}
```

必须包含 ambiguous boundary case，而不能只写明显 keyword case。

Stage 08 会把它升级成正式 evaluation set。

### Exercise 4 — Plan Validation

增加 application policy：拒绝 description 包含明确 forbidden action 的 PlanStep。

然后解释：为什么 text matching 只能作为 teaching exercise，而不能作为 production authorization system？

### Exercise 5 — Bounded Planning

修改 `max_plan_steps`：

```text
3
vs
6
```

对相同 task 比较 Planner behavior。

不要只看 Plan valid 与否；检查额外 step 是否真的增加 useful information。

### Exercise 6 — `StepFailure`

修改 `../code/bounded_replanning.py`：

1. primary source 先 raise safe actionable `StepFailure`；
2. 再改成包含 fake secret 的 unexpected `RuntimeError`；
3. 验证 secret 不会进入 `PlanRunResult.failure_reason`。

### Exercise 7 — Planner + ReAct Executor

运行 `../code/planner_executor_agent.py`。

对每个 high-level step 记录：

- Planner description；
- Executor 使用的 Tools；
- ReAct turn 数；
- final step result。

判断：哪些 decision 属于 global Planner，哪些只有 local observation 出现后才能决定？

## Part H — 面试题

准备 60–90 秒回答：

1. Workflow 和 Agent 有什么区别？
2. 企业系统为什么不应该所有步骤都交给 LLM？
3. 什么时候 rule-based routing，什么时候 LLM routing？
4. 如何防止 LLM Router 执行 arbitrary unauthorized branch？
5. ReAct 与 Planner–Executor 的主要差异是什么？
6. explicit Plan 为什么有利于 long task？
7. 什么情况下应该 replan？
8. 如何防止 Planner–Executor 无限循环 / cost 爆炸？
9. Executor 能否是另一个 Agent？优缺点是什么？
10. 如何分别测试 Router / Planner，而不是只看一次 end-to-end demo？

## Completion Challenge

设计 internal assistant：

> 处理 simple FAQ、billing ticket、open-ended technical incident investigation。

必须使用 **minimum necessary autonomy**，并指出：

- deterministic rules；
- semantic routing；
- fixed workflows；
- 是否需要 Planner；
- 是否需要 ReAct Executor；
- Tool / permission boundary；
- stopping / replanning budgets；
- production rollout 前要 evaluate 什么。

如果最终答案是：

```text
one giant Agent with all Tools
```

请重新设计。
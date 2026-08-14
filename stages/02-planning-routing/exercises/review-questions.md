# Stage 02 Exercises — Planning, Routing & Deterministic Workflows

These exercises are designed to test architectural judgment, not API memorization.

## Part A — Core concepts

Answer without looking at the notes.

1. What is the control-flow difference between a Workflow and an Agent?
2. Can a Workflow contain LLM calls and tools? Give an example.
3. Can an Agent invoke a deterministic workflow as one tool? Why is that often desirable?
4. What does "deterministic when possible, agentic when useful" mean in practice?
5. Why is more autonomy not automatically a better system?
6. What signals suggest a fixed workflow is preferable to a ReAct loop?
7. What signals suggest a dynamic Agent is justified?

## Part B — Routing

8. What should a Router decide, and what should remain application-owned dispatch?
9. When is a `RuleRouter` preferable to an LLM Router?
10. Why should LLM routes be constrained to an allowlist/enum?
11. Why is free-form routing prose weaker than a structured route object?
12. Why can overlapping category definitions create routing errors even with a strong model?
13. What is a hybrid router? Sketch one.
14. Why should you not treat a model-generated `confidence: 0.97` as a calibrated 97% probability?
15. How can routing reduce downstream permissions and tool surface?

## Part C — Planning

16. What planning already happens implicitly in ReAct?
17. What does an explicit Planner add?
18. Why should a plan contain high-level milestones rather than every tool call?
19. What makes a PlanStep too coarse? Too fine?
20. Why should plan output be structured application data?
21. Why must a model-generated Plan be validated before execution?
22. What is the difference between task decomposition and planning?
23. Why can long plans become stale?

## Part D — Planner–Executor

24. List the responsibilities of the Planner.
25. List the responsibilities of the Executor.
26. List the responsibilities of the Workflow/orchestrator.
27. Why is the Workflow a separate responsibility rather than just glue code?
28. Can a Stage 01 `AgentRuntime` serve as a Step Executor? Explain the hierarchy.
29. Why should an Executor usually be scoped to one PlanStep?
30. Why does the Executor need selected completed results from previous steps?
31. Why should those completed results eventually be filtered/summarized for long-running tasks?
32. Why does a syntactically valid Plan not grant permission to perform its actions?

## Part E — Replanning

33. Give three legitimate triggers for replanning.
34. Why is replanning after every successful step often a design smell?
35. Why should a Replanner return remaining work rather than blindly repeat the entire plan?
36. What different failures are controlled by `max_plan_steps`, `max_total_steps`, and `max_replans`?
37. Why is unlimited replanning another form of infinite-loop risk?
38. What is the difference between a known safe `StepFailure` and an unexpected Python exception in Tiny-Agent?
39. Why should unexpected exception details stay out of a model-backed Replanner prompt?

## Part F — Architecture classification

For each requirement, choose the simplest reasonable pattern and justify it.

### Case 1

A PDF upload must always be parsed, normalized, chunked, embedded, and indexed.

Choose from:

```text
single LLM call / deterministic workflow / router / planner-executor / ReAct Agent
```

### Case 2

A support request must be sent to one of three mature downstream workflows: billing, technical, or general. The request is free-form language.

### Case 3

An API event already contains `event_type="REFUND_REQUESTED"`.

Should an LLM classify it again?

### Case 4

A research request has task-specific major milestones, but each milestone may require several adaptive searches.

Design a two-level architecture using Stage 01 and Stage 02 components.

### Case 5

A deployment pipeline always runs tests, builds an image, scans it, then deploys after approval.

Where, if anywhere, might an LLM be useful without owning the pipeline order?

### Case 6

An incident investigation plan says to read the primary logs, but that service is unavailable. A fallback archive exists.

What should trigger, and what should **not** be rerun automatically?

## Part G — Coding exercises

### Exercise 1 — Improve deterministic routing

Extend [`../code/deterministic_router.py`](../code/deterministic_router.py) with an `account` route.

Requirements:

- stable deterministic signals should be evaluated before the fallback;
- add at least five tests/examples;
- document any overlap between `account`, `billing`, and `technical`.

### Exercise 2 — Hybrid router

Implement:

```text
known event fields -> deterministic route
otherwise -> LLMRouter
```

Record how many requests require an LLM call.

Question: how does this affect expected latency and cost compared with an LLM-only router?

### Exercise 3 — Routing dataset

Create 30 labeled support messages:

```json
{"input":"...","expected_route":"billing"}
```

Include ambiguous boundary cases. Do not only write obvious keyword examples.

Later, Stage 08 will turn this into a formal evaluation set.

### Exercise 4 — Plan validation

Add an application policy that rejects PlanSteps whose descriptions contain an explicitly forbidden action.

Think carefully: why is text matching only a teaching exercise rather than a sufficient production authorization system?

### Exercise 5 — Bounded planning

Change `max_plan_steps` and observe how the Planner behaves for the same task.

Compare:

```text
max_plan_steps = 3
max_plan_steps = 6
```

Evaluate not just whether the plan is valid, but whether extra steps add useful information.

### Exercise 6 — StepFailure

Modify [`../code/bounded_replanning.py`](../code/bounded_replanning.py):

- first make the primary source raise a `StepFailure` with a safe actionable message;
- then replace it with an unexpected `RuntimeError` containing a fake secret;
- verify that the fake secret does not enter `PlanRunResult.failure_reason`.

### Exercise 7 — Planner + ReAct Executor

Run [`../code/planner_executor_agent.py`](../code/planner_executor_agent.py).

For each high-level step, record:

- Planner step description;
- tools used by the Executor;
- number of ReAct turns;
- final step result.

Question: which decisions belong globally to the Planner, and which only appear after local observations?

## Part H — Interview questions

Prepare concise 60–90 second answers.

1. Workflow 和 Agent 有什么区别？
2. 企业系统为什么不应该所有步骤都交给 LLM 决策？
3. 什么时候使用 rule-based routing，什么时候使用 LLM routing？
4. 如何避免 LLM Router 执行任意未授权分支？
5. ReAct 和 Plan-and-Execute / Planner–Executor 的主要区别是什么？
6. 为什么显式 Plan 对长任务有价值？
7. 什么情况下应该 Replan？
8. 如何防止 Planner–Executor 无限循环或成本爆炸？
9. Executor 是否可以是另一个 Agent？这样做有什么优缺点？
10. 如何测试 Router 和 Planner，而不是只看一个 end-to-end Demo？

## Completion challenge

Design an architecture for this task:

> Build an internal assistant that handles simple FAQs, billing tickets, and open-ended technical incident investigations.

Your design must use the **minimum necessary autonomy** and identify:

- deterministic rules;
- semantic routing;
- fixed workflows;
- any Planner;
- any ReAct Executor;
- tool/permission boundaries;
- stopping/replanning budgets;
- what you would evaluate before production rollout.

If your answer is "one giant Agent with all tools," redesign it.

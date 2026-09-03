# Stage 02 — Planning、Routing 与 Deterministic Workflow

Stage 01 已经构建了 dynamic ReAct loop。Stage 02 接下来问一个更重要的工程问题：

> **这一部分 control flow，真的应该让 model 决定吗？**

Agent system 一个非常常见的错误，是把每一个 branch、sequence、retry、transformation 都做成 LLM decision。

真实系统通常在“可预测的工作继续由 ordinary software 负责、只有 semantic judgment / dynamic decomposition 才交给 model”时，更容易测试、更便宜、更可靠。

Stage 02 因此介绍从基础 ReAct loop 到 Stage 03 stateful graph orchestration 之间最重要的 orchestration patterns。

## 前置要求

完成：

- `../00-foundations/`
- `../01-react-runtime/`

并确认你理解：

- Structured Output；
- Function / Tool Calling；
- ReAct action-observation loop；
- model-provider adapter；
- model decision 与 runtime execution 的差别。

## 学习目标

完成本阶段后，你应该能够：

1. 区分 single LLM call、workflow、router、planner-executor system 与 autonomous Agent；
2. 解释为什么 autonomy 是 cost / reliability trade-off，而不是“架构升级奖励”；
3. 判断哪些 control-flow decision 应保持 deterministic code；
4. 在 LLM router 之前优先实现 deterministic routing；
5. rule 不够时使用 schema-constrained semantic routing；
6. 把 route decision 与 deterministic dispatch 分开；
7. 区分 ReAct 的 local / implicit planning 与 explicit high-level planning；
8. 把 Plan 表示成 application data，而不是 free-form prose；
9. 分离 Planner、Executor、Workflow responsibility；
10. execution 前 validate / bound Plan；
11. 只有 observation 使当前 Plan 失效时才 replan；
12. 区分 replanning 与“每完成一步就重新生成整个计划”；
13. enforce total-step / replan budget；
14. 解释为什么 model 自己报的 confidence 不是 calibrated probability；
15. 识别 Workflow 比 Agent 更合理的场景。

## Complexity Ladder

```text
Single deterministic function
          |
          v
Single LLM call
          |
          v
Prompt / processing chain
          |
          v
Deterministic workflow
          |
          v
Routing workflow
          |
          v
Planner -> Executor workflow
          |
          v
Bounded replanning
          |
          v
Open-ended autonomous Agent
```

向下增加 flexibility，通常也会增加：

- model calls；
- latency；
- token cost；
- nondeterminism；
- failure mode；
- testing difficulty；
- observability requirement。

> **使用能够把问题解决好的、动态性最低的架构。**

## 推荐顺序

### Part A — Workflow vs Agent

1. `theory/01-agent-vs-workflow.md`
2. `code/deterministic_router.py`

### Part B — Routing

3. `theory/02-routing-patterns.md`
4. `../../src/tiny_agent/decision.py`
5. `../../src/tiny_agent/models/openai_structured.py`
6. `../../src/tiny_agent/workflows.py`
7. `code/openai_router.py`

### Part C — Planning / Execution

8. `theory/03-planning-and-replanning.md`
9. `theory/04-planner-executor.md`
10. `code/planner_executor_agent.py`
11. `code/bounded_replanning.py`

### Part D — Review

12. `exercises/review-questions.md`
13. `../../tests/test_workflows.py`
14. `../../tests/test_structured_decision.py`

中文理论与练习使用同目录 `*.zh-CN.md`；代码、tests 仍共用同一份实现。

## Pattern 1 — Deterministic Workflow

如果 path 已知，就把 path 写进 code：

```text
Input
  |
  v
validate
  |
  v
transform
  |
  v
save
  |
  v
END
```

如果 application 已经知道 validation 应该发生在 save 之前，就不要再请 LLM 每次重新决定一次。

适合：

- document ingestion；
- fixed approval process；
- ETL；
- schema validation；
- known API sequence；
- deterministic business rule。

## Pattern 2 — Routing

Routing 只增加一个 semantic decision，downstream execution 仍然明确：

```text
                         +--> billing workflow
User request -> Router --+--> technical workflow
                         +--> general workflow
```

关键分离：

```text
Router chooses destination
        !=
Router executes arbitrary downstream action
```

### 能 Rule-Based 就先 Rule-Based

```python
if is_refund_request(request):
    route = "billing"
elif contains_known_error_code(request):
    route = "technical"
else:
    route = "general"
```

便宜、可测试、predictable。

### Semantic Ambiguity 再用 LLM Router

```json
{
  "route": "technical",
  "reason": "The user describes a product failure after login."
}
```

`route` 仍然只能来自 application-owned enum；model 无权发明新 destination。

## Pattern 3 — Explicit Planning

ReAct 本身就有 local planning：

```text
observe -> choose next action -> observe -> ...
```

explicit planning 把 global strategy 拆出来：

```text
Task
  |
  v
Planner
  |
  v
Plan
  |
  v
Executor(step 1)
  |
  v
Executor(step 2)
  |
  v
...
```

Tiny-Agent 把 Plan 表示成 data：

```python
Plan(
    objective="Prepare an incident brief",
    steps=(
        PlanStep(
            "health",
            "Inspect current service health.",
        ),
        PlanStep(
            "deploys",
            "Inspect recent deployments.",
        ),
        PlanStep(
            "brief",
            "Draft an evidence-based incident brief.",
        ),
    ),
)
```

Plan 不是 truth，而是需要 validation / budget / observation correction 的 proposed strategy。

## Pattern 4 — Bounded Replanning

不要默认每成功一步都重做 Plan。

```text
plan
  |
  v
execute step
  |
  +-- success --> next existing step
  |
  +-- failure --> current plan invalid?
                      |
                      +-- no --> local handling / stop
                      |
                      +-- yes --> bounded replan
```

replanning 应是明确 recovery transition。

所以 Stage 02 同时有：

```text
max_total_steps
max_replans
```

无限 replanning 只是把 infinite-loop problem 搬到了更高一层。

## Planner / Executor / Workflow Responsibility

```text
Planner
-------
understand global objective
choose high-level milestones
order major work
avoid unnecessary steps

Executor
--------
finish one assigned step
gather observations
use Tools when necessary
return concrete result / failure

Workflow
--------
validate Plan
enforce budgets
pass completed context
record results
decide when replanning is allowed
stop safely
```

Executor 可以是：

- deterministic Python；
- Tool-specific service；
- human；
- Stage 01 `AgentRuntime`；
- later LangGraph subgraph。

这种 composability 正是拆分 responsibility 的价值。

## Structured Decision Interface

Stage 02 增加：

```text
src/tiny_agent/decision.py
```

概念接口：

```python
class StructuredDecisionModel(Protocol):
    def decide(..., schema: dict) -> dict:
        ...
```

它与 Stage 01 `Model` protocol 有意不同。

Stage 01 问：

```text
Agent 下一步做什么？
-> ToolCall OR final answer
```

Stage 02 的 control component 问：

```text
Which route?
What bounded plan?
What remaining plan after failure?
-> schema-constrained application data
```

Structured Output 从 Stage 00 的 output contract，成为 Stage 02 的 orchestration primitive。

## Hybrid Router 示例

```text
User message
    |
    v
cheap deterministic rules
    |
    +-- certain match ----------> handler
    |
    +-- ambiguous
          |
          v
       LLM Router
          |
          v
   schema-constrained route
          |
          v
 deterministic dispatch
```

很多生产系统用这种结构，比“每个 request 都先问 LLM 怎么路由”更合理。

## Planner + Agent Executor 示例

```text
                     User task
                        |
                        v
                Structured Planner
                        |
                        v
                     Plan
              +---------+---------+
              |                   |
              v                   v
        executor step 1      executor step 2
        (AgentRuntime)       (AgentRuntime)
              |                   |
              v                   v
         observations         observations
              \                   /
               +--------+---------+
                        |
                        v
                  final step / result
```

Planner 决定“major work 是什么”；Executor Agent 决定“给定这一项工作，具体用哪些 Tool 怎么完成”。

## Decision Guide

| Situation | Prefer |
|---|---|
| Fixed sequence known in advance | deterministic workflow |
| 少量稳定 category | rule router |
| category 依赖 semantic ambiguity | LLM router + structured output |
| multi-step，milestone 可规划 | planner-executor |
| observation 会使 Plan 失效 | bounded replanning |
| step number/order 无法预知，environment feedback 持续驱动 | ReAct / autonomous Agent |
| 一次 prompt 已可靠完成 | one model call |

## 本阶段要防止的 Common Mistake

### “More Agent = More Intelligent”

autonomy 不是免费升级；path 已知时甚至可能降低 reliability。

### LLM Routing 没 Allowlist

不要接受 arbitrary route string，再动态 import / execute。

### Free-Form Planning Prose

Plan 应足够 structured，使 application 能 validate / execute。

### 把 Plan 当 Truth

Plan 是关于 future work 的 hypothesis，observation 可以推翻它。

### 每一步都 Replan

这增加 model call 和 strategy drift；只有 evidence 需要时才 replan。

### 没有 Plan Budget

Planner 一次吐 40 个 step，execution 还没开始，成本和可靠性问题已经开始了。

### Planner / Executor Responsibility 混在一起

如果 Planner 可任意执行 Tool，而 Executor 又随时重写 global strategy，system 很快就无法解释清楚“谁在控制什么”。

## Completion Checkpoint

进入 Stage 03 前，你应该能回答：

1. Workflow 为什么不是“低级 Agent”？
2. routing 什么时候应该 deterministic？
3. 为什么 LLM router 应返回 enum-like structured decision？
4. route decision 与 downstream dispatch 有什么区别？
5. explicit planning 比纯 ReAct 更清晰地解决什么问题？
6. 为什么 Plan execution 前必须 validation？
7. 什么应该 trigger replanning？
8. `max_total_steps` 与 `max_replans` 为什么都需要？
9. Executor 能不能本身是 Agent？为什么？
10. planner-executor 中哪些东西应该仍然是 ordinary Python control flow？
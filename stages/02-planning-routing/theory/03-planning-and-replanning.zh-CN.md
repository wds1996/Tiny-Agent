# 03 — Planning 与 Replanning：Plan 是有边界的 Hypothesis，不是 Ground Truth

ReAct 本身已经包含某种 planning：每一轮 model 都会判断“下一步做什么”。

那为什么还需要 explicit Planner？

因为 **local next-action reasoning** 与 **global task decomposition** 解决的是两种不同 coordination problem。

---

## 1. ReAct 中的 Local Planning

```text
current state
    |
    v
choose next action
    |
    v
observe result
    |
    v
choose next action
```

优点：

- 灵活；
- 每次 observation 后自然适应；
- 适合 exploration；
- 不需要提前猜完整路径。

缺点：

- 可能 myopic；
- 容易重复 work；
- global strategy 不易检查；
- long-horizon task 可能 drift；
- execution 前很难让 human review 整体 strategy。

---

## 2. Explicit Planning

Planner–Executor 把 planning phase 明确拆出来：

```text
Task
  |
  v
Planner
  |
  v
Plan = [step 1, step 2, step 3]
  |
  v
Execution
```

Plan 成为 application-visible state，例如：

```python
Plan(
    objective="Investigate checkout outage",
    steps=(
        PlanStep(
            "health",
            "Inspect checkout service health.",
        ),
        PlanStep(
            "changes",
            "Inspect recent relevant changes.",
        ),
        PlanStep(
            "evidence",
            "Gather evidence for likely causes.",
        ),
        PlanStep(
            "brief",
            "Produce an evidence-based incident brief.",
        ),
    ),
)
```

这样 software 就能：

- validate；
- display；
- approve；
- budget；
- trace；
- evaluate。

---

## 3. Plan First 不等于 Plan Every Micro-Step

糟糕的 over-decomposition：

```text
1. Think about the task.
2. Decide what to inspect.
3. Open monitoring.
4. Read title.
5. Read first metric.
6. Think about metric.
7. ...
```

Planner 已经越俎代庖，开始替 Executor 规定 microscopic behavior。

更合理的 high-level milestone：

```text
1. Establish current service health.
2. Identify recent changes correlated with failure window.
3. Gather evidence for/against likely causes.
4. Produce incident brief.
```

Executor 再决定每个 milestone 具体怎么完成。

---

## 4. Plan Granularity 是 Architecture Knob

太粗：

```text
1. Solve the entire problem.
```

Planner 没有提供增量价值。

太细：

```text
1. Call Tool A.
2. Copy field X.
3. Call Tool B with X.
4. ...
```

Planner 变成 brittle program generator，并且会过度依赖还没发生的未来 observation。

一个有用 PlanStep 通常应该：

- 独立有意义；
- 易解释；
- 一个 Executor invocation 可以处理；
- 仍给 Executor 留 tactical flexibility；
- 有清晰 result。

---

## 5. Plan 应该是 Structured Data

free-form prose：

```text
First maybe inspect logs, then perhaps check deployments...
```

application 很难可靠 validate。

Tiny-Agent 使用：

```python
Plan(
    objective="...",
    steps=(
        PlanStep(
            id="logs",
            description="Inspect relevant logs.",
        ),
        PlanStep(
            id="deploys",
            description="Inspect recent deployments.",
        ),
    ),
)
```

provider-side Structured Output 可以限制对应 JSON shape。

Plan 从 prompt prose 变成 control-plane object。

---

## 6. Execution 前先 Validate Plan

Planner 仍然是 model，所以 output 仍然是不可信 proposal。

Tiny-Agent 当前检查：

- objective 非空；
- 至少一个 step；
- 最大 plan step 数；
- step ID 唯一；
- description 非空。

production 还可能检查：

- allowed action types；
- dependency validity；
- approval requirements；
- policy constraints；
- estimated budget；
- Tool permissions；
- impossible / contradictory steps。

核心原则：

> **Model 提出 Plan，不等于 application 授权 Plan。**

---

## 7. Planning 是 Uncertainty 下对未来的 Prediction

Plan 描述的是还没发生的 future work，所以一定可能 stale。

例如原计划：

```text
1. Read primary logs.
2. Inspect deployment correlated with error.
3. Draft report.
```

但 execution：

```text
Step 1 -> primary log service unavailable
```

原 strategy 可能已经不能继续，这才是 replanning 有意义的地方。

---

## 8. Replanning 应该是 Exception Transition

糟糕模式：

```text
plan
execute step 1
replan
execute step 2
replan
execute step 3
replan
...
```

这通常只是用更贵的方式重新发明 ReAct loop。

更好：

```text
plan
  |
  v
execute current plan
  |
  +-- observation fits assumptions --> continue
  |
  +-- observation invalidates plan --> replan remaining work
```

replan 必须有理由。

---

## 9. 合法 Replanning Trigger

### Required Resource Unavailable

```text
primary search API unavailable
```

需要 fallback strategy。

### Assumption 被证伪

原假设：

```text
problem started after deployment X
```

新 evidence：

```text
failure began before deployment X
```

investigation strategy 应改变。

### 新信息扩大/改变 Task Scope

例如原以为单服务故障，后来发现多个 service 同时受影响。

### Step 变得 Impossible

例如 required permission 不可获得。

### User 改变 Goal

这通常是新的 planning event，而不是 ordinary retry。

---

## 10. 不合理 Replanning Trigger

不要因为：

- step 成功；
- model 能想出一份更漂亮的 plan；
- wording 有变化；
- loop 里本来就写了 `replan()`；

就重新规划。

只要 Plan 仍然 valid，就应该保持稳定。

Plan stability 会改善：

- auditability；
- cost；
- predictability；
- human comprehension。

---

## 11. Replan Remaining Work，不要盲目重做全部

已发生：

```text
Step 1 health check -> SUCCESS
Step 2 primary logs -> FAILURE
Step 3 report -> not executed
```

合理 replacement plan：

```text
1. Obtain equivalent evidence from fallback logs.
2. Draft report using completed health evidence + fallback logs.
```

通常不应该重新做：

```text
1. Health check again.
```

除非 failure 让先前 health result 失效。

Tiny-Agent replanner 会明确请求 **remaining work only**。

---

## 12. Completed Result 是 Replanning Context 的一部分

```text
Original task
+ completed observations
+ failed step
+ failure reason
        |
        v
Replanner
        |
        v
remaining Plan
```

没有 completed context，replanner 很容易重复 work。

---

## 13. Replanning 也需要 Budget

```text
plan -> fail -> replan -> fail -> replan -> ...
```

同样可以无限循环。

Stage 02 使用两个不同 control：

```text
max_total_steps
max_replans
```

### `max_total_steps`

限制 original + replacement Plan 的总 execution work。

### `max_replans`

限制 strategy 被重新生成的次数。

控制的是不同 failure mode。

---

## 14. Plan Length 自身也是 Budget

还需要：

```text
max_plan_steps
```

一个本来应该 4 个 milestone 的任务，如果 Planner 一口气生成 35 steps，execution 开始前就已经出现 warning signal。

long Plan 会增加：

- cost；
- failure opportunity；
- future assumption staleness；
- human review difficulty。

目标应该是：

> **smallest useful Plan**。

---

## 15. Planning vs Task Decomposition

Task decomposition 问：

```text
有哪些 subproblem？
```

Planning 还问：

```text
什么顺序？
有什么 dependency？
每一步 objective 是什么？
failure 后怎么变？
```

简单 independent task 可能 decomposition 就够了；long-horizon interaction 更关心 order 与 adaptation。

---

## 16. Sequential Plan vs DAG Plan

Stage 02 从：

```text
step 1 -> step 2 -> step 3
```

开始。

真实系统可能是：

```text
             +-> search source A --+
Task -> Plan |                     +-> synthesize
             +-> search source B --+
```

这已经是 DAG。

Tiny-Agent 有意把 full dependency graph / concurrent scheduling 延后到 Stage 03，因为学习顺序应是：

```text
sequential bounded Plan
        ↓
understand dependencies
        ↓
state graph / DAG orchestration
```

---

## 17. Planning 与 Human Approval

explicit Plan 适合在高风险 execution 前让 human review strategy：

```text
Task: migrate production database
        |
        v
Planner proposes Plan
        |
        v
Human review / edit / approve
        |
        v
Executor begins
```

但 plan approval 仍然不能替代每个 side effect 自己的 permission policy。

---

## 18. Planning 不授予 Permission

Planner 可能提出：

```text
1. Delete the old database.
```

Plan syntactically valid 不代表 runtime 应该允许。

必须分开：

```text
Planner capability
```

与：

```text
Executor authority
```

Stage 01 是：

> Model proposes action；runtime governs execution。

Stage 02 上升一层：

> Planner proposes strategy；Workflow governs Plan execution。

---

## 19. PlanStep 应包含什么？

Tiny-Agent 使用：

```python
PlanStep(
    id="health",
    description="Inspect current service health.",
)
```

而不是 arbitrary executable code。

因为 PlanStep 是给 Executor 的 **goal**，不是 trusted program。

未来 typed action plan 可以更强，但那需要更严格 validation / Tool-policy coupling。

---

## 20. ReAct vs Explicit Plan

| Dimension | ReAct | Planner–Executor |
|---|---|---|
| Next action | turn-by-turn | high-level Plan guided |
| Adaptability | naturally high | explicit replan |
| Global strategy visibility | lower | higher |
| Human plan review | harder | natural |
| Plan staleness | implicit | explicit risk |
| Long-horizon coordination | may drift | easier to structure |
| Model-call cost | depends | adds planning calls |

常见组合：

```text
Planner
   |
   v
one high-level PlanStep
   |
   v
ReAct Agent executes locally
```

得到：

```text
global structure + local flexibility
```

---

## 21. Planning Quality 也要 Evaluation

Plan prose 看起来合理，不代表 execution quality 好。

以后应测：

- task success；
- unnecessary step count；
- repeated work；
- Plan validity；
- replanning frequency；
- Tool calls；
- latency / cost；
- recovery success。

不要只让另一个 LLM 看一眼 Plan，然后说“看起来很专业”。

---

## 面试级回答

> ReAct 适合 next action 必须持续依据 environment observation 调整的任务，但 long-horizon task 中可能 myopic。Planner–Executor 把 global strategy 显式化，使它可以 validation、budget、display、approval，同时 Executor 保留 local flexibility。Plan 不是 truth；只有 observation 真正使其失效时，我才对 remaining work 做 bounded replanning，而不是每成功一步都重新生成 Plan。

---

## 自检

1. ReAct 中已经隐式存在什么 planning？
2. explicit Plan 为什么有助 long-horizon task？
3. over-detailed Plan 为什么 brittle？
4. PlanStep 为什么应是 structured data？
5. execution 前应该 validation 什么？
6. 哪类 observation 应 trigger replanning？
7. successful step 为什么通常不应该 trigger replanning？
8. 为什么同时需要 total-step / replan budget？
9. Planner proposal 为什么不代表 permission？
10. 什么时候 Planner + ReAct Executor 比单独使用其中一个更合适？
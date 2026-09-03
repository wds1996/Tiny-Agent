# 04 — Planner–Executor：分离 Global Strategy 与 Local Execution

Planner–Executor 是 multi-step Agent system 最重要的 orchestration pattern 之一。

核心思想：

```text
Planner decides WHAT major work is needed.
Executor decides HOW to complete one assigned step.
Workflow decides WHEN to continue, stop, or replan.
```

这能防止一个 model call 或一个 component 悄悄拥有所有 control layer。

---

## 1. 为什么拆 Planner 与 Executor？

任务：

```text
Investigate why checkout errors increased
and prepare an evidence-based incident brief.
```

pure ReAct 可以不断选 Tool 完成，但 long-horizon task 往往需要显式 strategy：

```text
1. Establish current service health.
2. Inspect recent changes near failure window.
3. Gather evidence for likely causes.
4. Produce incident brief.
```

这里其实有两种 reasoning problem。

### Global Reasoning

```text
哪些 milestone 必须存在？
顺序是什么？
什么 work 可以省略？
```

### Local Reasoning

```text
为了 inspect recent changes，具体用哪个 Tool？
哪些 deployment record 相关？
是否还要继续 query？
```

Planner–Executor 把它们交给不同 component。

---

## 2. Three-Layer Architecture

```text
                 +------------------+
Task ----------> |     Planner      |
                 +--------+---------+
                          |
                          v
                        Plan
                          |
                          v
                 +------------------+
                 |     Workflow     |
                 +--------+---------+
                          |
               one step at a time
                          |
                          v
                 +------------------+
                 |     Executor     |
                 +--------+---------+
                          |
                          v
                     Observation
                          |
                          +----> Workflow
```

### Planner

生成 high-level strategy。

### Executor

完成一个 step，返回 concrete result 或 safe failure。

### Workflow

拥有：

- Plan validation；
- ordering；
- completed-step history；
- total-step budget；
- replan budget；
- failure transition；
- termination。

第三层经常被忽视。

只有 Planner + Executor、没有 governing Workflow，很容易退化成“两个 model 互相叫对方做事，却没人真正负责 policy”。

---

## 3. Planner 不应该执行 Tool

弱架构：

```text
Planner:
1. search_web(...)
2. query_database(...)
3. write_file(...)
```

这时 Planner 已经同时变成 Executor，甚至 Agent。

高级系统里可以这样设计，但它会破坏当前需要学习的 separation。

Stage 02 Planner 返回：

```python
PlanStep(
    id="changes",
    description=(
        "Inspect recent changes that could "
        "explain the failure window."
    ),
)
```

而不是 executable Python / shell command。

---

## 4. Executor 也不应该拥有 Global Strategy

Executor 被分配：

```text
Inspect recent deployments.
```

它不应该擅自说：

```text
“算了，我们不调查 incident 了，
改成新建一个 monitoring dashboard。”
```

它的 scope 是一个 PlanStep。

一个好的 local contract：

```text
Input:
- original task
- current PlanStep
- selected completed StepResults

Output:
- concrete result
or
- safe failure
```

---

## 5. Executor 可以本身是 ReAct Agent

这里 Stage 01 开始真正复用。

例如 step：

```text
Gather relevant evidence from diagnostic Tools.
```

exact action sequence 未知，可以使用 ReAct Executor：

```text
Planner
   |
   v
PlanStep
   |
   v
AgentRuntime
   |
   +-> diagnostic Tool
   +-> log search
   +-> deployment lookup
   +-> observation
   +-> another Tool if needed
   |
   v
Step result
```

形成 hierarchy：

```text
global strategy      -> Planner
local adaptive work  -> Agent Executor
hard budgets         -> Workflow
```

比 one giant Agent 拥有一切 responsibility 更容易治理。

---

## 6. Executor 也可以是 Deterministic Code

不是每一个 PlanStep 都需要另一个 Agent。

例如：

```text
Step: Calculate summary statistics
from validated records.
```

完全可以：

```python
def run_statistics(records):
    return deterministic_statistics(records)
```

一个 Planner–Executor system 可以混合：

```text
PlanStep A -> deterministic function
PlanStep B -> external API
PlanStep C -> ReAct Agent
PlanStep D -> human approval
```

共同 interface 比“所有 node 都必须是 LLM”更重要。

---

## 7. 一个有用的 Executor Interface

概念上：

```python
class StepRunner(Protocol):
    def run(
        self,
        *,
        task: str,
        step: PlanStep,
        completed: tuple[StepResult, ...],
    ) -> str:
        ...
```

为什么传 `completed`？

后续 step 可能依赖之前 evidence：

```text
Step 1:
"Service health shows 18% checkout errors since 09:10."

Step 2:
"Inspect changes related to observed failure window."
```

Executor 需要足够 previous context 才能连接起来。

---

## 8. 但不要永远 Blindly Pass All History

Stage 02 example 小，所以直接传 completed results。

long-running production 中会导致：

- context growth；
- irrelevant information；
- sensitive-data propagation；
- token cost。

后续 Stage 会引入 state selection、memory、summarization、persistence。

原则：

> **Executor context 应该是 application 有意选择的 state，而不是“过去发生过的一切”的垃圾倾倒场。**

---

## 9. Step Success 必须有 Machine-Readable Contract

危险模式：

```text
Executor returns some prose
-> Workflow assumes success
```

如果 prose 是：

```text
“I could not access the logs.”
```

但 function 正常 return，Workflow 可能错误前进。

Stage 02 使用一个简单显式边界：

```text
return string
    -> success

raise StepFailure
    -> expected safe failure

raise other error
    -> unexpected failure, sanitized
```

未来可以 richer：

```python
ExecutorResult(
    status="success",
    evidence=[...],
    output="...",
)
```

重点是：success 应该 machine-readable，而不是从一段 prose 的“语气”猜出来。

---

## 10. Safe Execution Failure

Stage 01 已经说明 raw exception 不应自动进入 model context。

Stage 02 引入：

```python
class StepFailure(RuntimeError):
    """Expected failure whose message is safe for replanning."""
```

Executor 可以：

```python
raise StepFailure(
    "Primary log source is unavailable; "
    "a fallback evidence source is required."
)
```

这条 message 可以安全地给 Replanner。

但 unexpected exception：

```text
RuntimeError("secret-internal-path=/srv/private/data")
```

只应在 Workflow state 中留下：

```text
RuntimeError
```

详细 diagnostics 属于 logs / traces，不属于 model prompt。

---

## 11. 不带 Replanning 的 Planner–Executor

最简单结构：

```text
plan once
   |
   v
step 1
   |
step 2
   |
step 3
   |
finish
```

step fail：

```text
stop and report failure
```

很多 application 到这里已经够了。

只有 failure recovery 真正需要 semantic strategy change 时，才引入 Replanner。

---

## 12. Bounded Replanning

```text
initial Plan
    |
step A -> success
    |
step B -> failure
    |
Replanner
    |
remaining Plan C', D'
    |
continue
```

transition 由 Workflow 拥有。

failed Executor 不应直接自己调用 Replanner。

为什么？Workflow 必须在允许新 strategy generation 前 enforcement：

```text
max_replans
max_total_steps
```

---

## 13. Budget 为什么属于 Workflow

如果 Planner 自己控制 budget，它可以说：

```text
“我认为还需要更多 steps。”
```

如果 Executor 自己控制，它可以无限 local work。

如果 Replanner 自己控制 retry count，它可以无限重新规划。

Budget 是 governance control，应在 model-directed component 外部：

```text
Model component proposes
Workflow enforces
```

这只是 Tiny-Agent 核心哲学在更高 control layer 的重复。

---

## 14. Planner Output 不是 Authorization

Planner 可能提出：

```text
Step: Delete stale production records.
```

Plan 可以 syntax 合法，但 operation forbidden。

未来 production validation 应检查：

- policy；
- permission；
- side-effect level；
- human approval；
- allowed Tool；
- cost limit。

Plan 是 governance 的 input，不是绕过 governance 的通行证。

---

## 15. Planner–Executor vs Router

Router 选择一条已有 branch：

```text
request -> route -> handler
```

Planner 创建 task-specific sequence：

```text
request -> [step A, step B, step C]
```

如果 downstream path 已经存在，用 Routing。

如果 major milestone 本身依赖 request，再用 Planning。

可以组合：

```text
Request
   |
 Router
   |
   +-> simple FAQ workflow
   |
   +-> research branch
           |
         Planner
           |
         Executor
```

simple request 不必为 planning complexity 买单。

---

## 16. Planner–Executor vs Giant ReAct Agent

### Giant ReAct Agent

```text
one model loop
all Tools
all decisions
```

优点：local flexibility 高。

缺点：

- action space 大；
- global strategy visibility 弱；
- plan approval 难；
- long-horizon behavior 难约束。

### Planner + Scoped Executor

```text
Planner -> bounded steps -> scoped Executor
```

优点：

- explicit strategy；
- smaller local scope；
- easier budget / audit；
- 可以 per-step / per-branch 暴露不同 Tool。

缺点：

- extra model calls；
- bad / stale Plan；
- state coordination。

选择依据 requirement / evaluation，而不是 architecture fashion。

---

## 17. Research Example

```text
Compare three approaches for reducing hallucination in RAG.
```

Planner：

```text
1. Define comparison dimensions.
2. Gather evidence for A/B/C.
3. Compare against same dimensions.
4. Produce sourced synthesis.
```

每一个 step 可以交给带 search / retrieval Tool 的 Executor Agent。

Planner 不应该提前决定每一个 search query，因为 future query 依赖 execution 中找到的 evidence。

这就是 hierarchical planning 的核心收益：

```text
global structure + local adaptability
```

---

## 18. Planning 不必要的 Support Example

```text
I was charged twice.
```

如果企业已经有 fixed duplicate-charge workflow：

```text
identify account
-> inspect transactions
-> apply policy
-> response
```

不需要生成 task-specific Plan。

直接 Routing 到固定 Workflow 即可。

---

## 19. 如何测试 Planner–Executor

### Planner Test

检查：

- valid structured shape；
- bounded step count；
- objective stable；
- no empty / duplicate ID。

### Workflow Test

使用 fake Planner / Executor 验证：

- step order；
- completed context；
- stop behavior；
- replan trigger；
- total-step budget；
- replan budget。

### Executor Test

独立验证 local task completion。

不要依赖一次昂贵 end-to-end model test 去证明所有 control-flow invariant。

---

## 面试级回答

> 我会先判断任务能否表示为 deterministic Workflow。如果 major milestones 随 request 变化但仍然有界，我会采用 Planner–Executor。Planner 生成 schema-constrained high-level Plan；application code validation / budget；Executor（可以是 ReAct Agent）一次处理一个 step；completed observations 作为显式 state 保存。只有 failure / new observation 真正使剩余 Plan 失效时才 bounded replan。Planner output 是 proposal，不是 execution authorization。

---

## 自检

1. Planner 应负责什么？
2. Executor 应负责什么？
3. Workflow 应负责什么？
4. 为什么本架构里 Planner 不应该任意 call Tool？
5. Executor 能不能是 ReAct Agent？
6. 为什么 Executor 需要 selected completed result？
7. 为什么 completed context 不能无限增长？
8. `StepFailure` 的意义是什么？
9. 为什么 budget 应在 model-directed component 外部？
10. valid Plan 为什么仍然不代表允许 side effect？
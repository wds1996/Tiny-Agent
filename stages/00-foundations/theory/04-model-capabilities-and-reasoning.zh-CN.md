# 04 — Model Capability、Reasoning 与 Model Selection

Agent 架构绝不能从一个错误假设开始：

> **“LLM 反正都差不多。”**

不同模型在 capability、latency、cost、context limit、Tool support、multimodality，以及 structured control decision 的可靠性上都可能明显不同。

真正的工程问题不是：

> 哪个模型最聪明？

而是：

> **哪个 model / configuration 能在 application 的 latency、cost、safety 与 capability 约束下，达到当前任务需要的 quality target？**

F1 赛车当然是极其优秀的工程产品，但如果任务只是穿过学校门口送一袋菜，它仍然是一个值得怀疑的选型。

---

## 1. Model Capability 是 Contract Surface

provider 可能提供能力差异很大的 model：

- reasoning quality 与 configurable reasoning effort；
- context window / output limit；
- latency / throughput；
- input / output price；
- Function Calling reliability；
- Structured Output / schema support；
- image / audio / video input-output；
- built-in web / file / code / computer capability；
- fine-tuning / distillation / caching / batch option。

不能把 model selection 简化成某个 leaderboard 的一列分数。

Agent 会让 model 承担很多不同角色：

```text
router           -> 短分类 / enum decision
planner          -> multi-step semantic decomposition
writer           -> 长篇 grounded synthesis
embedding model  -> text -> vector
vision model     -> screenshot / image understanding
```

一个角色的最佳 model，换到另一个角色可能既浪费又不适合。

---

## 2. Model Capability != Runtime Capability

这个区分能避免大量架构错误：

```text
model capability
    = inference API 能表示、理解或提出什么

runtime capability
    = application 实际暴露、授权和执行什么
```

例如：

```text
model supports Function Calling
!= model 可以访问你的 database

model supports computer use
!= model 可以点击 production console

model supports 1M context
!= application 应该发送 1M tokens
```

model 是 reasoning component。

runtime 才拥有：

- credentials；
- Tool registration；
- authorization；
- budgets；
- sandbox boundary；
- side effects。

如果 model 说：

> 我可以删除数据库。

这只是一个 proposal，不是自动升职成为 DBA。

---

## 3. Reasoning Effort 是 Budget，不是“智力魔法滑块”

reasoning-oriented API 可能允许通过一个参数增加 inference work，以换取潜在更好的结果。

适合更高 reasoning effort 的任务：

- difficult planning；
- ambiguous multi-constraint decision；
- non-trivial code / math reasoning；
- complex evidence synthesis。

不应该自动拉满的任务：

- deterministic routing；
- trivial extraction；
- schema conversion；
- simple Tool selection；
- 本来就能由 code 精确完成的 decision。

正确的选择方式应该是 empirical：

```text
candidate model / configuration
        ↓
evaluation dataset
        ↓
quality + latency + cost + failure profile
        ↓
选择能满足 product target 的最小配置
```

没有 evaluation set 的“多给一点 reasoning 总不会错”，通常只是一种更贵的迷信。

---

## 4. 先做 Capability Matrix，再做 Router

很多应用用一张简单的 application-owned matrix 就足够：

| Role | Required capability | Priority |
|---|---|---|
| ticket router | structured enum output | latency / cost |
| research planner | strong reasoning + structured plan | quality |
| report writer | long grounded generation | quality / context |
| image inspector | vision input | capability |

model selection 完全可以先保持 deterministic：

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ModelProfile:
    name: str
    supports_structured: bool
    supports_vision: bool
    tier: str


def choose_model(
    task: str,
    profiles: list[ModelProfile],
) -> ModelProfile:
    if task == "vision":
        return next(
            p for p in profiles
            if p.supports_vision
        )

    if task in {"route", "extract"}:
        return next(
            p for p in profiles
            if p.tier == "fast"
            and p.supports_structured
        )

    return next(
        p for p in profiles
        if p.tier == "reasoning"
    )
```

真正重要的不是这段 toy policy，而是：

> **Model selection 本身就是 application policy。**

---

## 5. Dynamic Model Routing：有用，但必须 Bounded

有些 task complexity 本身是 semantic 的，可以让一个 LLM / router 帮忙分类。

比较安全的结构：

```text
request
  -> bounded complexity classifier
  -> enum: FAST | REASONING | VISION
  -> application maps enum to approved model
```

错误结构：

```python
# user / model text 直接变成任意 provider model id
model = provider.create(
    user_supplied_model_name
)
```

semantic router 可以在**预先批准的类别**里选择，但不能无意间变成 configuration-injection interface。

---

## 6. Capability 不满足时应该清晰失败

假设 application 强依赖 strict Structured Output，而当前 provider / model path 不支持需要的 schema behavior。

坏做法：

```text
先试试看
-> 收到 prose
-> 用 regex 拆
-> 希望今天星期二运气不错
```

更好的做法：

```text
required capability unavailable
-> reject configuration / choose approved fallback
-> record fallback reason
```

provider adapter 的价值之一，就是把这些快速变化的 provider capability detail 隔离在 core Agent runtime 外面。

---

## 7. Model Upgrade 也是 Software Change

model version 变化可能改变：

- ToolCall frequency；
- plan length；
- formatting behavior；
- refusal / abstention rate；
- latency；
- token usage；
- critic 请求 revision 的频率。

因此，model upgrade 应该像 library upgrade 一样进入 regression evaluation。

例如：

```text
                    old config    candidate
route accuracy         96%          97%
research success       82%          88%
p95 latency           1.2s         2.1s
mean tokens            900         1450
cost / successful run  $X          $Y
```

candidate 不是因为某一个 quality number 上升就自动“更好”。

---

## 8. 示例：一个 Agent，三个 Model Role

研究 Agent：

```text
user question
   ↓
fast router: "needs research?"
   ↓ yes
reasoning planner: subquestions + evidence plan
   ↓
retrieval / Tools
   ↓
writer model: grounded synthesis
```

为什么不三个阶段都用最强模型？

因为第一步可能是高频、非常简单的 decision。

为了判断：

```text
needs_research = true
```

每次都启用最高 reasoning，就像请最高法院大法官帮电影院验票。

那为什么不全部用最便宜的 model？

因为 planner 可能正是整个 downstream trajectory 最依赖 semantic quality 的阶段。

所以 model routing 是 systems optimization problem，不是品牌偏好。

---

## 9. 面试级回答

如果被问：

> How do you select models in an Agent system?

一个强回答应该表达：

> 我会先区分 model capability 与 runtime permission；为每一个 Agent role 定义 capability / quality requirement；把 routing 限制在 approved model set 中；再用 task success、latency、cost 与 failure behavior 对 candidate configuration 做 evaluation。只有在更高 reasoning 能测量地改善目标任务时才增加它，而不是让每一步都变成最昂贵配置。

---

## 10. Provider Detail 是 Versioned 的

model name、parameter、response shape 的变化速度远快于本仓库的 architecture principle。

Tiny-Agent 因此通过 adapter 隔离 provider behavior。

最终不变量：

> **通过 explicit application policy 选择 model capability，通过 evaluation 验证它，并永远不要把“model 能提出什么”与“runtime 允许它做什么”混为一谈。**
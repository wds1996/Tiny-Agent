# 03 — Base Implementation：先把 Agent 做对，再谈 Framework

Base 实现存在的理由只有一个：等你看到 LangGraph 版本时，每一个重要控制决策都应该已经能在**不依赖 decorator 或 graph API** 的情况下解释清楚。

## 主对象

```python
agent = BaseOpenScholarAgent(
    model=model,
    corpus=corpus,
    scholarly_search=search,
    memory=memory,
    exporter=exporter,
    config=config,
)
```

这个 class 负责组合已经存在的 Tiny-Agent primitives。

它不会再造：

- 第二套 Tool runtime；
- 第二套 memory system；
- 第二套 tracer。

## Step 1 — 读取 Long-Term Personalization

```python
remembered = dict(
    self.memory.read_context(request.user_id)
)
```

如果当前 request 临时指定 `preferred_style`，本次 run 可以覆盖 remembered preference。

但要牢记：

```text
remembered preference
!=
research evidence
```

memory 可以影响回答风格，但不能变成 citation source。

## Step 2 — Structured Planning

```python
plan = await asyncio.to_thread(
    self.model.plan,
    question=request.question,
    remembered_context=remembered,
)
```

模型提出 `ResearchPlan`，application code 再对其限界：

```python
subquestions = plan.subquestions[
    :config.max_subquestions
]
```

这延续 Stage 02 的原则：

> **Model output 可以提出 control data；application 负责验证和约束。**

如果模型返回 400 个 subquestion，正确反应不是：

> 哇，好严谨的研究员。

而是：

> 预算终于加入了群聊。

## Step 3 — Parallel，但必须 Bounded 的 Retrieval

每个 subquestion 可以触发两条彼此独立的 retrieval：

```python
local = asyncio.create_task(
    local_search(subquestion)
)

external = asyncio.create_task(
    external_search(subquestion)
)
```

前提是 subquestion 总量已经由 application bound；Crossref client 也有自己的 concurrency guard。

`asyncio.gather()` 只负责 scheduling / collecting。

它不会替你判断：

- 哪个 source 更可信；
- evidence 是否足够；
- 哪一篇论文能支撑哪一个 claim。

## Step 4 — Evidence Normalization

raw results 会先去重，然后分配稳定 public ID：

```text
E1
E2
E3
```

模型看到的 ID 与 evaluator 后面检查的 ID 是同一套。

## Step 5 — Synthesis 之前先做 Evidence Sufficiency

```python
local_count = sum(
    item.kind == "local_fulltext"
    for item in evidence
)
```

如果数量低于 configured threshold，Agent 直接返回：

```text
status = insufficient_evidence
```

并且**不会调用 synthesis model**。

这不仅是科学严谨性问题，也是成本问题：既然 application policy 已经知道回答无法被支撑，就没有必要再付费生成一段语言流畅但无法 grounded 的答案。

## Step 6 — Synthesis 阶段不再保留 Open-Ended Tool Surface

retrieval 结束后，writer 只接收 evidence：

```python
model.synthesize(
    question=question,
    evidence=evidence,
    remembered_context=remembered,
)
```

研究阶段可以更 Agentic；synthesis 阶段故意收窄。

成熟 Agent 不是每一行代码都追求最大 autonomy，而是在真正有价值的地方使用 autonomy。

## Step 7 — Bounded Critic / Writer Loop

initial draft 进入 Stage 11 `TeamRuntime`：

```text
Supervisor -> Critic
            -> optional Writer
```

critic 可以要求 revision，但 `max_revisions` 属于 application。

没有 bound 的：

```text
reflect until perfect
```

只是披着学术外衣的 infinite loop。

## Step 8 — Explicit Memory Write

只有 request 明确要求记住 style 时才写 memory：

```python
if request.remember_style:
    memory.write_style(...)
```

真正 durable boundary 仍然由底层 `ConservativeMemoryWritePolicy` 控制。

模型不能因为一句：

```text
“这个信息以后肯定有用”
```

就自动扩张 permanent memory。

## Step 9 — Export 是 Side Effect

提供 `export_path` 会生成 `ApprovalRequest`。

如果还没有 human decision，base 版本返回：

```text
status = approval_required
```

即使用户随后 approve，path 仍然要经过 exporter authorization：

```text
human approval
    -> application validation
    -> path containment check
    -> file write
```

Approval 不是一颗“获得 sudo”的魔法按钮。

## Step 10 — Trace 整个 Run

base path 记录 nested spans：

```text
openscholar.run
  plan
  retrieve.local
  retrieve.crossref
  synthesize
  review.team
  memory.write
```

默认不捕获 raw prompt / raw output，因为 Stage 10 已经明确：observability 不能为了“看得更全”而把 Stage 09 的 privacy boundary 拆掉。

## Base Version 故意没有解决什么

Base implementation 可以返回：

```text
approval_required
```

但它本身没有 durable suspended execution。

如果 process 退出，application 必须自己持久化 run state，并知道后面该从哪里继续。

这正是 LangGraph 版本开始真正“值得引入”的位置。

本章不是在教：

> Python 不行，必须换 graph。

而是在教：

> **普通 control flow 足够清楚时就使用普通 control flow；只有当 state-machine / checkpoint / resume requirement 真正出现时，专用 orchestration infrastructure 才开始产生结构性价值。**
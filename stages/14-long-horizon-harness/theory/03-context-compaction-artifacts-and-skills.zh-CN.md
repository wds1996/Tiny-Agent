# 03 — 跨 Session 的 Context Compaction、Artifact 与 Skill

长时程 Agent 必须维持连续性，同时接受一个现实：任何单个模型 context 都不应该装下整个项目历史。

关键是把不同类型的“连续性”放到正确的位置：

```text
facts / progress -> ledger / checkpoint
large outputs    -> artifacts / workspace
procedures       -> Skills
working view     -> compact model context
```

---

## 1. 不要把 transcript replay 当成 persistence

糟糕的做法：

```text
new session
-> replay 300 previous turns
-> 加入全部 Tool observations
-> 加入所有 generated files
```

它昂贵、缓慢，而且最终一定会变得不可行。

更好的 session 输入是：

```text
stable objective
+ ledger status
+ compact recent handoff
+ relevant artifacts
+ current Skill
+ current Tool subset
```

---

## 2. Compaction 是 context operation

Stage 07 已经介绍过：

```python
record = compact_items(
    old_context_items,
    key="handoff-summary",
    summarizer=summarize,
    provenance="derived:compaction",
)
```

在长时程任务里，compaction 尤其适合发生在 **session boundary**：

```text
session work
-> 保存 exact artifacts / ledger
-> 生成 short handoff summary
-> next session 从较小 context 开始
```

这里一定要注意：

```text
identifier
ownership
approval fact
```

这类不能随意模糊化的事实，仍然应该保存在结构化精确状态中，而不是只剩下一份语言模型摘要。

---

## 3. Artifact 承载大型 durable result

假设一个任务生成：

```text
12 MB CSV
20 figures
100 KB report draft
```

不要把这些内容贴进 `state.notes`。

记录引用即可：

```text
artifacts/data-summary.csv
artifacts/figures/plot-1.png
reports/draft.md
```

之后由 context engineering 在真正需要时选择 preview、section 或相关片段。

> Artifact 是外部 working state，不是一条野心过大的 prompt message。

---

## 4. Artifact provenance 很重要

未来 worker 看到一个文件时，需要知道：

```text
哪个 task 生成的？
基于哪个 input / source version？
由哪段 code / 哪个 model 产生？
通过了什么 test / evaluator？
属于哪个 tenant / run？
它是 scratch 还是 promoted output？
```

不能因为一个文件“已经躺在 workspace 里”，就自动把它视为可信事实。

---

## 5. Skill 跨模型 Session 保存的是 procedure

长时间 coding / research 工作通常依赖标准流程：

```text
research-review Skill
code-review Skill
data-analysis Skill
```

不要把这些组织级 procedure 每次都复制进 handoff summary。

更合理的是把 procedure 版本化为 Skill，在当前阶段需要时激活：

```text
ledger says next task = review evidence
-> SkillCatalog activates research-review
-> ContextBuilder adds Skill instructions
```

这样 handoff 就能专注于 **project-specific state**，而不是反复背诵团队工作手册。

---

## 6. Skill version 也属于 reproducibility

一个 3 天任务可能跨越 Skill 更新：

```text
day 1: Skill v1
中途发布 v2
new worker: 默认使用 v2
```

行为可能在同一个 run 中途改变。

对高 reproducibility 任务，应：

```text
pin / record Skill version or source
```

或者明确执行 migration。

同样需要关注的还有：

```text
model / provider version
code version
environment artifact
```

---

## 7. 从 durable source 构造当前 Context

概念上的长时程 worker：

```python
items = [
    ContextItem("objective", "task", state.objective, required=True, trusted=True),
    ContextItem("handoff", "note", handoff, priority=90),
    ContextItem("skill", "skill", activated_skill.instructions, priority=85),
    ContextItem("artifact-preview", "workspace", preview, priority=80),
]

snapshot = ContextBuilder(budget).build(items)
```

实际 `ContextItem` API 以 Stage 07 定义为准；这段代码主要展示各子系统如何组合。

---

## 8. 示例：研究任务的 Session 4

Session 3 结束时：

```text
Ledger:
  search papers        completed
  extract evidence     completed
  compare methods      pending

Workspace:
  evidence/method-a.md
  evidence/method-b.md

Handoff:
  “Two methods extracted; compare assumptions/performance next.”
```

Session 4 只需要加载：

```text
objective
pending compare task
research-review Skill
method-a / method-b 的相关 section
```

它没有必要重新知道 session 1–3 的每一次 search query 和每一个失败 URL。

---

## 9. Garbage Collection / Retention

长项目会不断积累 scratch data，因此必须定义：

```text
什么是 temporary？
什么必须在 run 完成后保留？
什么是 user-facing output？
什么因 audit 需要保留？
什么时候可以删除 artifact？
```

retention 同时是成本政策和隐私政策。

“把所有中间 Tool 输出永久保存”并不会自动升级成“更好的 observability”。有时它只是更贵、风险更高的硬盘收藏癖。

---

## 完成原则

> **用 ledger 保存精确进度，用 artifact 保存大型 durable output，用 Skill 保存 reusable procedure，用 compact context 服务当前模型决策。**

这样新的 session 可以继续工作，而不用假装模型拥有无限容量的自传式记忆。
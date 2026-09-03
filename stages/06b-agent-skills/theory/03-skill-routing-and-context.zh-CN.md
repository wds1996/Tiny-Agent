# 03 — Skill Routing、Activation 与 Context Integration

> Language: [English](03-skill-routing-and-context.md) | 简体中文

安装 Skill 很容易。真正有意思的工程问题是：**怎样在正确的时候 activate 它，同时又不把所有 Skill 的完整正文塞进每一次请求？**

```text
installed Skills
   ↓ metadata catalog
candidate Skills
   ↓ task matching/policy
activated Skill(s)
   ↓
ContextBuilder
   ↓
model decision
```

Routing 是 context selection，不是 permission assignment。

---

## 1. 从 Metadata 开始，而不是从整本手册开始

`SkillCatalog.metadata_prompt()` 提供精简 discovery view：

```python
catalog = SkillCatalog("skills")
metadata = catalog.metadata_prompt()
```

即使装了 50 个 Skill，startup context 也可以只包含：

```text
- code-review: Review code changes...
- data-analysis: Analyze tabular datasets...
- research-review: Check claims against evidence...
...
```

如果一开始就加载 50 份完整 procedural manual，那等于亲手把 Progressive Disclosure 这个概念取消了。

---

## 2. Routing 可以是 Deterministic，也可以是 Semantic

### Deterministic

Trigger 明确时：

```python
def choose_skill(file_name: str) -> str | None:
    if file_name.endswith(".pdf"):
        return "pdf-processing"
    if file_name.endswith(".csv"):
        return "data-analysis"
    return None
```

### Semantic

Intent 模糊时：

```text
Task: "Check whether these claims exaggerate the papers"
Candidates:
- research-review
- copy-editing
- citation-formatting
```

可以让 model/router 从**应用给定的 candidate set**中选择 enum。

结果仍然需要 validation：

```python
selected = decision["skill"]
if selected not in approved_candidate_names:
    raise ValueError("unknown skill selection")
```

---

## 3. 不要让模型在“无限文件系统”里 Routing

错误：

```text
"Here are 4,000 SKILL.md files. Read them and choose."
```

更好：

```text
catalog metadata
-> category/filter
-> small candidate list
-> semantic choice if needed
-> activate one/few Skills
```

Catalog 很大时，连 metadata 本身都可能需要 indexing/search。

也就是说 Progressive Disclosure 可以递归应用：你的“技能目录”太大时，它自己也需要 progressive disclosure。

---

## 4. Selection 之后才 Activate

```python
skill = catalog.activate("research-review")
```

此时才获得：

```text
skill.instructions
skill.references
skill.scripts
skill.assets
```

Activated Skill 可以成为 `ContextItem`：

```python
from tiny_agent import ContextItem

skill_item = ContextItem(
    key="skill:research-review",
    kind="skill",
    content=skill.instructions,
    priority=90,
    provenance="skill:research-review",
    trusted=False,
)
```

为什么默认 `trusted=False`？

因为 Skill 可以指导模型 procedure，但不应该自动升级为 immutable control authority，尤其是 third-party Skill。

---

## 5. Skill 也要竞争 Context Budget

一个 Skill body 可能很大。即使 activate 了三个，也不要无脑拼接。

可以采用：

```text
one primary Skill + one helper Skill
per-phase Skill activation
Skill instruction compaction
load references only on demand
```

例如：

```text
PLAN
  -> research-planning Skill

EVIDENCE REVIEW
  -> research-review Skill

FINAL FORMAT
  -> report-formatting Skill
```

Plan 已经确定后，writer 通常不再需要一直带着 planning manual。

---

## 6. Skill Routing vs Tool Routing

三个决策相关，但不同：

```text
Skill routing
    -> 模型应该看到哪份 procedural guidance？

Tool exposure
    -> 模型应该看到哪些 action schema？

Tool authorization
    -> 哪些 action 真的允许执行？
```

Skill 可以推荐某组 Tool，但 Host 仍然拥有 exposure 与 authorization 决策权。

---

## 7. Skill Routing vs Sub-Agent Delegation

适合用 Skill：

- 仍由同一个 runtime/identity 继续执行；
- 只需要 domain procedure；
- 不需要独立 lifecycle/state。

适合用 sub-Agent：

- 需要 isolated context；
- 需要独立 role/Tool surface；
- 独立 state/lifecycle 有价值；
- parallel/delegated execution 确实有必要。

错误思路：

```text
需要换一套 checklist
-> 再启动一个 autonomous Agent
```

有时你缺的是一本操作手册，不是再召开一个委员会会议。

---

## 8. 例子：Academic Answer Review

输入：

```text
"Review this answer and tell me whether every major claim is supported."
```

Pipeline：

```text
1. application exposes metadata for review-related Skills
2. router chooses research-review
3. SkillCatalog.activate("research-review")
4. ContextBuilder includes:
   - task
   - answer under review
   - evidence
   - Skill instructions
5. model produces structured review
6. deterministic evaluator checks citation IDs/known sources
```

Skill 提供 procedure；Evidence 提供事实；Evaluator code 提供 deterministic check。

把这三件事分开，就是架构价值所在。

---

## 9. Failure Case：Accidental Skill Stacking

假设同时 activate：

```text
legal-contract-review: "Prefer conservative wording"
marketing-copy: "Use bold persuasive claims"
```

任务明明是 legal review，第二个 Skill 不仅无关，还会制造 instruction collision。

Skill 越多不代表 expertise 会自动叠加，反而可能让模型同时听见互相打架的导师。

可以评估：

```text
activation precision = relevant activated Skills / activated Skills
activation recall    = needed Skills activated / needed Skills
```

---

## 10. Observability

为了调试 Skill routing，应记录足够的 metadata：

```text
available Skill metadata/version
candidate Skills
selected Skill(s)
loaded references
context token contribution
routing reason/model version
```

如果 Skill/resource 含 proprietary procedure 或敏感数据，不要默认把完整内容全部打进日志。

---

## 完成原则

> **Discover cheaply, select narrowly, activate deliberately, load resources lazily, and keep authorization outside Skill routing.**

这样 Skill 才是一种可扩展 context mechanism，而不是又一个 giant prompt directory。

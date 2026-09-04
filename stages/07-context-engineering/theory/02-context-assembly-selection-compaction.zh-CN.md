# 02 — Context Assembly、Selection、Ordering 与 Compaction

> Language: [English](02-context-assembly-selection-compaction.md) | 简体中文

一个好的 Context Builder，更像一条编译流水线，而不是：

```python
"\n".join(everything)
```

更合理的流程是：

```text
sources
  -> candidates
  -> classify
  -> select under budget
  -> compact where appropriate
  -> restore intentional ordering
  -> render
```

每一步都解决不同的问题。

---

## 1. Selection 与 Ordering 不是一回事

Selection 问：

> 哪些内容值得保留，而且预算允许？

Ordering 问：

> 被选中的内容应该以什么顺序交给模型？

Tiny-Agent 用 priority 决定**谁能进入上下文**，然后再恢复应用原本定义的语义顺序。

下面是 `ContextBuilder.build()` 的简化逻辑：

```python
required = [(i, item) for i, item in indexed if item.required]
optional = [(i, item) for i, item in indexed if not item.required]

used = sum(item.estimated_tokens for _, item in required)
optional.sort(key=lambda pair: (-pair[1].priority, pair[0]))

for index, item in optional:
    if used + item.estimated_tokens <= budget.available_input_tokens:
        selected_indexes.add(index)
        used += item.estimated_tokens

selected = tuple(
    item for index, item in indexed
    if index in selected_indexes
)
```

为什么最后还要恢复原始顺序？

因为“retrieval score = 0.94”不应该让一段不可信文档自动跑到 system instruction 前面。Priority 负责“保留还是丢弃”，不是拿来重新定义语义权威顺序的。

---

## 2. Greedy priority 是一种 policy，不是天降真理

Tiny-Agent 故意采用简单、确定性的规则：

```text
required first
optional by priority
skip items that do not fit
```

生产系统可以有更复杂的策略，例如：

- 按 kind 分配 quota；
- relevance score + recency；
- diversity constraint；
- source quality；
- conversation segmentation；
- learned context selection。

教学版本的价值在于：每个选择都能被看懂、测试和解释。

如果你还没有证据证明简单策略哪里不好，就没必要先把选择算法写成一篇优化论文。

---

## 3. 为什么不能对一个 giant prompt 直接截尾？

很诱人的实现：

```python
prompt = huge_prompt[-max_chars:]
```

可能出现：

```text
最前面的 system instruction -> 被截掉
最后一段随机 Tool output     -> 完整保留
```

纯字符/字节截断不知道什么重要、什么不重要。

显式的：

```python
ContextItem(required=True)
```

让应用在无法满足 invariant 时直接失败，而不是悄悄把 invariant 切掉一半。

---

## 4. Compaction 是有损的派生状态

历史增长后，常见做法是：

```text
old detailed turns
      ↓ summarizer
compact summary
+
recent turns verbatim
```

但必须牢记：

```text
summary != source of truth
```

Tiny-Agent 会记录 summary 与来源之间的关系：

```python
from tiny_agent import compact_items

record = compact_items(
    old_turns,
    key="history-summary-1",
    summarizer=summarize_history,
    kind="history",
    provenance="derived:compaction",
)

print(record.source_keys)
print(record.saved_estimated_tokens)
```

Summary 被明确标记为 derived state，并且默认不是 trusted control data。

---

## 5. Summary 可以非常自信地总结错

原始对话：

```text
User: Never send the report automatically.
User: You may generate a draft.
User: I will approve export later.
```

糟糕 summary：

```text
User wants a report generated and sent later.
```

只少了一个细节，authorization semantics 就被完全改写了。

因此，有些状态不应该被随便压成模糊自然语言。

---

## 6. 哪些东西不能轻易 Compact？

只要后续行为依赖精确值，就应该保留原始 structured/source state，例如：

- approval decision；
- authorization/ownership fact；
- idempotency key；
- run/task identifier；
- financial amount；
- 参与计算的结构化 Tool result；
- legal/audit record；
- citation 所需的精确 source locator。

Context compaction 的目标是减少模型输入，不是获得“随手销毁 durable truth”的许可证。

---

## 7. Compaction policy 应把事实与叙事分开

一个好的 handoff 可以同时包含：

```text
STRUCTURED FACTS
- task_id: task-12
- status: pending
- artifact: reports/a.md
- approval: not_granted

SUMMARY
- searched papers A/B; next step is compare methods
```

Structured facts 精确保留，narrative 可以有损压缩。

Stage 14 会继续使用这一原则：ledger/workspace state 才是 authoritative state，而 handoff summary 只是下一位 worker 读取的压缩视图。

---

## 8. 一个 Selection 例子

假设 input budget = 1,000 tokens：

```text
system        120 required
current task   80 required
recent turns  300 priority 90
paper A       350 priority 80
paper B       350 priority 70
old history   500 priority 20
```

Required context 先占 200。

然后 greedy selection：

```text
recent turns -> total 500
paper A      -> total 850
paper B      -> 超过 1000，跳过
old history  -> 超过 1000，跳过
```

如果后面还有体积更小、priority 更低但能放下的 item，Tiny-Agent 会继续扫描并允许它进入。策略因此仍然是确定且可检查的。

---

## 9. 什么时候触发 Compaction？

可选 trigger：

```text
estimated token threshold
turn count threshold
phase transition
long-horizon session handoff
Tool observation burst
```

不要每一轮都总结一次。那会额外消耗模型调用，而且会让 summary error 一层层累积。

一个更常见的模式：

```text
recent window verbatim
+
periodic older summary
+
需要时重新检索 exact history/artifacts
```

---

## 10. 评估 Context Policy，而不是只看最终答案

可测量：

```text
answer/task quality
constraint retention
input tokens
latency/cost
Tool selection precision
retrieval precision
prompt-injection success
summary factual error
```

如果某项 policy 降低 40% token，同时保持任务成功率并缩小攻击面，这是工程收益。

如果它同样省了 40% token，却把用户的“不要发送”压缩没了，那只是一次非常高效的失败。

---

## 完成后的核心区分

```text
selection   != ordering
summary     != truth
storage     != context
priority    != authority
compression != deletion of durable state
```

这些边界一旦清楚，Context Engineering 就从“prompt 太长怎么办”的焦虑，变成了一套可控、可测量的 pipeline。

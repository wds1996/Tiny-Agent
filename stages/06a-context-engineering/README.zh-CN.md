# Stage 06A — Context Engineering（上下文工程）

> Language: [English](README.md) | 简体中文

现代 Agent 的质量，往往并不是首先受限于模型“最多能塞多少上下文”，而是受限于：**应用到底选择把什么放进这次上下文里**。

前面的 Stage 00、RAG、Memory、Tool Use 和 Multi-Agent 已经反复触及这个问题。Stage 06A 把这些零散原则正式收束成一门独立的工程能力：**Context Engineering**。

> Context Engineering 的目标，是为当前这一次模型决策，构造一个尽可能小、但信号足够强的上下文，让模型拿到它真正需要的指令、信息、能力和状态。

## 为什么放在 Memory 之后？

到 Stage 06 为止，应用已经可能拥有很多上下文来源：

```text
system instructions
current task
conversation history
thread checkpoint
long-term memory
retrieved evidence
tool schemas
tool observations
MCP resources
skills
workspace files
progress notes
```

最容易犯的错误，就是把这些东西统统拼起来。

```text
available data != model context
```

Persistence 决定“应用保留什么”；Context Engineering 决定“模型这一次看到什么”。这两件事不是一回事。

## 学习目标

完成本阶段后，你应该能够：

1. 把 context 理解为有限的 attention/token 预算；
2. 区分应用保留的 state 与真正送给模型的 context；
3. 主动为模型输出以及后续 runtime/Tool 循环预留 token 空间；
4. 按角色、来源、信任级别、优先级和生命周期描述 context；
5. 在预算内确定性地选择 required 与 optional context；
6. 解释为什么超大 context window 并不会让 Context Engineering 消失；
7. 对旧历史进行 compaction，同时保留 provenance；
8. 把 summary 当成有损的派生状态，而不是原始事实；
9. 按需加载 evidence、Tool、Skill 和 workspace 文件；
10. 避免每一轮都向模型暴露所有 Tool；
11. 为 sub-Agent 投影最小必要上下文，而不是复制完整父状态；
12. 从质量、成本、延迟和 prompt-injection 暴露面评估 context policy。

## 推荐学习顺序

1. [`theory/01-context-is-an-attention-budget.zh-CN.md`](theory/01-context-is-an-attention-budget.zh-CN.md)
2. [`theory/02-context-assembly-selection-compaction.zh-CN.md`](theory/02-context-assembly-selection-compaction.zh-CN.md)
3. [`code/context_budget_demo.py`](code/context_budget_demo.py)
4. [`code/compaction_demo.py`](code/compaction_demo.py)
5. [`theory/03-just-in-time-context-and-capabilities.zh-CN.md`](theory/03-just-in-time-context-and-capabilities.zh-CN.md)
6. [`theory/04-provenance-trust-and-isolation.zh-CN.md`](theory/04-provenance-trust-and-isolation.zh-CN.md)
7. [`../../src/tiny_agent/context_engineering.py`](../../src/tiny_agent/context_engineering.py)
8. [`../../tests/test_context_engineering.py`](../../tests/test_context_engineering.py)
9. [`exercises/review-questions.zh-CN.md`](exercises/review-questions.zh-CN.md)

## 可复用实现

`ContextBuilder` 接收显式的 `ContextItem` 和 `ContextBudget`：

```python
snapshot = ContextBuilder(
    ContextBudget(
        max_context_tokens=32_000,
        reserve_output_tokens=4_000,
        reserve_runtime_tokens=2_000,
    )
).build(items)
```

如果 required item 放不下，构建过程会 fail closed，而不是悄悄把它丢掉。Optional item 则按照 priority 竞争预算；完成选择后，再恢复为应用定义的原始顺序。

教学实现使用的是 provider-neutral 的粗略 token 估算。真实生产环境中的精确计数，应来自具体模型 tokenizer 或 provider 返回的 usage metadata。

## Context Pipeline

```text
application-owned data
      |
      v
context candidates
(kind / provenance / trust / priority)
      |
      v
budget + policy
      |
      +--> required instructions/task
      +--> relevant evidence/memory
      +--> activated skill
      +--> selected tools
      +--> recent/compacted history
      |
      v
model context for this decision
```

## 参考资料

- Anthropic, *Effective context engineering for AI agents* — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- LangGraph memory/context documentation — https://docs.langchain.com/oss/python/langgraph/add-memory
- OpenAI model catalog — https://platform.openai.com/docs/models

2026 年的前沿模型即使支持非常大的 context window，也只是把“容量”变大了。过时、冲突、低信号甚至恶意的 token，并不会因为窗口变大就突然变得有价值。

## 完成检查点

如果应用拥有：

```text
2 GB state
400 Tools
80 Skills
300 conversation turns
40 retrieved documents
```

你应该能回答：

> 下一次模型调用究竟应该收到哪一小部分内容？为什么是这些？它们分别受什么预算和信任策略约束？

# Stage 00 — LLM、Context 与 Tool-Use 基础

Stage 00 在任何 Agent framework 出现之前，先建立最重要的 **model / runtime boundary**。

现代 Agent 不是简单的“LLM + 一个循环”。更准确地说，它是一个 application：不断构造 model context，请概率模型提出下一步建议，验证 structured output，执行受治理的 capability，记录 observation，并决定哪些 state 应该继续存在。

## 学习路径

```text
LLM API + message roles
        ↓
Structured Output / JSON Schema
        ↓
Function / Tool Calling
        ↓
model capabilities + reasoning effort
        ↓
context windows / tokens / cost / latency
        ↓
instruction hierarchy + context construction
        ↓
minimal multi-turn Tool loop
```

## 学习目标

完成 Stage 00 后，你应该能够：

1. 解释 system / user / assistant / tool message；
2. 区分 natural-language output 与 schema-constrained output；
3. 解释为什么“请输出 JSON”比 validated Structured Output 弱得多；
4. 解释模型只是提出 `ToolCall`，真正执行的是 runtime；
5. 区分 Tool schema 与 executable handler；
6. 把 Tool observation 返回给模型；
7. 区分 model capability 与 application/runtime capability；
8. 从 reasoning effort、quality、latency、cost 等维度做 model selection；
9. 区分 context-window capacity 与真正 useful context；
10. 为 final output 和后续 Tool/runtime continuation 预留 context；
11. 区分 instructions、task data、examples、evidence、memory、Tool schemas；
12. 实现一个最小、bounded、multi-turn Tool loop；
13. 说明 production Agent runtime 还缺哪些能力。

## 推荐顺序

1. [LLM API 与消息](theory/01-llm-api-and-messages.zh-CN.md)
2. [Structured Output](theory/02-structured-output.zh-CN.md)
3. [Function / Tool Calling](theory/03-function-calling.zh-CN.md)
4. [模型能力与 Reasoning](theory/04-model-capabilities-and-reasoning.zh-CN.md)
5. [Context、Token、Cost 与 Latency](theory/05-context-tokens-cost-latency.zh-CN.md)
6. `code/context_budget_basics.py`
7. [Instructions、Prompts 与 Context Construction](theory/06-instructions-prompts-and-context-construction.zh-CN.md)
8. `code/minimal_tool_loop.py`
9. [复习题](exercises/review-questions.zh-CN.md)



## 核心心智模型

```text
Application owns
----------------
instructions
context selection
available Tools
validation
authorization
execution
state / persistence
budgets
observability

Model owns
----------
对给定 context 进行 probabilistic inference
提出 text / structured data / ToolCalls
```

整个仓库反复出现的规则，从这里开始：

> **Model proposes；application code validates、authorizes、executes、persists，并负责 stop。**

模型负责“建议下一步是什么”，并不意味着模型拥有“下一步一定执行”的权力。

## Context 从一开始就是 Engineering 问题

即使 frontier model 拥有非常大的 context window，也不代表每一个 token 都值得发送。

Stage 00 先解释容量、token、cost 和 latency；Stage 06A 再把：

```text
selection
compaction
progressive disclosure
provenance
isolation
```

发展成完整的 Context Engineering discipline。

## 当前 Model 说明

Tiny-Agent 在确实需要 live OpenAI call 的 example 中，可以使用当前 GPT-5.6 family model ID。

但请牢记：

```text
model name
price
context size
parameter details
```

都是会变化的 provider-level details。架构不能依赖某一个固定 model name。

当前 OpenAI model catalog：
https://platform.openai.com/docs/models

## 完成检查

进入 Stage 01 之前，你应该能够不看笔记解释完整流程：

```text
instructions + task + selected context + Tool schemas
        ↓
model inference
        ↓
ToolCall proposal
        ↓
local validation / policy
        ↓
real Python / API execution
        ↓
Tool observation
        ↓
next selected model context
        ↓
next proposal or final answer
```

如果这里仍然把“模型输出 ToolCall”理解成“模型自己执行了 Python”，建议不要急着进入 Agent framework；后面的很多概念都会因此整体错位。

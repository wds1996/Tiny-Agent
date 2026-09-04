# 01 — 什么时候应该使用 Multiple Agents？

> Language: [English](01-when-to-use-multiple-agents.md) | 简体中文

Multi-Agent 很有用，但**Agent 数量不是成熟度徽章**。

系统里有五个 Agent 名字，也可能只是一个套了五层马甲的 deterministic pipeline。

真正的问题不是：

> 怎么创建更多 Agent？

而是：

> **哪一个工程问题，因为 responsibility 被拆到 autonomous Agent boundary 后，真的变得更容易了？**

---

## 1. 从更简单的 Architecture 开始

Tiny-Agent 已有：

```text
plain function
-> deterministic workflow
-> one Agent with Tools
-> one Agent + RAG/MCP/memory
-> multi-Agent
```

只有前一种不再合适时，才继续向右。

如果任务只是：

```text
load CSV -> validate columns -> aggregate revenue -> save report
```

却创建：

```text
CSV Agent
Validation Agent
Revenue Agent
Saving Agent
```

本质上只是开了一场昂贵的办公室会议。直接写代码更合适。

---

## 2. 真正理由：不同 Expertise Boundary

当 subtask 需要明显不同的 instruction/context/Tool/evaluation criterion 时，拆分有意义。

```text
Research specialist
- external evidence
- citation rules
- search Tools

Legal reviewer
- policy corpus
- narrow legal instructions
- no external mutation Tool

Writer
- style guide
- approved source summaries
```

这里的 boundary 承载了真实责任差异。

---

## 3. 真正理由：Context Isolation

One giant Agent 可能同时看到 billing data、research corpus、legal notes、production credential、marketing docs。

Multi-Agent 可以 projection：

```text
research -> research-safe context
billing  -> billing-safe context
writer   -> approved summaries only
```

好处不是“智力变高”，而是 **context 与 authority domain 变小**。

---

## 4. 真正理由：Independent Parallel Work

例如：

```text
quality analysis ─┐
cost analysis    ─┼─> synthesis
risk analysis    ─┘
```

只有在 subtask 独立、工作量值得并行、fan-in 有明确 aggregation rule 时并行才有意义。

不要把有依赖的：

```text
retrieve -> read -> conclude
```

硬并行。那不是 parallel intelligence，而是“拒绝承认时间顺序”。

---

## 5. 真正理由：Ownership Transfer

Support 场景：

```text
triage --handoff--> refund specialist
```

关键不是“第二个 LLM 被调用”，而是：

> **Conversation ownership 发生变化。**

这与 manager 只让 specialist 做一个 bounded subtask 完全不同。

---

## 6. 真正理由：Independently Deployed Agent System

另一个 Agent 可能由其他团队/公司构建，使用其他语言，拥有你看不到的 private Tool/memory。

这时 A2A 这类 Agent interoperability protocol 有意义：remote Agent 暴露 contract，而不暴露内部实现。

---

## 7. 弱理由与 Warning Sign

- “感觉更 agentic”——不是工程需求。
- “每一步都值得一个 persona”——persona 不是 architecture boundary。
- “模型有点乱，所以再加三个模型”——真正问题可能是 Tool description、context、routing、state、validation 或 retrieval。
- “框多的图看起来更高级”——PowerPoint 不是 distributed-system benchmark。

---

## 8. 同一个 Foundation Model 也可以形成不同 Agent

Agent boundary 可以来自不同：instruction、Tool、context、permission、memory、output contract、runtime policy，而不要求 foundation model 权重不同。

---

## 9. Multiple Model Calls 也不等于 Multi-Agent

```text
classify -> extract -> summarize -> verify
```

即使调用不同 model，只要 path 由 application 固定，每一轮只是 workflow stage，就更应该称为 workflow。

Tiny-Agent 不会给每次 API call 发一张“Agent 身份证”。

---

## 10. Decision Checklist

增加 Agent 前问：

1. 是否拥有 distinct decision domain？
2. 是否需要 meaningfully different context？
3. 是否需要 distinct Tool set？
4. 是否应该拥有不同 permission？
5. 是回答 manager，还是接管 interaction？
6. 是否真正可并行？
7. 是否独立部署？
8. 能否相较 simpler baseline 证明 measurable benefit？

多数答案为 no，就保留更简单架构。

---

## 11. Complexity 不是免费的

第二个 Agent 带来的不仅是一轮额外 model call，还包括 routing/context-transfer error、constraint loss、coordination loop、latency/token/retry、更多 tracing/permission/failure surface。

一个团队即使 outperform 单 Agent，也仍可能是更差的产品。

---

## 12. Stage 11 Principle

> **继续使用能解决问题的最小动态架构。只有 specialization、isolation、parallel work、ownership transfer 或 interoperability 带来的价值足以支付 coordination overhead 时，Multi-Agent 才值得。**

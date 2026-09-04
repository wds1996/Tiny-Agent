# 07 — Framework Mapping、Evaluation 与 Production Boundary

> Language: [English](07-framework-mapping-and-evaluation.md) | 简体中文

Stage 11 先手写 coordination mechanism，再引入 multi-Agent framework。目的不是拒绝 framework，而是先知道它自动化了什么、哪些 application policy 仍属于你。

---

## 1. Tiny-Agent Handwritten Mapping

```text
AgentSpec
ContextEnvelope / ContextPolicy
DelegationPolicy
CoordinationBudget / CoordinationState
TeamRuntime.delegate()
TeamRuntime.handoff()
TeamRuntime.fan_out()
```

这些 abstraction 直接暴露 control semantics。

---

## 2. OpenAI Agents SDK Mapping

### Manager / Agent as Tool

```text
Tiny-Agent delegate() ~ Agent.as_tool()
```

Specialist 完成 nested run 后回 manager。

### Handoff

```text
Tiny-Agent handoff() ~ Agent(..., handoffs=[...])
```

Target 接管 conversation。

---

## 3. SDK 增加什么？

Mature runtime 可以管理 model turn、specialist invocation、handoff transfer、schema、session、guardrail、tracing、approval、streaming。

它减少 plumbing，但不会替你决定 product authority model、context minimization、business success metric。

---

## 4. LangGraph Mapping

```text
Agent/supervisor/specialist -> node or subgraph
handoff/routing            -> conditional transition
shared state               -> explicit graph state
persistence                -> checkpointer / Store
```

Stage 03 原则仍成立：Graph structure 不自动等于 Agent intelligence。Routing 已知就写 deterministic edge。

---

## 5. 为什么不把所有 Framework 都装一遍？

OpenAI Agents SDK、LangGraph、AutoGen-style、Crew-style、custom runtime 都能做 Multi-Agent。

更可迁移的问题是：谁拥有 control？谁能看到什么 context？谁可以 call 谁？stop condition？failure handling？怎样证明 benefit？

Framework syntax 变化得比这些问题快。

---

## 6. 必须和 Simpler Baseline 比

```text
single Agent baseline
vs
multi-Agent candidate
```

至少测 quality、success rate、latency、cost、Agent-call attempts、handoff attempts/success、failure rate、policy violations。

```text
quality +1%
latency +180%
cost +250%
```

不一定值得。

---

## 7. Coordination Metrics

`coordination_metrics(state)`：

```text
agent_call_attempts
handoff_attempts
successful_handoffs
unique_agents
failed_agent_calls
```

失败 attempt 仍计数，因为它也消耗 budget/latency/API capacity；successful handoff 单独统计，避免把 attempt 当成功 ownership transfer。

还能加 handoff_accuracy、constraint_preservation、specialist_acceptance_rate、parallel_efficiency、coordination_cost。

---

## 8. Handoff Accuracy

Dataset 可标：

```text
input -> expected owner Agent
```

类似 Stage 02 router evaluation，但错 route 现在会改变 conversation owner，所以代价更高。

---

## 9. Delegation Quality

Supervisor 即使选对 specialist，也可能把 subtask 写错。

要分别评估：destination correctness、subtask/constraint correctness、worker output correctness、final synthesis correctness。

Final-answer score 一项诊断不了四个问题。

---

## 10. Agent-aware Trajectory Evaluation

```text
manager -> research -> manager -> reviewer -> manager
```

可定义 forbidden Agent edges、max handoff attempts、required specialist、no ping-pong、no unauthorized remote Agent。

Stage 10 trajectory concepts 直接适用。

---

## 11. Trace Agent Identity

```text
invoke_agent manager
├── delegate research
│   └── invoke_agent research
└── delegate reviewer
    └── invoke_agent reviewer
```

可记录 source/target/coordination.mode，但 raw hidden prompt/private context 继续受 Stage 10 capture policy 控制。

---

## 12. 测试 Failure Topology

不仅测 happy path，还测 denied delegation、unknown Agent、handoff failure/loop、budget exhaustion、invalid parallel batch、private-context isolation、malformed worker output、remote Agent failure、result conflict。

Architecture quality 很大一部分就藏在 edge case。

---

## 13. Production Boundary

不宣称解决 distributed registry、enterprise service identity、cross-service transaction、durable queues、remote cancellation、A2A task DB、multi-region routing、service mesh policy、full distributed tracing。这些进 Stage 13。

---

## 14. 推荐顺序

```text
one Agent vs team
-> manager delegation
-> handoff
-> context isolation
-> fan-out/fan-in
-> governance/loops
-> OpenAI Agents SDK mapping
-> A2A 1.0
-> single-Agent baseline comparison
```

不要从背 framework decorator 开始。

---

## 15. 最终原则

> **好的 Multi-Agent architecture 会让 responsibility 更清楚，而不只是把责任分散得更多。**

如果加 Agent 后 ownership/context/permission/failure/evaluation 反而更难解释，那 architecture 很可能只是复杂得比能力增长得更快。

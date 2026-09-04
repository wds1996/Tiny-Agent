# Stage 11 — Multi-Agent Systems、Handoff 与 A2A Interoperability

> Language: [English](README.md) | 简体中文

## 为什么 Stage 11 才讲 Multi-Agent？

Tiny-Agent 故意把 Multi-Agent 放得很后面。

在把工作拆给多个 Agent 之前，你应该已经理解：single-Agent Tool loop、deterministic workflow/planning、explicit state/LangGraph、RAG/MCP、memory/HITL、reliability/permission/budget、tracing/evaluation。

否则 Multi-Agent 很容易变成：用更多 LLM call 把原本不清楚的 architecture 再包一层。

核心问题不是：

> 怎么创建更多 Agent？

而是：

> **把责任拆到多个 Agent boundary 之后，是否真的产生了足以抵消 coordination、latency、cost 和 failure surface 的可测价值？**

---

## 学习目标

完成 Stage 11 后，你应该能够解释并实现：

1. 什么时候 deterministic workflow / one Agent 比团队更合适；
2. 有明确责任边界的 specialist Agent；
3. manager-style delegation：manager 保持 control；
4. handoff：conversation ownership 转移；
5. supervisor/worker orchestration；
6. controlled context projection，而不是 full-state copying；
7. parallel fan-out + application-owned fan-in；
8. delegation allowlist、handoff budget、loop protection；
9. 用 single-Agent baseline 评估 multi-Agent；
10. OpenAI Agents SDK `Agent.as_tool()` vs handoff；
11. A2A 1.0 的 Agent Card、Message、Task、Part、Artifact；
12. MCP capability interoperability 与 A2A Agent interoperability 的区别。

---

## Stage 11 心智模型

```text
                   Application policy
                         |
              +----------+----------+
              |                     |
        DelegationPolicy        ContextPolicy
              |                     |
              +----------+----------+
                         |
                         v
                    TeamRuntime
                         |
          +--------------+--------------+
          |              |              |
       delegate        handoff        fan_out
          |              |              |
          v              v              v
     specialist     new active     parallel workers
       returns          Agent              |
          |              |                 v
          +--------------+------------> application fan-in
```

模型可以提出 destination；Application 仍拥有 registered Agents、allowed edges、context visibility、coordination budget、Tool permission、approval、stop condition。

---

# 两种最重要的 Control Semantics

## Delegation / Agent as Tool

```text
user -> manager -> specialist -> manager -> user
```

Manager 一直是 active/user-facing Agent。Specialist 只是完成 bounded subtask 并把结果交回 manager。

## Handoff

```text
user -> triage -> specialist -> user
```

成功 transfer 后 specialist 成为 active Agent。

使用 handoff 的前提是 domain ownership 真的发生变化，而不是“又调用了一个模型”。

---

# Handwritten Core

`src/tiny_agent/multi_agent.py` 新增：

```text
AgentSpec
AgentInput
ContextEnvelope / ContextPolicy
DelegationPolicy
CoordinationBudget / CoordinationState
AgentInteraction / AgentInvocation
TeamRuntime.delegate()
TeamRuntime.handoff()
TeamRuntime.fan_out()
coordination_metrics()
```

Handwritten core 故意只支持 text output，先把 coordination mechanism 看清楚，再引入 framework/runtime-specific structured output。

---

# Important Invariants

1. **Model-proposed Agent name 不是 authority**：必须经过 registry + `DelegationPolicy`。
2. **Delegation 不改变 active ownership**。
3. **Handoff 只有 target 成功后才改变 ownership**；失败保持 source active。
4. **Context 被 projection，而不是 full application state 全量复制**。
5. **Coordination state 是 run-scoped**。
6. **Parallel batch 必须 launch 前一次性全量 prevalidate**。
7. **Worker exception message 不直接进入 cross-Agent output**，只记录 exception type。
8. **Handoff loop 受到 total handoff/repeated-edge deterministic limit**。

---

# A2A Interoperability Target

本阶段目标：

```text
A2A specification: 1.0
Python SDK line:    1.1.x
```

A2A 允许独立、内部可 opaque 的 Agent system：

- 通过 Agent Card 发现彼此；
- 交换 Message 与 typed Part；
- 建立 stateful Task；
- 交付 Artifact；
- stream progress；
- 支持 async/long-running interaction。

本阶段只离线构造当前 A2A protocol object。真正 network server/client、service identity、task store 与 deployment 留到 Stage 13。

---

# MCP vs A2A

```text
MCP: Agent/Application -> Tools / Resources / Prompts
A2A: Agent System A    -> Agent System B
```

Remote A2A Agent 内部可以使用 MCP、LangGraph、OpenAI Agents SDK 或 custom runtime，caller 不需要知道内部 topology。

---

# OpenAI Agents SDK Mapping

## Manager Pattern

```python
specialist_tool = specialist.as_tool(
    tool_name="research_expert",
    tool_description="Handle a bounded research subtask",
)
manager = Agent(..., tools=[specialist_tool])
```

Specialist 在 manager 背后运行并返回。

## Handoff Pattern

```python
triage = Agent(..., handoffs=[refund_agent])
```

Specialist 接管 conversation。

本阶段 SDK example 只 build/inspect object，不进行 live model call，因此不需要 API key。

---

# 推荐学习顺序

1. [`theory/01-when-to-use-multiple-agents.zh-CN.md`](theory/01-when-to-use-multiple-agents.zh-CN.md)
2. `code/one_agent_vs_team.py`
3. [`theory/02-delegation-handoffs-supervision.zh-CN.md`](theory/02-delegation-handoffs-supervision.zh-CN.md)
4. `code/specialist_team.py`
5. `code/handoff_demo.py`
6. `code/supervisor_workers.py`
7. [`theory/03-context-ownership-and-shared-state.zh-CN.md`](theory/03-context-ownership-and-shared-state.zh-CN.md)
8. `code/context_isolation.py`
9. [`theory/04-parallelism-and-coordination.zh-CN.md`](theory/04-parallelism-and-coordination.zh-CN.md)
10. `code/parallel_fanout.py`
11. [`theory/05-delegation-governance.zh-CN.md`](theory/05-delegation-governance.zh-CN.md)
12. `code/delegation_governance.py`
13. [`theory/06-a2a-interoperability.zh-CN.md`](theory/06-a2a-interoperability.zh-CN.md)
14. `code/a2a_protocol_objects.py`
15. [`theory/07-framework-mapping-and-evaluation.zh-CN.md`](theory/07-framework-mapping-and-evaluation.zh-CN.md)
16. `code/openai_agents_patterns.py`
17. `code/multi_agent_eval.py`
18. [`exercises/review-questions.zh-CN.md`](exercises/review-questions.zh-CN.md)

---

# 安装与 Tests

```bash
python -m pip install -e ".[dev]"
python -m pip install -e ".[dev,stage11]"
```

Optional dependencies：

```text
openai-agents >= 0.22, < 1
a2a-sdk       >= 1.1, < 2
```

Core：

```bash
pytest -q tests/test_multi_agent.py
```

Integrations：

```bash
pytest -q tests/test_stage11_integrations.py
```

---

# External Resources

OpenAI Agents SDK：
- https://openai.github.io/openai-agents-python/agents/
- https://openai.github.io/openai-agents-python/multi_agent/
- https://openai.github.io/openai-agents-python/tools/
- https://openai.github.io/openai-agents-python/handoffs/

A2A：
- https://a2a-protocol.org/latest/specification/
- https://a2a-protocol.org/latest/topics/key-concepts/
- https://a2a-protocol.org/latest/whats-new-v1/
- https://a2a-protocol.org/latest/sdk/python/api/

阅读旧 A2A 教程时务必检查 protocol version；1.0 与 0.3-era 的 operation/card shape 已有变化。

---

# Interview-ready Distinctions

```text
Workflow != Multi-Agent
Multiple model calls != Multi-Agent
Agent as Tool != Handoff
Shared context != copy all state
Discovery != authorization
Delegation != privilege escalation
Parallelism != free speed
A2A != MCP
Agent Card != internal Tool registry
Correct final answer != good coordination trajectory
```

---

# Milestone

你应该能构建一个 specialist team，其中 manager 能 bounded delegation、handoff ownership、project minimum context、限制 Agent call/handoff、并行 fan-out，并输出 coordination metrics。

最后回答：

> **这个团队是否真的比更简单的 single-Agent/workflow baseline 好到足以值得额外复杂度？**

---

# Stage Boundary

本阶段不宣称已经实现 enterprise distributed registry、production A2A server、durable A2A task store、service-mesh authorization、distributed transaction/exactly-once、remote cancellation guarantee、remote Agent sandbox、multi-region scheduling 或 production queue/worker infrastructure。

这些属于 Stage 13 production/deployment。Stage 11 先把 coordination architecture 与 interoperability semantics 建立正确。

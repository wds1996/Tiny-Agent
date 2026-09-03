# 03 — Context Ownership、Shared State 与 Information Boundary

> Language: [English](03-context-ownership-and-shared-state.md) | 简体中文

Multi-Agent 会在多个 reasoning boundary 之间移动信息。这既增加 capability，也增加风险。

---

## 1. Shared Context != Copy Everything

Naive：

```python
worker_input = entire_application_state
```

可能把 conversation、retrieved docs、其他 Agent scratch state、billing data、credential、approval record、routing metadata 全送过去。

大多数 worker 根本不需要这些。

---

## 2. Tiny-Agent Context Model

```text
ContextEnvelope
├── shared
└── private_by_agent
```

`ContextPolicy` 再 projection target view。

例如 shared 有 question/language/customer_id/api_key；research private 有 source_policy；billing private 有 invoice_scope。

Policy 可以规定 research 只看 question/language，billing 只看 customer_id；`api_key` 完全不 forward。

---

## 3. Private Namespace 为什么重要？

所有 Agent 都写同一个：

```python
state["notes"] = ...
```

可能互相覆盖、把别人的 draft 当 approved state、暴露 internal scratch、制造 hidden coupling。

Namespace 让 ownership 可见。

---

## 4. Shared State 应该像 API Contract，而不是杂物抽屉

适合 shared：task_id、user_goal、approved constraints、artifact references、public intermediate result。

风险较高：all raw prompts、all credentials、all scratchpads、all Tool outputs forever。

“以后可能有人需要”是所有架构杂物抽屉的经典开场白。

---

## 5. Summary vs Raw History

Specialist 常只需：user goal、critical constraints、relevant evidence，而不是 137 条 transcript + 所有 ToolCall + routing chatter。

可以传 bounded packet：

```text
Task
Constraints
Relevant Context
Expected Output
```

降低 token 与 contamination。

---

## 6. 但 Summarization 会丢 Constraint

原请求：

```text
Compare A and B.
Use only primary sources.
Do not include pricing.
Return JSON.
```

若 summary 只剩 `Compare A and B.`，worker 逻辑再正确也会违反三个要求。

因此区分：

```text
compressible narrative context
vs
non-negotiable structured constraints
```

---

## 7. Handoff 的 Conversation History

Handoff 往往需要更强 continuity，但：

```text
full conversation history != full runtime state
```

即使 user-visible history forward，credential、hidden policy、unrelated Tool trace 仍不应无条件进入 target context。

---

## 8. Shared Memory 也不是自动好事

Memory scope 可以是 user/team/Agent role/project/conversation。

不要默认所有 Agent 都能读写所有 long-term memory namespace。Worker 的临时 observation 更不应该自动变成 company-wide procedural memory。

---

## 9. Blackboard Pattern

```text
Agent A -> shared board <- Agent B
                ^
                |
              Agent C
```

适合贡献 structured artifact，但必须有 schema、ownership、versioning、write permission、conflict handling、provenance。

没有规则的 blackboard，就像一个所有人同时改同一句话的群聊文档。

---

## 10. Durable Intermediate Result 优先用 Artifact

与其共享 giant prompt，不如交换：

```text
research_report.json
risk_review.json
draft.md
```

Artifact 可带 producer、schema/version、created_at、source refs、approval status。

A2A 也区分 conversational `Message` 与 durable `Artifact`。

---

## 11. Context 与 Authority 分开

给 Agent 信息不代表给它 action permission；给它 Tool permission 也不代表需要所有 sensitive context。

分别保留：

```text
ContextPolicy
DelegationPolicy
Tool permission policy
Approval policy
```

Stage 07 在每个 Agent boundary 内仍然成立。

---

## 12. Agent Identity 应进入 Trace

可以记录：

```text
agent.name
source_agent
target_agent
coordination.mode
```

而不是默认记录 raw delegation content。

---

## 13. Context Transfer Checklist

Forward 前问：receiver 需要吗？user-visible 还是 internal？是否含 sensitive data？summary 是否足够？哪些 constraint 必须 exact？artifact 谁拥有？receiver 能否写 shared state？

优秀 Multi-Agent system 不只是协调“智能”，也协调**信息所有权**。

# 05 — Delegation Governance、Authority 与 Budget

> Language: [English](05-delegation-governance.md) | 简体中文

Multi-Agent 增加了新的 control edge，而每一条新 edge 也是一条新的 authority path。

因此 Stage 09 的安全规则在 Multi-Agent 中只会更重要，不会失效。

---

## 1. Model-proposed Destination 仍然只是 Proposal

```json
{"delegate_to": "production_admin_agent"}
```

不代表 destination 合法/授权。

Application 仍检查：registered Agent、allowed source->target edge、coordination budget、context projection、target permission。

Tiny-Agent 使用 default-deny `DelegationPolicy`。

---

## 2. Explicit Agent Registry

不要从 model text 直接：

```python
importlib.import_module(model_output)
```

或 arbitrary URL/Agent lookup。

更安全：

```text
model symbolic destination
-> application registry
-> known AgentSpec / known remote Agent
```

Discovery 与 authorization 分开，和 MCP 一样。

---

## 3. Delegation 不能创造 Authority

Manager 如果只能 read，却可以委派给“能 delete everything”的 Admin Agent，那 delegation 就变成 privilege escalation path。

核心 invariant：

> **Caller 不能仅仅通过“让更高权限 Agent 替我做”，获得自己本来被禁止的 authority。**

生产 IAM 可能用 scopes/claims/policy engine/service identity；Tiny-Agent 小型 allowlist 不冒充 enterprise IAM，但 architecture rule 必须先正确。

---

## 4. Agent Identity != User Authority

“Billing Agent”只是 architecture role，并不能证明当前 user 有 billing mutation permission。

Downstream action 仍需 authenticated principal、resource authorization、argument validation、必要时 approval。

---

## 5. Context Minimization 也是 Security Control

Research 只需要 question/language/public evidence，就不要送 customer payment token、admin session、other Agent private notes。

Projection 限制 confused/compromised worker 的 leakage blast radius。这就是 information least privilege。

---

## 6. Delegation Budget

一个 manager call 很容易放大成：

```text
3 workers × 3 retries × 2 reviewers × 2 follow-up rounds
```

一个请求瞬间变成“小型学术会议”。

应限制 max Agent calls/handoffs/parallel width/same-edge handoffs、wall-clock、tokens、cost。

---

## 7. Handoff Loop 是 Control-plane Failure

```text
A -> B -> A -> B
```

它与 repeated Tool 不同，因为还反复改变 ownership。

Repeated-edge limit 是简单 deterministic guard；更强系统还可 path hashing、no-progress、state convergence、semantic duplicate detection。

---

## 8. Failed Handoff 不转移 Ownership

```text
reserve attempt
-> invoke target
-> success? yes: switch owner / no: source stays active
```

这避免 broken control pointer，也是 transactional thinking 的一个例子。

---

## 9. Parallel Fan-out 先 Prevalidate

Batch 中只要一个 edge forbidden，应先整体发现，不要一半 reserve/launch 后才失败。

这样 budget 与 trace 也更容易解释。

---

## 10. Remote Agent Output 是 Untrusted Data

A2A compliance 不让 remote Agent 自动变成可信。它可能 wrong、compromised、malicious、stale、prompt-injected、policy 不同。

```text
receive -> validate -> trust policy -> evaluate -> downstream use
```

---

## 11. Agent Card Metadata 不是 Permission

Agent Card 描述“remote system 声称会做什么、怎么通信”，不回答“当前用户是否有权要求它做”。

```text
discovery != authorization
```

---

## 12. Handoff Context 可以携带 Prompt Injection

Conversation history 中的 untrusted web/retrieved content 被 forward 时，attack surface 也一起 forward。

Target Agent 必须继续遵守：

```text
external data != control-plane authority
```

---

## 13. Human Approval 不会因为 Multi-Agent 消失

“另一个 Agent review 过”不等于 human/policy approval。

LLM 委员会再多人，本质仍然是 LLM 委员会。

---

## 14. Trace Control Edge

记录：

```text
source_agent
target_agent
coordination.mode
handoff_count
agent_call_count
```

但不要默认记录完整 delegation prompt/private context。

---

## 15. 核心 Invariant

> **Delegation 改变的是谁进行 reasoning；它不能偷偷改变谁有权做什么。**

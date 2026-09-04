# 07 — 组合起来：Guarded Execution Pipeline

> Language: [English](07-guarded-runtime-and-production.md) | 简体中文

Stage 00–06 逐步增加 capability。

Stage 09 给这些能力增加一条组合原则：

> **模型可以 proposal；每一个真正产生后果的 transition 都必须由 runtime mediation。**

本章把前面所有机制串成一个 execution pipeline。

---

## 1. Naive Pipeline

```text
LLM
  ↓
ToolCall
  ↓
handler(**arguments)
```

它很短，也几乎漏掉了前面学过的所有 production control。

---

## 2. Guarded Pipeline

Stage 09 使用：

```text
LLM ToolCall proposal
        ↓
BudgetLedger.consume_tool_call()
        ↓
resolve registered Tool
        ↓
validate arguments locally
        ↓
principal / role allowlist
        ↓
exact-action approval if required
        ↓
repeated-call detector
        ↓
ToolExecutionPolicy
        ↓
timeout
        ↓
execute
        ↓
classify failure
        ↓
retry only if:
  retryable failure
  AND retry-safe operation
  AND attempts remain
  AND global retry budget remains
        ↓
model-safe result/failure
```

每一根箭头都是 application-owned control point。

---

## 3. 为什么顺序重要？

### Budget before execution

已经知道超预算，就不要先执行再记账。

### Validation before permission fingerprint / execution

先得到定义明确的 argument object，再做后续判断。

### Authorization before side effect

这听起来显而易见，但很多 demo 正好跳过了它。

### Loop detection before execution

不要再付出一次 side effect，执行后才发现“原来又循环了一次”。

### Timeout around operation

给等待设上限。

### Failure classification before retry

Bad arguments、permission errors、programming bugs 不应该因为“发生 exception”就 retry。

---

## 4. 为什么 Policy 与 Tool Implementation 分开？

Tool 描述 capability：

```text
name
description
parameters
handler
```

Policy 描述 deployment context：

```text
who can call it
whether approval is required
how long it may run
whether retries are safe
how many calls are allowed
```

同一个 Tool 在不同环境可以有不同 policy：

```text
local developer environment
    -> broader capability

production customer environment
    -> narrower capability
```

把所有 policy 都硬塞进 handler，会让 reuse 和 audit 更困难。

---

## 5. 为什么不把 Stage 09 全塞进 `ToolRegistry`？

因为 `ToolRegistry` 已经有清晰职责：

```text
lookup
schema export
basic invocation
```

Stage 09 通过：

```python
GuardedToolExecutor
```

在外层组合 orchestration/policy。

这样可以保留教学连续性：

```text
Stage 01 ToolRegistry
    仍然简单可读

Stage 09 GuardedToolExecutor
    在它外面组合 reliability/security policy
```

Framework growth 应该增加层次，而不是不断重写旧代码，最后让初学者再也看不见最初机制。

---

## 6. Legacy Runtime 的 Safe Failure Fix

现有 integrated `AgentRuntime` 里确实有一个问题值得直接修：

```text
raw arbitrary exception message
    -> model transcript
```

它现在已经被移除。

但 legacy runtime 故意没有升级成完整 Stage 09 executor。

原因是它仍然承担教学 ReAct loop 的职责。

因此：

```text
AgentRuntime
    -> minimal learning runtime + safe error redaction

GuardedToolExecutor
    -> advanced execution policy layer
```

两条代码路径都保持可读。

---

## 7. Audit Event 已经有了语义，但 Stage 10 才负责 Observability

Stage 09 已经产生结构化信息：

```text
failure.code
failure.retryable
attempt count
budget counters
permission decision
risk level
internal exception type
```

这些都非常适合作为 trace attribute。

但 Stage 09 不负责构建完整 tracing system。

Stage 10 会继续回答：

- 怎样 emit span/event；
- 怎样 correlate Agent/model/tool call；
- 测量什么；
- 怎样 evaluate trajectory；
- 怎样使用 LangSmith/OpenTelemetry。

也就是：

```text
Stage 09 defines meaningful runtime events
Stage 10 observes and evaluates them
```

---

## 8. Stage 09 仍然没有解决什么？

高质量教程必须明确自己的边界。

当前 guarded runtime **不宣称**已经提供：

- enterprise IAM/RBAC/ABAC；
- signed approval workflow；
- distributed rate limiting；
- exactly-once side effects；
- fleet-level circuit breaker；
- hardened arbitrary-code sandbox；
- secret-management infrastructure；
- complete prompt-injection prevention；
- malware scanning；
- DLP/PII classification；
- browser isolation；
- production policy administration；
- full audit retention/compliance；
- red-team coverage。

这些仍然属于 deployment-specific security engineering。

Stage 09 提供的是：让这些系统未来有正确位置接入的 architecture。

---

## 9. Reliability 与 Safety 实际高度耦合

Timeout 是 reliability control，同时也可以防 resource exhaustion。

Tool allowlist 是 security control，也能防 accidental destructive action。

Budget 控制 cost，也能限制 denial-of-wallet。

Idempotency key 支持 retry，同时也减少 duplicate financial side effect。

Agent engineering 中 reliability 与 security 往往共享 runtime primitive，很难完全切成两堵互不相干的墙。

---

## 10. 一个 Practical Production Checklist

把 Tool 暴露给模型前，问：

```text
1. Agent 真的需要这个 capability 吗？
2. 有没有比 generic shell/browser/API proxy 更窄的 Tool？
3. arguments 是否 local validation？
4. user/principal identity 是否 application-owned？
5. authorization 是否 default-deny？
6. high-risk action 是否需要 approval？
7. approval 是否绑定 exact action？
8. underlying credential 是否 least-privileged？
9. 是否有 timeout？
10. 如果 retry，operation 是否 retry-safe/idempotent？
11. 是否存在 global execution budget？
12. loop 能否在 global cap 前被提前检测？
13. output 是否可能包含 secret/hostile instruction？
14. code execution 是否有真实 isolation boundary？
15. Stage 10 将记录/评估什么 event？
```

如果很多答案都是“我们已经在 prompt 里告诉模型不要这么做了”，那 architecture 还没完成。

---

## 11. Stage 09 Invariant

保留这张图：

```text
UNTRUSTED / PROBABILISTIC
model output
retrieved content
remote tool metadata/results
        ↓

DETERMINISTIC MEDIATION
validation
permissions
approval binding
budgets
loop limits
timeouts
retry policy
sandbox boundary
        ↓

SIDE EFFECT
```

Probabilistic reasoning 可以提出 action；deterministic policy 决定它是否真的跨入现实世界。

---

## 12. 一个中文语境下很直观的比喻

一个 capability 很强但没有 governance 的 Agent，就像把下面几样东西一起交给一个极其积极的新实习生：

```text
root password
company credit card
production SSH
```

然后再发一封热情洋溢的邮件：

> “相信你，一定要谨慎操作哦！”

Stage 09 做的事情，就是把这封“鼓励信”换成真正可执行的权限、预算、审批和隔离控制。

---

## Code to Inspect

- `src/tiny_agent/guarded_runtime.py`
- Stage 09 全部 examples

按 [`../README.zh-CN.md`](../README.zh-CN.md) 中的顺序运行。

---

## 完成检查

你应该能不看笔记画出 guarded execution pipeline，并解释：

1. 每个 control 为什么放在那个位置；
2. Tool implementation 与 Tool policy 为什么分离；
3. 原始 `AgentRuntime` 为什么继续保持小；
4. Stage 09 如何为 Stage 10 提供 structured event；
5. 哪些 production security 问题仍 out of scope；
6. 为什么 reliability 与 safety 经常共享 runtime primitives；
7. model proposal 与 execution authority 的本质区别。

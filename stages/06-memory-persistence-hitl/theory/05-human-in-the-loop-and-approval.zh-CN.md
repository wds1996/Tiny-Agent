# Human-in-the-Loop：Approve、Edit、Reject

HITL 经常被演示成一个英雄式 checkbox：

```text
Approve? [Yes] [No]
```

真实 review workflow 往往需要更细：

```text
Yes, exactly as proposed.
No, do not do this.
Do it, but change the recipient/amount/query first.
```

所以 Stage 06 明确建模三种 outcome：

```text
approve
edit
reject
```

---

# 1. HITL 是 control boundary

Agent 可以提出：

```python
{
    "action": "send_email",
    "arguments": {
        "to": "alice@example.com",
        "subject": "Release"
    }
}
```

Runtime 决定这个 action 是否需要 review。

如果需要：

```text
model proposal
     ↓
application review policy
     ↓
interrupt
     ↓
human decision
     ↓
validation + authorization
     ↓
execute or stop
```

Human 没有替代 runtime，只参与一个显式定义的 transition。

---

# 2. Approval request 应是 structured data

Tiny-Agent：

```python
request = ApprovalRequest(
    action="send_email",
    arguments={
        "to": "alice@example.com",
        "subject": "Release",
    },
    reason="External communication has a side effect.",
    risk="high",
)
```

Interrupt payload 应是 serializable application data：

```python
{
    "type": "tool_approval",
    "action": "send_email",
    "arguments": {...},
    "reason": "...",
    "risk": "high",
    "allowed_decisions": ["approve", "edit", "reject"],
}
```

这比把 Python function object、framework exception 或巨大 internal state blob 直接扔给 reviewer UI 更正确。

---

# 3. Approve

Approve 表示：

> 按被 reviewer 看过的 proposal 原样执行。

概念上：

```python
ApprovalDecision(outcome="approve")
```

解析为：

```text
approved = True
arguments = original reviewed arguments
```

但 approve 仍不等于最终 authorization。

---

# 4. Edit

Edit 非常重要。

Agent 提议：

```python
{
    "to": "all-company@example.com",
    "subject": "Draft release note"
}
```

Reviewer 可能想改成：

```python
{
    "to": "release-team@example.com",
    "subject": "Reviewed release note"
}
```

不应该为了改一个 recipient，就先 reject 整个 workflow、手工重启，再要求 model 猜一次。

`edit` 可以：

```python
Command(
    resume={
        "outcome": "edit",
        "edited_arguments": {
            "to": "release-team@example.com",
            "subject": "Reviewed release note",
        },
    }
)
```

然后 workflow 使用 reviewed arguments 继续。

---

# 5. Human edit 后必须 revalidate

Human 也会输错。

Tool schema：

```json
{
  "amount": {
    "type": "number",
    "minimum": 0,
    "maximum": 1000
  }
}
```

Reviewer 改成：

```json
{"amount": -500}
```

Application 仍必须拒绝。

同样：

```text
reviewer changes file path
        ↓
path sandbox policy still applies
```

或者：

```text
reviewer changes SQL query
        ↓
DB permissions still apply
```

因此：

```text
human edit
   ↓
normal schema validation
   ↓
normal authorization
   ↓
execute
```

HITL 不是绕过工程控制的 VIP 通道。

---

# 6. Reject

Reject 表示：

> 不执行 proposed side effect。

Tiny-Agent 故意让 resolution 没有 executable arguments：

```python
ApprovalResolution(
    approved=False,
    arguments=None,
    feedback="Do not send this message.",
)
```

结构上明确“不可执行”。

之后 application 可以：

- end；
- replan；
- 让 model 提供更安全 alternative；
- 把 reviewer feedback 返回给 user。

决定权仍归 application。

---

# 7. Interrupt 为什么依赖 persistence

Graph 到：

```python
raw_decision = interrupt(payload)
```

execution 暂停。

Reviewer 可能：

```text
5 seconds later
5 minutes later
5 hours later
```

才回复。

Runtime 必须持久化 thread state，因此 HITL 与 persistence 天然绑定。

当前 LangGraph interrupt semantics 使用 checkpointer + `thread_id`，再通过 `Command(resume=...)` 恢复。

---

# 8. Resume 时 node 从头重启

Stage 03 的规则在这里尤其关键。

不安全：

```python
def review_node(state):
    send_email(state["draft"])
    approved = interrupt("Was that okay?")
    ...
```

这不是 review，这是 apology workflow。

而且 resume 时 node 重新从头执行，`send_email()` 可能再发一次。

更安全：

```text
prepare proposal
      ↓
interrupt / review
      ↓
approve or edit
      ↓
validate
      ↓
execute side effect
```

危险动作必须发生在 gate **之后**。

---

# 9. Approval 后仍需要 idempotency

即使 side effect 在 approval 后才执行，process 也可能在 external call 中途 crash：

```text
approved
   ↓
call payment API
   ↓
network response lost
   ↓
process restarts
```

Payment 到底发生了吗？Persistence 自己未必知道。

高风险 operation 仍应考虑：

- idempotency key；
- external operation ID；
- status check；
- transactional/outbox design。

Human approval 减少 undesired action，但不替你解决 distributed systems。

---

# 10. Approval != authorization

这是 Stage 06 核心规则之一。

Junior reviewer 点击：

```text
Approve production database deletion
```

但其账户无权批准 production deletion。

Secure system 仍应 deny。

因此：

```text
human decision
     ↓
reviewer identity / role
     ↓
application authorization policy
     ↓
argument validation
     ↓
execution
```

点击按钮只是 intent evidence，不自动等于 permission evidence。

---

# 11. Reviewer 是谁？

严肃 HITL system 需要 review identity / audit context：

```text
reviewer_id
role
request_id
thread_id
action
original_arguments
edited_arguments
decision
feedback
timestamp
policy version
```

Stage 06 教学模型保持较小，但 production boundary 必须从第一天可见。

“A human approved it” 如果不知道哪一个 human，并不是充分 audit record。

---

# 12. Risk-based review

不是每个 Tool 都该 interrupt。

如果软件不断问：

```text
Approve reading current date?
Approve calculating 2+2?
Approve formatting Markdown?
```

用户很快会培养一种安全行为：

> 一路点 Yes，直到软件终于闭嘴。

Review 应该 risk-based。

| Action | Example policy |
|---|---|
| calculator | no review |
| read public docs | usually no review |
| create draft email | maybe no review |
| send email | review |
| write production DB | review + authorization |
| irreversible destructive action | strong review / possibly multi-party |

具体 policy 取决于 product。

---

# 13. Review 真正的 proposal，不要只给模糊一句话

坏 interrupt：

```text
"Approve action?"
```

更好：

```text
Action: send_email
To: release-team@example.com
Subject: Production incident update
Risk: high
Reason: External communication
```

Reviewer 必须看得到 meaningful consequence 才能做有效决策。

Destructive action 可以展示 preview/diff：

```text
rows affected
files changed
permissions added
email recipients
money amount
```

---

# 14. Durable HITL

Stage 06 核心示例：

```text
code/durable_hitl_resume.py
```

证明 reviewer 不需要依赖 original Python process：

```text
runtime A
  -> interrupt
  -> SQLite checkpoint
  -> exits

runtime B
  -> same thread_id
  -> resume reviewer decision
  -> execute
```

这就是 demo callback 与 durable human workflow 的区别。

---

# 15. High-level LangChain HITL middleware

理解底层机制后，高层 Agent API 可以把它包装起来。

当前 LangChain HITL middleware 可以支持 policy-controlled interrupt 与同类：

```text
approve
edit
reject
```

Tiny-Agent 故意先实现低层 model，这样高层 framework convenience 不会看起来像魔法。

---

## 完成检查

你应该能解释：

1. HITL 为什么是 control transition，而不是替代 Agent；
2. approve/edit/reject 区别；
3. edit 为什么重要；
4. edited arguments 为什么必须再次 validate；
5. interrupt 为什么需要 persistence；
6. side effect 为什么应在 approval 后；
7. node restart / idempotency 为什么重要；
8. approval 为什么不等于 authorization；
9. reviewer identity/audit data 为什么重要；
10. 为什么不是所有 Tool 都应 human approval；
11. 什么让 HITL 真正跨 process restart durable。
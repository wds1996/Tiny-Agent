# Human-in-the-Loop: Approve, Edit, Reject

Human-in-the-loop (HITL) is often demonstrated with one heroic checkbox:

```text
Approve? [Yes] [No]
```

Real review workflows need more nuance.

A human may want to say:

```text
Yes, exactly as proposed.
No, do not do this.
Do it, but change the recipient/amount/query first.
```

That is why Stage 06 models three explicit outcomes:

```text
approve
edit
reject
```

---

# 1. HITL is a control boundary

The Agent can propose:

```python
{
    "action": "send_email",
    "arguments": {
        "to": "alice@example.com",
        "subject": "Release"
    }
}
```

The runtime decides whether this action requires review.

If it does:

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

The human is not replacing the runtime.

The human participates in one explicitly defined transition.

---

# 2. Approval request should be structured data

Tiny-Agent defines:

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

The interrupt payload is serializable application data:

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

This is better than exposing a Python function object, framework exception, or giant internal state blob to the reviewer UI.

---

# 3. Approve

Approve means:

> Execute the reviewed proposal without changing its arguments.

Conceptually:

```python
ApprovalDecision(outcome="approve")
```

resolves to:

```text
approved = True
arguments = original reviewed arguments
```

But approval is still not final authorization.

More on that shortly.

---

# 4. Edit

Edit is critically useful.

Suppose the Agent proposes:

```python
{
    "to": "all-company@example.com",
    "subject": "Draft release note"
}
```

A reviewer might prefer:

```python
{
    "to": "release-team@example.com",
    "subject": "Reviewed release note"
}
```

The reviewer should not need to reject the whole workflow, manually restart it, and ask the model to try again.

With `edit`:

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

The workflow can continue with reviewed arguments.

---

# 5. Edited arguments must be revalidated

A human can make mistakes too.

If the Tool schema says:

```json
{
  "amount": {
    "type": "number",
    "minimum": 0,
    "maximum": 1000
  }
}
```

and the reviewer edits:

```json
{"amount": -500}
```

the application must still reject the invalid arguments.

Likewise:

```text
reviewer changes file path
        ↓
path sandbox policy still applies
```

or:

```text
reviewer changes SQL query
        ↓
DB permissions still apply
```

Therefore:

```text
human edit
   ↓
normal schema validation
   ↓
normal authorization
   ↓
execute
```

HITL is not a bypass lane around engineering controls.

---

# 6. Reject

Reject means:

> Do not execute the proposed side effect.

Tiny-Agent's resolution deliberately returns no executable arguments:

```python
ApprovalResolution(
    approved=False,
    arguments=None,
    feedback="Do not send this message.",
)
```

That makes the "do not execute" state structurally obvious.

A workflow can then:

- end;
- replan;
- ask the model for a safer alternative;
- return reviewer feedback to the user.

The choice belongs to the application.

---

# 7. Why interrupt requires persistence

When the graph reaches:

```python
raw_decision = interrupt(payload)
```

execution pauses.

The reviewer may answer:

```text
5 seconds later
5 minutes later
5 hours later
```

The runtime therefore needs to persist state associated with the thread.

This is why HITL and persistence are structurally connected.

Current LangGraph interrupt semantics use a checkpointer plus `thread_id`, then resume with `Command(resume=...)`.

---

# 8. The node restarts on resume

This Stage 03 rule becomes even more important here.

Unsafe:

```python
def review_node(state):
    send_email(state["draft"])   # side effect first
    approved = interrupt("Was that okay?")
    ...
```

This is not review.

This is an apology workflow.

And because the node restarts on resume, `send_email()` may execute again.

Safer:

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

Do the dangerous thing **after** the gate.

---

# 9. Idempotency still matters after approval

Even if execution happens after approval, the process might crash while the external side effect is in flight.

So:

```text
approved
   ↓
call payment API
   ↓
network response lost
   ↓
process restarts
```

Did the payment happen?

Persistence alone may not know.

For high-risk operations, use:

- idempotency keys;
- external operation IDs;
- status checks;
- transactional/outbox designs where appropriate.

Human approval reduces unwanted actions.

It does not solve distributed systems.

---

# 10. Approval != authorization

This is one of Stage 06's central rules.

Suppose a junior reviewer clicks:

```text
Approve production database deletion
```

but their account is not allowed to approve that action.

A secure system should still deny it.

Therefore:

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

A button click is evidence of intent.

It is not automatically evidence of permission.

---

# 11. Who is the reviewer?

A serious HITL system needs reviewer identity and audit context:

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

Tiny-Agent Stage 06 keeps the teaching model small, but the production boundary should be visible from day one.

"A human approved it" is not a sufficient audit record if nobody knows which human.

---

# 12. Risk-based review

Not every Tool deserves an interrupt.

If every action asks:

```text
Approve reading the current date?
Approve calculating 2+2?
Approve formatting Markdown?
```

users will rapidly develop the security behavior known as:

> clicking yes until the software stops bothering them.

Review should be risk-based.

Example:

| Action | Example policy |
|---|---|
| calculator | no review |
| read public docs | usually no review |
| create draft email | maybe no review |
| send email | review |
| write production DB | review + authorization |
| irreversible destructive action | strong review / possibly multi-party |

The exact policy is product-specific.

---

# 13. Review the proposal, not a vague sentence

Bad interrupt:

```text
"Approve action?"
```

Better:

```text
Action: send_email
To: release-team@example.com
Subject: Production incident update
Risk: high
Reason: External communication
```

A reviewer can only make a useful decision if the review payload contains the meaningful consequences.

For destructive actions, consider previews/diffs:

```text
rows affected
files changed
permissions added
email recipients
money amount
```

---

# 14. Durable HITL

Stage 06's key example:

```text
code/durable_hitl_resume.py
```

proves that the reviewer does not need the original Python process to remain alive.

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

That is the difference between a demo callback and a durable human workflow.

---

# 15. High-level LangChain HITL middleware

Once you understand the mechanism, high-level Agent APIs can package it.

Current LangChain HITL middleware supports policy-controlled interrupts and the same broad review outcomes:

```text
approve
edit
reject
```

Tiny-Agent intentionally implements the lower-level model first so the framework convenience layer is not mysterious.

---

## Completion check

You should be able to explain:

1. Why HITL is a control transition, not an Agent replacement.
2. Approve vs edit vs reject.
3. Why edit is useful.
4. Why edited arguments require validation again.
5. Why interrupt requires persistence.
6. Why side effects must happen after approval.
7. Why node restart and idempotency matter.
8. Why approval does not equal authorization.
9. Why reviewer identity/audit data matters.
10. Why every Tool should not require human approval.
11. What makes HITL durable across process restarts.

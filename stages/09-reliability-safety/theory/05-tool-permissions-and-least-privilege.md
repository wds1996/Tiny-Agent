# 05 — Tool Permissions, Least Privilege and Approval Binding

Stage 05 gave Tiny-Agent standardized external capabilities through MCP.

Stage 06 added human approval.

Stage 09 asks the uncomfortable question:

> **Just because the Agent can discover a Tool, why should it be allowed to execute it?**

The answer is: it should not, unless deterministic application policy says so.

---

# 1. Capability discovery is not authorization

An MCP server may advertise:

```text
read_file
write_file
delete_file
send_email
run_query
```

That only means:

```text
these capabilities exist
```

It does not mean:

```text
the current user may execute all of them
```

Tiny-Agent uses a default-deny allowlist.

Unknown capability:

```text
not in policy
    -> deny
```

not:

```text
not in policy
    -> probably fine
```

---

# 2. The Principal

Authorization needs an identity.

Stage 09 models:

```python
Principal(
    subject_id="user-42",
    roles=frozenset({"analyst"}),
)
```

The important part is not the exact class.

It is the architectural boundary:

```text
model
    !=
identity provider
```

Never ask the model:

```text
"Does this user look like an admin?"
```

Identity should come from authenticated application context.

---

# 3. Tool allowlists reduce blast radius

Suppose a read-only research Agent needs:

```text
search_documents
read_document
```

Do not expose:

```text
delete_document
send_email
run_shell
manage_users
```

and hope the system prompt says:

```text
"Please do not use the scary tools."
```

OWASP describes this as Excessive Agency: too much functionality, too much permission, or too much autonomy.

The safest tool is often the one the model never receives.

---

# 4. Prefer narrow tools over open-ended tools

Compare:

```text
run_shell(command: str)
```

with:

```text
get_service_status(service_id)
restart_service(service_id)
```

The first capability surface is enormous.

The second is bounded by application semantics.

This does not mean a shell tool is never appropriate.

It means:

- it needs a much stronger sandbox;
- permissions must be narrower;
- human approval may be mandatory;
- output and side effects need strong auditing;
- it should not be the default solution when a narrow API exists.

---

# 5. Approval is not authorization

Stage 06 taught:

```text
approve / edit / reject
```

Stage 09 makes the next distinction:

```text
human approval
    = a reviewer expressed a decision

authorization
    = application policy verified that execution is allowed
```

An intern clicking Approve does not become an administrator.

Tiny-Agent checks role policy even when an approval object exists.

---

# 6. Approval should be bound to the exact reviewed action

This is a subtle but important upgrade over a plain boolean.

Bad approval representation:

```python
approved = True
```

Approved *what*?

Imagine a reviewer saw:

```json
{
  "tool": "deploy",
  "environment": "staging"
}
```

Then arguments changed to:

```json
{
  "tool": "deploy",
  "environment": "production"
}
```

If the runtime only stores:

```text
approved = True
```

then the old review may authorize the new action.

Stage 09 issues an `ApprovalGrant` over a fingerprint of:

```text
tool name + canonical JSON arguments
```

Conceptually:

```python
grant = ApprovalGrant.issue(
    tool_name="deploy",
    arguments={"environment": "staging"},
    reviewer_id="reviewer-2",
)
```

Reusing it for production fails.

---

# 7. Why fingerprint canonicalization matters

These should mean the same action:

```json
{"a": 1, "b": 2}
```

```json
{"b": 2, "a": 1}
```

So Tiny-Agent canonicalizes JSON before hashing.

The goal is not cryptographic authentication of the human UI.

The goal is to teach the invariant:

> Review must be attached to the action that was actually reviewed.

Production systems may use signed approval records, workflow IDs, database transactions, reviewer identity claims, expiration, and audit logs.

---

# 8. Time-of-check vs time-of-use

A general security problem appears when:

```text
check action A
    ↓
mutate data
    ↓
execute action B
```

Approval binding reduces one version of this problem.

But production systems should also consider:

- resource version changed after review;
- target ownership changed;
- approval expired;
- reviewer lost permission;
- deployment artifact changed;
- price/account balance changed.

Sometimes the runtime must re-check application state immediately before execution.

---

# 9. Downstream authorization still matters

Even if Tiny-Agent has perfect policy code, downstream APIs should also enforce permissions.

Why?

Defense in depth.

```text
Agent runtime allowlist
        ↓
service/API authorization
        ↓
database/storage permissions
```

Do not connect a read-only Agent to PostgreSQL using a superuser account and declare victory because the prompt says "read only".

Least privilege should reach the actual credential.

---

# 10. Permission policy is application-owned

The model can propose:

```json
{
  "tool": "delete_report",
  "arguments": {"report_id": "r-7"}
}
```

But it cannot propose:

```json
{
  "new_role": "admin",
  "policy": "allow everything"
}
```

and expect the runtime to honor that.

Security policy belongs outside model-controlled state.

This is one reason procedural memory from Stage 06 was treated cautiously.

---

# 11. Humorous memory aid

MCP discovery is a restaurant menu.

Permission policy is the waiter checking whether your coupon actually covers the lobster.

Human approval is your friend saying:

> "Yes, order it."

Authorization is the card issuer deciding whether the payment is allowed.

Different layers.

---

## Code to inspect

- `src/tiny_agent/governance.py`
- `code/permission_policy.py`

Run:

```bash
python stages/09-reliability-safety/code/permission_policy.py
```

---

## Completion check

Explain:

1. Discovery vs authorization.
2. Authenticated Principal vs model-inferred identity.
3. Why default deny is safer than default allow.
4. Excessive functionality vs excessive permissions vs excessive autonomy.
5. Narrow tools vs open-ended shell-like tools.
6. Approval vs authorization.
7. Why approval should bind to exact arguments.
8. Why downstream services still need their own authorization.

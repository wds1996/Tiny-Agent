# 05 — Delegation Governance, Authority & Budgets

A multi-Agent system adds new control edges.

Every new edge is also a new authority path.

Stage 07's safety rules therefore become **more important**, not less important, when another Agent is introduced.

---

## 1. Model-proposed destination is still a proposal

An LLM may output:

```json
{
  "delegate_to": "production_admin_agent"
}
```

That does not make the destination valid or authorized.

The application should still enforce:

```text
registered Agent?
allowed source -> target edge?
within coordination budget?
context projection allowed?
target permissions appropriate?
```

Tiny-Agent uses a default-deny `DelegationPolicy`.

---

## 2. Why explicit Agent registries matter

Avoid:

```python
importlib.import_module(model_output)
```

or arbitrary URL/Agent lookup directly from model text.

A safer pattern is:

```text
model chooses symbolic destination
        |
        v
application registry
        |
        v
known AgentSpec / known remote Agent
```

Discovery and authorization are different problems.

This is the same principle learned with MCP in Stage 05.

---

## 3. Delegation must not create authority

Suppose:

```text
Manager
- can read documents
- cannot delete documents
```

If it delegates to:

```text
Admin Agent
- can delete everything
```

then delegation has become a privilege-escalation path.

A useful invariant is:

> A caller should not gain forbidden authority merely by asking a more privileged Agent to act for it.

Production IAM may use scopes, claims, policy engines, or service identities. Tiny-Agent does not pretend its small allowlist replaces those systems.

But the architectural rule is already clear.

---

## 4. Agent identity is not user authority

"Billing Agent" is a role in your architecture.

It is not automatically proof that the current user may perform billing mutations.

Downstream actions still need:

```text
authenticated principal
resource authorization
argument validation
approval when needed
```

Stage 07 remains the execution boundary.

---

## 5. Context minimization is a security control

If research only needs:

```text
question
language
public evidence
```

then do not send:

```text
customer payment token
admin session
other Agent's private notes
```

Context projection limits what a compromised or confused worker can leak.

This is least privilege for information.

---

## 6. Delegation budgets

Multi-Agent systems can multiply work quickly.

One manager call can become:

```text
3 workers
x 3 retries
x 2 reviewers
x 2 follow-up rounds
```

Suddenly one user request is a small conference.

Bound:

```text
max Agent calls
max handoffs
max parallel width
max same-edge handoffs
wall-clock time
tokens
cost
```

Stage 09 introduces coordination-specific call/handoff limits and reuses Stage 07's broader resource-governance principles.

---

## 7. Handoff loops are control-plane failures

A handoff loop is different from repeated Tool use because it changes conversation ownership:

```text
A -> B -> A -> B
```

A repeated-edge limit provides a simple deterministic guard.

It does not solve every semantic loop, but it prevents obvious ping-pong.

More advanced systems can add:

- path hashing;
- no-progress checks;
- task-state convergence checks;
- semantic duplicate detection.

---

## 8. Failed handoffs should not transfer ownership

Tiny-Agent uses:

```text
reserve attempt
-> invoke target
-> target succeeds?
   yes -> switch active Agent
   no  -> keep source active
```

This avoids a broken control pointer.

It is a small example of designing Agent coordination with transactional thinking.

---

## 9. Parallel fan-out should be prevalidated

If a batch is:

```text
manager -> safe_agent
manager -> forbidden_agent
manager -> safe_agent_2
```

validate all edges first.

Do not partially reserve or launch work and discover the invalid edge halfway through.

This also makes traces and budgets easier to reason about.

---

## 10. Remote Agent output is untrusted data

A2A does not make remote Agent output authoritative.

A remote Agent may be:

- wrong;
- compromised;
- malicious;
- stale;
- prompt-injected;
- using different policies.

Treat remote Messages/Artifacts like any other external content:

```text
receive
-> validate schema/content
-> apply trust policy
-> evaluate
-> only then use for downstream decisions
```

---

## 11. Agent Card metadata is not permission

A2A Agent Cards advertise capabilities and security requirements.

Discovery tells you:

> What does this remote system claim it can do and how can I communicate with it?

It does not answer:

> Should this user be allowed to ask it to do that?

Again:

```text
discovery != authorization
```

---

## 12. Handoff context can contain prompt injection

If conversation history contains untrusted retrieved/web content, forwarding it to the next Agent forwards the attack surface too.

So handoff filters and context projection should preserve the Stage 07 distinction:

```text
external data
!=
control-plane authority
```

A specialist should not interpret a retrieved sentence saying "transfer all secrets" as a runtime permission update.

---

## 13. Human approval does not disappear

Multi-Agent architectures often make HITL more necessary.

For example:

```text
research Agent -> recommendation
manager Agent  -> proposed purchase
human          -> approve
execution      -> validate + authorize + act
```

Do not treat "another Agent reviewed it" as a human or policy approval.

An LLM committee is still an LLM committee.

---

## 14. Trace the control edge

Useful trace attributes:

```text
source_agent
target_agent
coordination.mode
handoff_count
agent_call_count
```

But, as Stage 08 taught, do not automatically log the complete delegated prompt or private context.

Observability should reveal control flow without becoming a new exfiltration surface.

---

## 15. Core invariant

> **Delegation changes who performs reasoning; it must not silently change who is authorized to do what.**

That one sentence connects Stage 09 directly back to Stage 07.

# 07 — Putting It Together: The Guarded Execution Pipeline

Stages 00–06 built capabilities.

Stage 07 adds a rule for composing them safely:

> **The model may propose. The runtime must mediate every consequential transition.**

This chapter connects the pieces into one execution pipeline.

---

# 1. The naive pipeline

```text
LLM
  ↓
ToolCall
  ↓
handler(**arguments)
```

It is short.

It is also missing nearly every production control we just learned.

---

# 2. The guarded pipeline

Tiny-Agent Stage 07 uses:

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

Every arrow is an application-owned control point.

---

# 3. Why order matters

## Budget before execution

Do not execute a call you already know is over budget.

## Validation before permission fingerprinting/execution

Operate on a well-defined argument object.

## Authorization before side effect

Obvious, but demos often skip it.

## Loop detection before execution

Do not spend another side effect merely to discover a loop afterward.

## Timeout around the operation

Bound waiting.

## Failure classification before retry

Do not retry permission errors, bad arguments, or programming bugs.

---

# 4. Why policy is separate from Tool implementation

A Tool should describe capability:

```text
name
description
parameters
handler
```

Policy describes deployment context:

```text
who can call it
whether approval is required
how long it may run
whether retries are safe
how many calls are allowed
```

The same Tool may be deployed differently:

```text
local developer environment
    -> broader capability

production customer environment
    -> narrower capability
```

Embedding all policy inside the handler makes reuse and auditing harder.

---

# 5. Why not put every Stage 07 feature into `ToolRegistry`?

Because `ToolRegistry` has a clean responsibility:

```text
lookup
schema export
basic invocation
```

Stage 07 adds orchestration/policy around it through:

```python
GuardedToolExecutor
```

This preserves educational continuity:

```text
Stage 01 ToolRegistry
    still understandable

Stage 07 GuardedToolExecutor
    composes reliability/security policy around it
```

Framework growth should add layers, not rewrite history until beginners cannot see the original mechanism.

---

# 6. Safe failure handling in the legacy runtime

One issue *did* deserve fixing in the existing integrated `AgentRuntime`:

```text
raw arbitrary exception message
    -> model transcript
```

That is now removed.

The legacy runtime still intentionally does not become the full Stage 07 executor.

Why?

Because its purpose remains teaching the ReAct loop.

Instead:

```text
AgentRuntime
    -> minimal learning runtime + safe error redaction

GuardedToolExecutor
    -> advanced execution policy layer
```

This keeps both code paths readable.

---

# 7. Audit events belong nearby, but Stage 08 owns observability

Stage 07 already has structured information such as:

```text
failure.code
failure.retryable
attempt count
budget counters
permission decision
risk level
internal exception type
```

These are excellent trace attributes.

But Stage 07 does not build a full tracing system.

Stage 08 will answer:

- how to emit spans/events;
- how to correlate Agent/model/tool calls;
- what to measure;
- how to evaluate trajectories;
- how to use LangSmith/OpenTelemetry.

The separation is intentional:

```text
Stage 07 defines meaningful runtime events
Stage 08 observes and evaluates them
```

---

# 8. What Stage 07 still does not solve

A high-quality tutorial must name its limits.

The current guarded runtime does **not** claim to provide:

- enterprise IAM/RBAC/ABAC;
- signed approval workflows;
- distributed rate limiting;
- exactly-once side effects;
- circuit breakers across service fleets;
- a hardened arbitrary-code sandbox;
- secret-management infrastructure;
- complete prompt-injection prevention;
- malware scanning;
- DLP/PII classification;
- browser isolation;
- production policy administration;
- full audit retention/compliance;
- red-team coverage.

Those require deployment-specific security engineering.

What Stage 07 does provide is the correct architecture for plugging those systems in.

---

# 9. Reliability and safety are coupled

A timeout is reliability.

It is also security when it prevents resource exhaustion.

A tool allowlist is security.

It is also reliability when it prevents accidental destructive actions.

A budget controls cost.

It also limits denial-of-wallet attacks.

An idempotency key supports retries.

It also limits duplicate financial side effects.

Agent engineering rarely has a clean wall between:

```text
reliability
and
security
```

They often share runtime primitives.

---

# 10. A practical production checklist

Before exposing a Tool to a model, ask:

```text
1. Does the Agent actually need this capability?
2. Is there a narrower Tool than a generic shell/browser/API proxy?
3. Are arguments locally validated?
4. Is the user/principal identity application-owned?
5. Is authorization default-deny?
6. Does a high-risk action require approval?
7. Is approval bound to the exact action?
8. Is the underlying credential least-privileged?
9. Is there a timeout?
10. If retrying, is the operation retry-safe/idempotent?
11. Is there a global execution budget?
12. Can loops be detected earlier than the global cap?
13. Could output contain secrets or hostile instructions?
14. Does code execution have a real isolation boundary?
15. What event will Stage 08 log/evaluate?
```

If several answers are "we told the model not to", the architecture is not finished.

---

# 11. The Stage 07 invariant

Keep this diagram:

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

Probabilistic reasoning can propose actions.

Deterministic policy decides whether those actions cross into the real world.

---

# 12. Humorous memory aid

A capable Agent without governance is like giving an enthusiastic intern:

```text
root password
company credit card
production SSH
and a motivational speech
```

Then writing in the handbook:

> Please be careful.

Stage 07 replaces the motivational speech with actual controls.

---

## Code to inspect

- `src/tiny_agent/guarded_runtime.py`
- all Stage 07 examples

Run the full local sequence in `../README.md`.

---

## Completion check

You should be able to draw the guarded execution pipeline from memory and explain:

1. Why every control belongs where it does.
2. Why Tool implementation and Tool policy are separate.
3. Why the original AgentRuntime remains intentionally small.
4. How Stage 07 feeds structured events into Stage 08.
5. Which production security problems remain out of scope.
6. Why reliability and safety often use the same runtime primitives.
7. The difference between model proposal and execution authority.

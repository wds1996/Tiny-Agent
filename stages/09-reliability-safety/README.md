# Stage 09: Once the Agent Can Act, Teach It Not to Wreck Things — Reliability, Safety, and Guardrails

> Language: **English** | [简体中文](README.zh-CN.md)

By Stage 08, the Agent has a large capability surface. It can call Tools, retrieve evidence, connect to remote MCP servers, retain selected memory, load Skills, and pause for human review.

That is exactly why failures now matter. A bug may no longer mean “the answer sounds odd.” It may mean repeated side effects, uncontrolled retries, unauthorized Tools, leaked credentials, or an Agent looping until someone notices the bill.

Stage 09 does not add intelligence. It adds brakes.

The central rule is:

> **Reliability is not a more obedient model, and safety is not one extra sentence in the prompt. Both must become rules the runtime can check and reject.**

---

## 1. Classify failure before retrying it

This is a tempting pattern:

```python
except Exception:
    retry()
```

It can turn one failure into ten.

Model failures, validation failures, permission failures, Tool failures, dependency failures, and budget failures need different responses. Missing arguments will not repair themselves through repetition.

The teaching runtime uses:

```python
class ToolFailure(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False):
        ...
```

Retryability is explicit data, not a guess derived from exception text.

---

## 2. Validation comes before execution

A Tool proposal is still a proposal.

```python
ToolSpec(
    name="lookup_order",
    required={"order_id": str},
    handler=lookup_order,
)
```

Before the handler runs, `tool.validate(arguments)` checks required fields, types, and unknown fields.

A production system may use Pydantic, JSON Schema, or domain validators. The library can change; the ordering should not:

```text
proposal
    ↓
validation
    ↓
policy
    ↓
budget
    ↓
execution
```

---

## 3. Capability discovery is not permission

Stage 05 gave us `discovery != authorization`. Stage 08 gave us `declaration != authorization`. Now that becomes runtime code.

A principal has roles:

```python
Principal(
    id="alice",
    roles=frozenset({"support"}),
)
```

A permission policy grants Tools to roles:

```python
PermissionPolicy(
    {
        "support": {"lookup_order"},
        "refund_manager": {"lookup_order", "issue_refund"},
    }
)
```

A support principal attempting `issue_refund` is denied because the grant is absent. No intent classifier is required to decide this.

---

## 4. Default deny protects new capabilities

Suppose the system adds `delete_customer_account`.

Under default allow, a forgotten permission entry may expose it immediately. Under default deny:

```text
no explicit grant
    ↓
no execution
```

This requires more deliberate configuration and creates a much safer failure mode.

---

## 5. Approval and authorization are separate checks

Stage 06 separated approval from authorization. The full sequence is:

```text
model proposes
    ↓
validate
    ↓
authorize principal
    ↓
obtain approval when required
    ↓
validate final reviewed arguments
    ↓
authorize again if necessary
    ↓
execute
```

Approval should bind to an exact action and arguments. It should not become a permanent permission token.

---

## 6. Legal calls can still run forever

A model can make a perfectly valid `lookup_order("ORDER-42")` call five hundred times. That is still broken.

The chapter adds run-wide budgets:

```python
@dataclass(slots=True)
class ExecutionBudget:
    max_tool_calls: int
    max_retries: int
    max_same_call: int
```

This continues the same idea as Stage 01 `max_steps` and Stage 02 planning budgets: autonomy needs a bounded horizon.

---

## 7. Repeated calls may indicate a loop

Arguments are canonicalized and hashed with the Tool name:

```python
canonical = json.dumps(arguments, sort_keys=True)
fingerprint = sha256(f"{tool_name}:{canonical}")
```

The runtime counts identical fingerprints and stops after `max_same_call`.

Repeated calls can be legitimate. The point is not to ban repetition; it is to make repetition explicitly bounded.

---

## 8. Retry only failures that may improve

A temporary dependency outage may be retryable. “Order does not exist” is not.

The runtime retries only when the failure says it is retryable. Even then, side effects require another check.

---

## 9. Side effects make retries expensive

A refund may succeed while its response is lost. Retrying blindly can duplicate the effect.

`ToolSpec` therefore declares:

```python
safe_to_retry: bool
```

Read-only operations can usually opt in. Side-effecting operations should stay conservative unless the real execution system provides an idempotency contract.

This repeats the Stage 06 lesson:

```text
durable recovery != exactly-once side effect
```

---

## 10. An idempotency key is not a guarantee by itself

A stable key such as `refund:run-17:ORDER-42` can let an execution service recognize duplicate attempts.

But adding a field named `idempotency_key` does not implement idempotency. The actual execution boundary must enforce it.

The runtime should treat idempotency as an explicit contract, not a hopeful string.

---

## 11. Timeouts are less magical than tutorials suggest

A thread `future.result(timeout=3)` often means only that the caller stops waiting after three seconds. The worker thread may still be running and producing side effects.

This chapter therefore uses a cooperative deadline:

```python
ExecutionContext(
    deadline_monotonic=...
)
```

Handlers call `context.check_deadline()` at safe interruption points.

Strong termination of arbitrary code belongs to a stronger process or sandbox boundary, which Stage 12 will cover.

---

## 12. Propagate one deadline down the call chain

A ten-second request should not give every downstream component a fresh ten seconds.

Use an absolute deadline and let each layer observe remaining time. That keeps nested operations inside the original request budget.

---

## 13. Error messages are an output boundary

Returning `str(exc)` can leak `Authorization: Bearer ...`, `password=...`, or `api_key=...`.

The teaching runtime redacts obvious secret patterns and does not reflect unknown internal exceptions verbatim.

This is not full DLP. It establishes the more important default: internal exceptions are not automatically model-visible output.

---

## 14. External content is data, not a new system instruction

RAG evidence, MCP resources, Skill references, and user text can contain instruction-like language. Their relevance does not grant them authority.

```text
application-owned instructions
        ↓ higher authority

external content
        ↓ data

model proposal
        ↓ policy checks still apply
```

Prompt injection becomes dangerous when low-trust content can reach high-impact capabilities without independent policy boundaries.

The strongest defenses are therefore least privilege, validation, authorization, approval, and execution isolation—not a blacklist of suspicious phrases.

---

## 15. Skills do not expand permissions

A Skill may recommend creating a release. If the principal lacks `create_release`, the Skill does not change that fact.

Procedure and authority remain separate.

---

## 16. Model-visible errors and engineer diagnostics should differ

A model may need:

```text
tool_error
retryable = true
message = "upstream temporarily unavailable"
```

An engineer may need stack traces, request IDs, and internal dependency details. Those audiences should not automatically receive the same string.

Stage 10 will turn this separation into an observability design.

---

## 17. The guarded execution pipeline

The complete entry point looks like:

```python
executor.execute(
    principal=principal,
    tool_name="lookup_order",
    arguments={"order_id": "ORDER-42"},
    budget=budget,
    context=context,
)
```

Internally:

```text
lookup ToolSpec
    ↓
validate
    ↓
authorize
    ↓
budget / loop check
    ↓
deadline check
    ↓
execute
    ↓
classify failure
    ↓
bounded retry when safe
    ↓
safe result or safe error
```

The pipeline matters more than the name of a guardrail library.

---

## 18. Why sandboxing is not in this chapter

These Tools are still application-owned Python handlers.

Stage 09 asks who may call them, with what arguments, how often, and under which retry/deadline rules.

Stage 12 will ask a different question: what happens when the Agent can run shell commands, scripts, or untrusted code inside a workspace.

Keeping those layers separate prevents “safety” from becoming one enormous miscellaneous chapter.

---

## 19. Run the chapter

```bash
python stages/09-reliability-safety/code/demo.py
python stages/09-reliability-safety/code/checks.py
```

The checks cover validation-before-execution, default deny, retry classification, conservative side-effect retry, repeated-call detection, deadlines, and secret redaction.

---

## 20. The next question is evidence of quality

We now have explicit guardrails. But how do we know they make the system better?

A polished final answer can hide unnecessary Tool calls, missing evidence, bad trajectories, higher latency, or a failure to abstain.

Stage 10 therefore asks:

> **How do we observe the trajectory and evaluate whether the Agent actually improved?**

That is Evaluation and Observability.

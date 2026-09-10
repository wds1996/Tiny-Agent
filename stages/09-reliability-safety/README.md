# Stage 09: Once the Agent Can Act, Teach It Not to Wreck Things — Reliability, Safety, and Guardrails

> Language: **English** | [简体中文](README.zh-CN.md)

By Stage 08, the Agent has a large capability surface. It can call Tools, retrieve evidence, connect to remote MCP servers, retain selected memory, load Skills, and pause for human review.

That is exactly why failures now matter. A bug may no longer mean “the answer sounds odd.” It may mean repeated side effects, uncontrolled retries, unauthorized Tools, leaked credentials, or an Agent looping until someone notices the bill.

Stage 09 does not add intelligence. It adds brakes.

The central rule is:

> **Reliability is not a more obedient model, and safety is not one extra sentence in the prompt. Both must become rules the runtime can check and reject.**

First, separate the three terms that recur throughout this chapter:

| Term | Meaning in this chapter | Example |
| --- | --- | --- |
| **Reliability** | The system finishes or reports failure predictably despite transient failures, duplicate requests, and bad input. | A lost response retries only an allowed call and stays within a retry limit. |
| **Safety** | The system does not turn invalid, unauthorized, or high-impact proposals directly into actions. | A `support` principal cannot issue a refund; an error does not send a secret back to the model. |
| **Guardrail** | A runtime check or limit that actually runs and rejects a call when its condition is not met. | Argument validation, permission policy, call budgets, deadlines, and retry rules. |

A guardrail is therefore not another model capability. It is ordinary Host code that runs before and after a real Tool call.

---

## 1. Where guardrails sit in the Runtime

The core implementation in this chapter deliberately does not depend on one
specific LLM. Whether a Tool proposal came from DeepSeek, another model, or an
offline test, the Runtime receives the same `tool_name`, `arguments`,
`principal`, and run Budget. That makes validation, permission, retry, and
deadline rules independently testable rather than model-specific.

The chapter also includes [`code/deepseek_guardrails.py`](code/deepseek_guardrails.py). It lets DeepSeek make real Tool Calling proposals, then sends **every** Tool Call through `GuardedExecutor.execute()`. The Host returns the checked result to the model as a Tool Result; the model cannot bypass that route to invoke a Python handler. The offline `demo.py` and `checks.py` make the same Runtime rules repeatable without an API call.

Start by classifying failures.

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
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable
```

Retryability is explicit data, not a guess derived from exception text.

---

## 2. Validation comes before execution

A Tool proposal is still a proposal.

The real registration in `demo.py` is:

```python
ToolSpec("lookup_order", {"order_id": str}, lookup_order, safe_to_retry=True),
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

## 3. Identity, default deny, and approval are separate gates

Stage 05 gave us `discovery != authorization`. Stage 08 gave us `declaration != authorization`. Now that becomes runtime code.

A `Principal` carries the caller identity and roles:

```python
@dataclass(frozen=True, slots=True)
class Principal:
    id: str
    roles: frozenset[str]
```

A permission policy grants Tools to roles:

```python
policy = PermissionPolicy(
    grants={
        "support": {"lookup_order"},
        "refund_manager": {"lookup_order", "issue_refund"},
    }
)
```

A support principal attempting `issue_refund` is denied because the grant is absent. No intent classifier is required to decide this.

---

### Default deny protects new capabilities

Suppose the system adds `delete_customer_account`.

Under default allow, a forgotten permission entry may expose it immediately. Under default deny:

```text
no explicit grant
    ↓
no execution
```

This requires more deliberate configuration and creates a much safer failure mode.

---

### Approval approves one action; it does not grant permanent permission

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

`GuardedExecutor` begins after the application has obtained any required
approval, so it does not store approval records or replace the Stage 06
Checkpoint. When an approved task resumes, the application should send its
final arguments through the Executor again so validation, authorization, budget,
and deadline checks all run again.

---

## 4. Legal calls still need a bounded budget

A model can make a perfectly valid `lookup_order("ORDER-42")` call five hundred times. That is still broken.

The chapter adds run-wide budgets:

`ExecutionBudget` stores both the configured limits and counters for this Run:

```python
@dataclass(slots=True)
class ExecutionBudget:
    max_tool_calls: int = 8
    max_retries: int = 2
    max_same_call: int = 2
    tool_calls: int = 0
    retries: int = 0
    fingerprints: dict[str, int] = field(default_factory=dict)
```

This continues the same idea as Stage 01 `max_steps` and Stage 02 planning budgets: autonomy needs a bounded horizon.

---

### Repeated calls may indicate a loop

Arguments are canonicalized and hashed with the Tool name:

The real fingerprint calculation in `ExecutionBudget.before_call()` is:

```python
        canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(
            f"{tool_name}:{canonical}".encode("utf-8")
        ).hexdigest()
```

The runtime counts identical fingerprints and stops after `max_same_call`.

Repeated calls can be legitimate. The point is not to ban repetition; it is to make repetition explicitly bounded.

---

## 5. Retry, side effects, and idempotency belong together

A temporary dependency outage may be retryable. “Order does not exist” is not.

The runtime retries only when the failure says it is retryable. Even then, side effects require another check.

---

### Side effects make retries expensive

A refund may succeed while its response is lost. Retrying blindly can duplicate the effect.

`ToolSpec` separates a Tool that is inherently safe to retry from an execution
integration that declares idempotency support:

```python
    safe_to_retry: bool = False
    idempotency_supported: bool = False
```

Read-only operations can usually opt in. Side-effecting operations should stay conservative unless the real execution system provides an idempotency contract.

This repeats the Stage 06 lesson:

```text
durable recovery != exactly-once side effect
```

---

### An idempotency key needs execution support

A stable key such as `refund:run-17:ORDER-42` can let an execution service recognize duplicate attempts. The Runtime therefore requires both an integration that declares `idempotency_supported=True` and an `idempotency_key` on this call; supplying a key alone does not enable retry.

`idempotency_supported=True` is neither model-controlled nor automatically
detected by the Runtime. The engineer maintaining that Tool integration sets it
only after verifying the remote execution contract; in this chapter it records
that Host-side assurance.

But adding a field named `idempotency_key` does not implement idempotency. The actual execution boundary must enforce it.

The runtime should treat idempotency as an explicit contract, not a hopeful string.

### A complete refund-retry example

For this chapter, read **idempotent** as one concrete promise: **when the same business action is delivered again, its effect counts only once.** It does not mean every request has identical output; it means a retry must not refund the customer twice.

[`code/idempotency_demo.py`](code/idempotency_demo.py) deliberately simulates the difficult case: the payment service has already created a refund, but its response is lost on the way back to the Host. A timeout cannot tell the Host whether no refund happened or a refund already happened, so retry is permitted only when the service can recognize the same action.

The service-side core is simple: look up a stored receipt by key first; return it when present, and only create and store a refund when it is absent.

```python
def issue_refund(
    self,
    *,
    order_id: str,
    amount: str,
    idempotency_key: str,
) -> RefundReceipt:
    existing = self._receipts_by_key.get(idempotency_key)
    if existing is not None:
        return existing

    self.created_refunds += 1
    receipt = RefundReceipt(
        receipt_id=f"refund-{self.created_refunds}",
        order_id=order_id,
        amount=amount,
    )
    self._receipts_by_key[idempotency_key] = receipt
    return receipt
```

The demonstration proceeds as follows:

1. The Host derives `refund:run-17:ORDER-42` for “refund 10.00 for `ORDER-42` in this run.”
2. The first call creates `refund-1` at the service, then the transport reports a lost response. This is a `retryable=True` **ambiguous outcome**.
3. `GuardedExecutor` sees both `idempotency_supported=True` on the Tool and the key in the Context, so it retries within budget.
4. The second call reaches the service with the same key. The service returns existing `refund-1`; it does not create a second refund.

Run it:

```bash
python stages/09-reliability-safety/code/idempotency_demo.py
```

The two important output lines are:

```text
executor attempts: 2
refunds created by service: 1
```

That is where the reliability comes from: retry keeps trying to obtain a result, while the execution service folds repeated delivery with the same key into one business action. A real payment, email, or order service must store the key-to-receipt mapping at a durable execution boundary, such as its own database; the dictionary in this example only makes the mechanism small enough to run locally. A **new** refund action needs a new key and must not reuse an old one.

---

## 6. A deadline is the request's shared time boundary

A thread `future.result(timeout=3)` often means only that the caller stops waiting after three seconds. The worker thread may still be running and producing side effects.

This chapter therefore uses a cooperative deadline:

```python
@dataclass(frozen=True, slots=True)
class ExecutionContext:
    deadline_monotonic: float | None = None
    idempotency_key: str | None = None

    def check_deadline(self) -> None:
        if self.deadline_monotonic is not None and time.monotonic() >= self.deadline_monotonic:
            raise DeadlineExceeded("execution deadline exceeded")
```

Handlers call `context.check_deadline()` at safe interruption points.

Strong termination of arbitrary code belongs to a stronger process or sandbox boundary, which Stage 12 will cover.

---

### Propagate one deadline down the call chain

A ten-second request should not give every downstream component a fresh ten seconds.

Use an absolute deadline and let each layer observe remaining time. That keeps nested operations inside the original request budget.

---

## 7. Outputs, external text, and diagnostics need boundaries too

Returning `str(exc)` can leak `Authorization: Bearer ...`, `password=...`, or `api_key=...`.

The teaching runtime redacts obvious secret patterns and does not reflect unknown internal exceptions verbatim.

This is not full DLP. It establishes the more important default: internal exceptions are not automatically model-visible output.

---

### External content is data, not a new system instruction

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

### Skills do not expand permissions

A Skill may recommend creating a release. If the principal lacks `create_release`, the Skill does not change that fact.

Procedure and authority remain separate.

---

### Model-visible errors and engineer diagnostics should differ

A model may need:

```text
tool_error
retryable = true
message = "upstream temporarily unavailable"
```

An engineer may need stack traces, request IDs, and internal dependency details. Those audiences should not automatically receive the same string.

Stage 10 will turn this separation into an observability design.

---

## 8. Bring the rules together in a guarded executor

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

### With DeepSeek, put the guardrail before the Tool Result

A real LLM integration does not change the Runtime entry point. DeepSeek only proposes a Function Call; the Host parses its arguments, invokes `GuardedExecutor`, then returns a safe result to the model as a `role="tool"` message:

```text
DeepSeek Tool Call
    ↓
Host: dispatch_tool_call(...)
    ↓
GuardedExecutor.execute(...)
    ↓
Host guarded result
    ↓
DeepSeek receives a Tool Result
```

[`code/deepseek_guardrails.py`](code/deepseek_guardrails.py) is the complete runnable program; its message sequence follows the [DeepSeek Tool Calls guide](https://api-docs.deepseek.com/guides/tool_calls/). Its boundary function is below. It does not call `lookup_order` or `issue_refund` directly; it sends the model-provided name and arguments to the Executor instead:

```python
def dispatch_tool_call(
    *,
    executor: GuardedExecutor,
    principal: Principal,
    budget: ExecutionBudget,
    context: ExecutionContext,
    call: Any,
) -> tuple[str, str]:
    try:
        arguments = json.loads(call.function.arguments)
    except json.JSONDecodeError:
        return call.function.name, json.dumps(
            {"ok": False, "error": "invalid JSON tool arguments", "attempts": 0}
        )
    if not isinstance(arguments, dict):
        return call.function.name, json.dumps(
            {"ok": False, "error": "tool arguments must be an object", "attempts": 0}
        )
    result = executor.execute(
        principal=principal,
        tool_name=call.function.name,
        arguments=arguments,
        budget=budget,
        context=context,
    )
    return call.function.name, tool_result(result)
```

The Host creates `principal`, `budget`, and `context`; the model cannot forge them in a Function Call. The default `support` role can look up an order but is denied a refund. Only `--role refund_manager` has the example refund permission. The two Handlers are local demonstration data, so they neither contact a payment system nor create a real refund.

---

### Why sandboxing is not in this chapter

These Tools are still application-owned Python handlers.

Stage 09 asks who may call them, with what arguments, how often, and under which retry/deadline rules.

Stage 12 will ask a different question: what happens when the Agent can run shell commands, scripts, or untrusted code inside a workspace.

Keeping those layers separate prevents “safety” from becoming one enormous miscellaneous chapter.

---

## 9. Run, observe, then evaluate

```bash
python stages/09-reliability-safety/code/demo.py
python stages/09-reliability-safety/code/idempotency_demo.py
python stages/09-reliability-safety/code/checks.py
```

`demo.py` shows an allowed read-only call, an unauthorized side effect, one bounded retry, and a deadline rejection. `idempotency_demo.py` verifies “two attempts, one refund created.” `checks.py` also asserts that property automatically.

To run the real DeepSeek Tool Calling integration, install the dependency and set the variables in the **same terminal** that will run Python:

```bash
python -m pip install -r stages/09-reliability-safety/code/requirements.txt
```

Windows Command Prompt (CMD):

```bat
set "DEEPSEEK_API_KEY=your_key_here"
set "DEEPSEEK_MODEL=your_available_deepseek_model"
python stages/09-reliability-safety/code/deepseek_guardrails.py
```

PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="your_available_deepseek_model"
python stages/09-reliability-safety/code/deepseek_guardrails.py
```

The default role is `support`. Even if the model proposes a refund, the Host returns a permission denial under `=== Host guarded result ===`. To observe the same proposal pass with the authorized example identity, run:

```bash
python stages/09-reliability-safety/code/deepseek_guardrails.py --role refund_manager
```

The checks cover validation-before-execution, default deny, retry classification, conservative side-effect retry, an idempotent execution service preventing a duplicate refund, repeated-call detection, deadlines, and secret redaction.

---

### The next question is evidence of quality

We now have explicit guardrails. But how do we know they make the system better?

A polished final answer can hide unnecessary Tool calls, missing evidence, bad trajectories, higher latency, or a failure to abstain.

Stage 10 therefore asks:

> **How do we observe the trajectory and evaluate whether the Agent actually improved?**

That is [Stage 10: Evaluation and Observability](../10-evaluation-observability/README.md).

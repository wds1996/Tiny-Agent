# 01 — Agent Failure Modes and a Safe Error Model

Stage 07 begins with a boring fact that saves exciting outages:

> **Failure is part of the Agent protocol, not an embarrassing exception path.**

A demo often assumes:

```text
model proposes tool
    -> tool succeeds
    -> model continues
```

Production looks more like:

```text
model proposes tool
    -> malformed arguments
    -> permission denial
    -> network timeout
    -> 429 / 503
    -> partial side effect
    -> provider bug
    -> repeated call loop
    -> internal exception containing secrets
```

If every one of those becomes:

```python
except Exception as exc:
    return str(exc)
```

then the runtime has no failure model. It has a confession booth for stack traces.

---

## 1. Why Stage 01 error handling was intentionally incomplete

The first Tiny-Agent runtime taught one important idea:

```text
tool failure
    -> observation
    -> model can recover
```

That is useful for learning ReAct.

But the integrated runtime previously copied arbitrary exception text into the model transcript.

Imagine:

```python
raise RuntimeError(
    "postgresql://admin:super-secret@prod-db/internal"
)
```

A naive observation becomes:

```text
ToolError[RuntimeError]:
postgresql://admin:super-secret@prod-db/internal
```

The Agent just turned an internal diagnostic into model context.

Stage 07 changes the reusable runtime boundary:

```text
known operational failure
    -> deliberately safe message may cross boundary

unknown exception
    -> generic safe message
    -> internal exception type retained for audit
    -> raw message stays internal
```

---

# 2. Typed failures answer operational questions

A useful failure model should answer at least:

```text
What happened?
Can it be retried?
Can the model see a safe explanation?
Should execution stop?
Should a human be involved?
```

Tiny-Agent now uses categories such as:

```text
invalid_arguments
unknown_tool
permission_denied
approval_required
timeout
transient_error
permanent_error
budget_exceeded
loop_detected
internal_error
```

These codes are application control data.

They are more useful than asking the LLM to infer policy from prose like:

```text
"Oops, network maybe failed? Try again if you feel like it."
```

---

# 3. `SafeToolError`

Known application failures can explicitly declare a sanitized message.

```python
from tiny_agent import TransientToolError

raise TransientToolError(
    "Upstream service is temporarily unavailable."
)
```

This can become:

```text
ToolFailure[transient_error]:
Upstream service is temporarily unavailable.
```

The class name is intentionally `SafeToolError`, not `PublicException`.

The contract is:

> The developer has already decided that the message is safe to cross the model boundary.

Do not do this:

```python
raise TransientToolError(str(raw_provider_exception))
```

That merely puts a clean label on an unclean payload.

---

# 4. Unknown exceptions are redacted

Tiny-Agent's default classifier does this:

```python
failure = failure_from_exception(exc)
```

For an unexpected exception:

```python
RuntimeError("secret-token=abc123")
```

model-facing output is only:

```text
ToolFailure[internal_error]: Tool execution failed.
```

while internal metadata may retain:

```text
internal_exception_type = RuntimeError
```

Why keep the type?

Because Stage 08 observability will want to answer:

```text
Which internal exception types are rising?
Which tool is failing most often?
How many failures are transient vs permanent?
```

The model does not need the stack trace to answer the user.

---

# 5. Retryable vs retry-safe are different

This distinction is critical.

A timeout may be:

```text
retryable failure
```

but the operation might not be:

```text
retry-safe action
```

Example:

```text
charge_card($100)
    -> client times out
```

Did the payment fail?

Or did the server charge successfully and the response get lost?

The runtime does not know.

Therefore:

```text
failure.retryable == True
```

is not sufficient to retry.

Tiny-Agent also requires:

```text
ToolExecutionPolicy.retry_safe == True
```

Typical retry-safe cases:

- read-only GET-like operations;
- operations with a downstream idempotency key;
- application operations explicitly designed to tolerate duplicates.

Typical unsafe default:

- send email;
- charge payment;
- delete resource;
- publish release;
- create duplicate records without an idempotency key.

---

# 6. Expected failure vs bug

Do not classify everything as transient merely because retrying made the test pass once.

Example:

```python
def calculate(x):
    return None + x
```

This raises `TypeError`.

That is probably a code bug, not:

```text
invalid user arguments
```

Stage 07 deliberately avoids guessing that every `TypeError` came from a bad ToolCall.

The correct order is:

```text
schema validation before execution
        ↓
known operational errors typed explicitly
        ↓
unexpected exceptions -> internal_error
```

This preserves diagnostic integrity.

---

# 7. Failure classes are not user-facing UX

A model-safe observation may still be too technical for the final user response.

Internal observation:

```text
ToolFailure[permission_denied]:
Principal does not have an allowed role for this tool.
```

Final assistant response could be:

```text
I can't perform that operation with the current permissions.
```

Think of three audiences:

```text
runtime
    -> structured code / retryability

model
    -> safe operational observation

engineer
    -> detailed logs / traces / stack
```

Do not collapse them into one string.

---

# 8. Humorous memory aid

An exception stack trace is like your server's diary.

Useful to the engineer?

Absolutely.

Should you hand the whole diary to every model call because the printer jammed?

Probably not.

---

## Code to inspect

- `src/tiny_agent/reliability.py`
- `src/tiny_agent/runtime.py`
- `code/error_model.py`

Run:

```bash
python stages/07-reliability-safety/code/error_model.py
```

---

## Completion check

You should be able to explain:

1. Why arbitrary `str(exc)` should not enter model context.
2. Why a typed safe error is different from an arbitrary exception.
3. Retryable failure vs retry-safe operation.
4. Why unknown `TypeError` should not automatically become input error.
5. Model-safe observation vs developer log.
6. Why failures need structured codes before Stage 08 observability.

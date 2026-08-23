# 03 — Timeout, Cancellation, Retry, Backoff and Fallback

A reliable Agent does not ask:

> Did the tool fail?

It asks:

> **How did it fail, how long have we waited, is the operation safe to repeat, and what should happen next?**

---

# 1. Timeout is a budget on waiting

Without a timeout:

```text
Agent
  -> tool call
  -> waiting...
  -> waiting...
  -> waiting...
```

One stuck dependency can hold the entire Agent hostage.

Python's current `asyncio.wait_for()` / `asyncio.timeout()` mechanisms cancel overdue async work and surface `TimeoutError` when the deadline is exceeded.

Stage 07 uses this idea around async Tool execution.

---

# 2. Async timeout and sync timeout are not the same

For a real coroutine:

```python
await asyncio.wait_for(
    remote_call(),
    timeout=2.0,
)
```

cancellation can propagate into the task.

But consider a blocking sync function:

```python
def legacy_sdk_call():
    time.sleep(60)
```

If you call it directly inside the event loop, the loop is blocked.

Tiny-Agent therefore runs synchronous handlers in:

```python
asyncio.to_thread(...)
```

before applying an async waiting timeout.

This keeps the event loop responsive.

However:

> **Timing out the await does not magically kill the worker thread.**

The underlying synchronous function may still be running.

This distinction is one reason true hard termination needs a process/container/VM boundary.

---

# 3. Cancellation is control flow

A caller may cancel an Agent task because:

- user pressed Stop;
- HTTP request disconnected;
- deployment is shutting down;
- parent workflow cancelled the branch.

Stage 07 deliberately does not convert `asyncio.CancelledError` into:

```text
ToolFailure[internal_error]
```

Cancellation should propagate.

Otherwise your runtime can become the software equivalent of:

> “I heard you say stop, so I converted that into a warning and continued.”

---

# 4. Retry only transient failures

Retry is useful for failures such as:

```text
temporary 503
connection reset
short-lived rate limit
transient service unavailable
```

Retry is usually pointless for:

```text
invalid arguments
permission denied
unknown tool
business rule violation
malformed schema
programming bug
```

A good retry predicate is therefore narrow.

Tiny-Agent expresses known retryable operational failures with typed exceptions such as:

```python
TransientToolError(...)
ToolTimeoutError(...)
```

Unexpected exceptions default to non-retryable.

---

# 5. Retryable failure != retry-safe operation

This is the most important retry lesson.

Imagine:

```text
send_email()
    -> server accepted email
    -> network response lost
    -> client timeout
```

The failure *looks* retryable.

But retrying may send the email twice.

Therefore Tiny-Agent requires both:

```text
failure.retryable
AND
tool_policy.retry_safe
```

before another attempt is scheduled.

`ToolExecutionPolicy` even rejects this configuration:

```python
ToolExecutionPolicy(
    retry_policy=RetryPolicy(max_attempts=3),
    retry_safe=False,
)
```

at construction time.

This forces the developer to think about duplicate side effects before enabling retries.

---

# 6. Idempotency keys make more operations retry-safe

For a payment-like operation:

```python
charge(
    amount=100,
    idempotency_key="thread-7:payment-2",
)
```

A downstream service can remember that logical operation and avoid applying it twice.

Then a transport retry can repeat the request without repeating the business side effect.

Do not confuse:

```text
HTTP request repeated
```

with:

```text
business action repeated
```

Good idempotency design lets the former happen without causing the latter.

---

# 7. Exponential backoff

If a service is overloaded, retrying immediately can make the overload worse.

A simple backoff sequence:

```text
0.5s
1.0s
2.0s
4.0s
...
```

Tiny-Agent's small `RetryPolicy` implements bounded exponential backoff so learners can inspect the formula.

Production retry libraries such as Tenacity support:

- stop by attempts;
- stop by elapsed time;
- fixed/random/exponential waits;
- exception predicates;
- result predicates;
- async retry;
- callbacks/logging.

The library removes plumbing.

It does **not** know your business idempotency semantics.

---

# 8. Jitter

Suppose 500 Agent workers all receive a 503 at the same time.

Without jitter:

```text
all wait 1s
all retry together
all receive 503
all wait 2s
all retry together
```

Congratulations: the clients have formed a synchronized denial-of-service choir.

Jitter adds randomness so retries spread out.

Tiny-Agent's policy models this explicitly.

---

# 9. Retry budgets are separate from per-call attempts

A single tool may allow:

```text
max_attempts = 3
```

But an entire Agent run also needs a global retry budget.

Otherwise ten different tools can each retry three times and create much more load than expected.

So Stage 07 separates:

```text
per-tool retry policy
```

from:

```text
run-wide BudgetLedger.max_retry_attempts
```

Both must allow another retry.

---

# 10. Fallback is not retry

Retry says:

> Try the same operation again.

Fallback says:

> Use a different implementation or degraded mode.

Examples:

```text
primary search API fails
    -> fallback cached index
```

```text
premium model unavailable
    -> fallback smaller model
```

But fallback also needs policy.

A smaller model may not meet the same quality/safety requirements.

A backup data source may be stale.

Never implement:

```text
if anything fails:
    silently use something else
```

because silent degradation is difficult to debug and evaluate.

Stage 07 focuses on the retry/timeout primitives; Stage 08 will make fallback/degradation observable.

---

# 11. Humorous memory aid

Retry is like knocking again because you think the person did not hear you.

Retrying `delete_database()` is like repeatedly swinging a hammer because you are unsure whether the first window broke.

Same mechanism.

Very different policy.

---

## Code to inspect

- `src/tiny_agent/reliability.py`
- `src/tiny_agent/guarded_runtime.py`
- `code/retry_policy.py`
- `code/guarded_tool_runtime.py`

Run:

```bash
python stages/07-reliability-safety/code/retry_policy.py
python stages/07-reliability-safety/code/guarded_tool_runtime.py
```

---

## Completion check

Explain:

1. Timeout vs cancellation.
2. Why sync thread timeout is not hard termination.
3. Retryable failure vs retry-safe operation.
4. Why idempotency keys matter.
5. Exponential backoff and jitter.
6. Per-tool retry attempts vs global retry budget.
7. Retry vs fallback.
8. Why cancellation should normally propagate instead of becoming a ToolFailure.

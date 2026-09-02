# 04 — Evaluator/repair loops and session boundaries

A long-running Agent should not decide completion only by saying “looks good.”

Use external checks where possible:

```text
unit/integration tests
schema validation
citation checks
static analysis
artifact existence
benchmark thresholds
human review
calibrated LLM judge for semantic dimensions
```

## Generator vs evaluator

A useful pattern is:

```text
worker produces artifact
-> evaluator checks objective criteria
-> pass: mark complete
-> fail: create bounded repair task
```

The evaluator does not need to be another Agent. Deterministic code is preferable whenever it can judge reliably.

## Repair is not blind retry

Retry repeats an operation because the failure is transient and the operation is retry-safe.

Repair changes the artifact/plan because evaluation found a defect.

```text
HTTP 503 -> retry
unit test failed -> repair
requirements changed -> replan
```

Confusing these creates expensive loops.

## Session boundaries are healthy

A new context window/session can be beneficial if continuity is externalized correctly. It removes accumulated conversational noise and forces the harness to reconstruct context from explicit current state.

# 01 — Why long-horizon Agents fail

Long tasks amplify every small weakness in an Agent architecture.

Common failure modes include:

```text
context overflow / context rot
forgotten requirements
repeating completed work
stale plans
drifting objectives
lost artifacts
process/container death
unbounded retries
partial side effects
"done" claims without verification
```

## One session is not durable work

A model transcript is not a project database.

If a task lasts 6 hours, assuming one ever-growing conversation remains available is fragile even if the model advertises a huge context window.

The run needs explicit external state:

```text
objective
task ledger
progress notes
artifacts
checkpoints
approvals
evaluation results
```

## Incremental progress beats heroic completion

A good harness makes each session leave the project in a better, inspectable state:

```text
select bounded task
-> inspect current workspace
-> perform work
-> verify
-> persist artifact/progress
-> hand off
```

This resembles engineers working shifts: the next engineer should not need telepathy to know what happened.

## Long horizon is an orchestration problem

A stronger model helps, but it does not remove:

- crash recovery;
- durable storage;
- ownership/leases;
- side-effect idempotency;
- verification;
- resource limits.

Those remain runtime responsibilities.

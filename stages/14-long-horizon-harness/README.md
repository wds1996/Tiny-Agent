# Stage 14: A Two-Hour Task Cannot Depend on One `while True` — Long-Horizon Agent Harnesses

> Language: **English** | [简体中文](README.zh-CN.md)

Stage 13 separated HTTP requests from durable Runs.

Now let a task run for two hours. A worker dies after eighty-seven minutes and leaves `status = running`. A new worker assumes someone is still working. No one is.

Long-horizon work therefore needs more than a larger `max_steps`.

> **Task progress must outlive a worker, a process, a model context, and sometimes the current workspace.**

Stage 14 builds a durable task ledger, bounded work units, leases, heartbeats, durable outputs, and a bounded repair loop.

---

## 1. Long-running is not the same as durable long-horizon

A loop can run for hours as long as its process survives.

Durable long-horizon execution must survive worker restart, deployment, machine loss, approval waits, rate limits, workspace loss, and context compaction.

If every interruption restarts from zero, the task is merely long-running.

---

## 2. The Task Ledger is external execution truth

The ledger records:

```text
task_id
status
step_index
total_steps
lease_owner
lease_until
progress
repair_count
```

It answers where the task actually is—not where a model summary says it is or where one worker's memory believes it is.

---

## 3. Split large work into bounded units

Instead of one worker owning 0% through 100%, represent a task as steps.

The teaching harness executes exactly one step in `work_once()`:

```python
task = ledger.claim(...)
output = step(progress)
ledger.record_step_output(...)
ledger.advance(...)
```

Frequent durable boundaries improve recovery granularity.

---

## 4. Re-queueing between steps creates clean handoff points

One worker can complete step 0, persist progress, and release ownership. Another worker can execute step 1.

A production system may batch several units, but continuation should not require the original worker.

---

## 5. A Lease makes running ownership expire

A worker claims a task with:

```text
lease_owner = worker-a
lease_until = ...
```

Another worker cannot steal an unexpired lease.

If the owner disappears and the lease expires, the task can be reclaimed.

`running` is no longer permanent ownership.

---

## 6. A Lease is not just a lock

The defining property is ownership plus expiry.

The system can recover even when the old owner disappears.

Real distributed systems may also require fencing tokens and careful clock/database semantics. This chapter focuses on the core idea first.

---

## 7. Heartbeats extend ownership

Long work units can renew their lease.

Only the current owner may heartbeat the task. Otherwise workers could keep each other's leases alive without owning the work.

---

## 8. Recovery can replay a side effect

A worker may complete an external action and crash before recording success. After lease expiry, another worker may rerun the same step.

This is the same invariant from Stages 06 and 09:

```text
recovery != exactly once
```

Long-horizon work units should therefore be idempotent, use stable idempotency keys, verify completion, or have compensation strategies where necessary.

---

## 9. Step outputs should be durable too

The chapter stores output by `(task_id, step_index)`.

Later workers no longer depend on an earlier worker's memory, and operators can inspect what each step actually produced.

---

## 10. Progress should not live only in model context

Model context supports the current decision.

The ledger stores durable progress.

Artifacts store large intermediate and final outputs.

```text
Ledger   -> where am I?
Artifact -> what did I produce?
Context  -> what do I need to see now?
```

Do not ask a model summary to perform all three jobs.

---

## 11. Artifacts externalize long work

Reports, datasets, repositories, test output, and drafts may be too large or too durable for model context.

The workspace from Stage 12 is the active workbench. Long-horizon artifacts should survive the current compute session when the application needs them.

---

## 12. Repair can restart a bounded portion of the task

A verification step may discover that an earlier draft needs repair.

The teaching evaluator can return:

```python
{
    "needs_repair": True,
    "restart_step": 0,
}
```

The task is re-queued from the chosen step rather than silently looping forever.

---

## 13. Repair has a budget

`repair_count` and `max_repairs` stop a draft/verify cycle from becoming permanent autonomous work.

Long horizon means durable, not unlimited.

---

## 14. Evaluator does not automatically mean another Agent

Evaluation may be deterministic tests, schemas, static checks, a human, or an LLM judge.

Do not add an evaluator Agent merely because the architecture diagram has room.

Use the simplest evaluator that can reliably judge the invariant.

---

## 15. New workers need compute rehydration

When a new worker takes over, the old temporary directory may be gone.

A real harness needs enough durable information to reconstruct source, inputs, dependencies, artifacts, and task progress.

Stage 12 provided the workbench. Stage 14 decides what a replacement workbench must recover.

---

## 16. Session handoff should be built from durable state

A summary saying “we were working on...” can be useful context, but it should not be the only recovery record.

Prefer durable task ID, step, structured progress, step outputs, artifact references, and repair history, then build continuation context from that data.

---

## 17. Long horizon does not grant unlimited autonomy

A task that may last days still needs work-unit deadlines, task budgets, cost limits, repair limits, permission scope, and approval points.

Duration is not permission.

---

## 18. Run the chapter

```bash
python stages/14-long-horizon-harness/code/demo.py
python stages/14-long-horizon-harness/code/checks.py
```

The demo performs draft, verify, one bounded repair, and finalize.

The checks cover lease expiry, lease ownership, heartbeats, durable step outputs, one-step work units, repair budgets, restart progress, and completed-task behavior.

---

## 19. The Capstone can finally choose from the whole toolbox

We now have mechanisms for model contracts, Tool loops, workflows, state, retrieval, protocols, memory, context, Skills, guardrails, evaluation, teams, workspaces, services, and long-horizon execution.

The final chapter should not turn all of them on.

A mature system selects only the mechanisms its domain needs.

Stage 15 builds a support Agent and deliberately practices that restraint.

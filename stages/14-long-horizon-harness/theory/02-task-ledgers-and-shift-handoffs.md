# 02 — Task Ledgers, Crash Recovery, and Shift Handoffs

A task ledger externalizes project progress so a new worker/session can continue from current truth instead of replaying hidden conversation history.

Tiny-Agent intentionally uses a human-readable JSON ledger because the mechanism should be visible before introducing a workflow engine.

---

## 1. Minimal task record

```text
id
description
status
attempts
latest note
artifact paths
```

Tiny-Agent:

```python
@dataclass
class TaskRecord:
    id: str
    description: str
    status: str = "pending"
    attempts: int = 0
    note: str = ""
    artifacts: list[str] = field(default_factory=list)
```

The ledger also stores the run objective and recent notes.

---

## 2. Persist before work

`LongHorizonHarness` marks a task running **before** calling the worker:

```python
task.status = "running"
task.attempts += 1
self.ledger.save(state)

result = await worker(...)
```

Why save first?

If the process dies during work, the persisted state shows that the task was in-flight.

If you save only after completion, a crash leaves no clue whether the task ever started.

---

## 3. Atomic ledger writes

Tiny-Agent writes a temporary file then replaces the ledger:

```python
temporary.write_text(json_text)
temporary.replace(self.path)
```

This reduces the chance that a crash leaves a half-written JSON file.

For multi-worker distributed mutation, a JSON file is insufficient; use a transactional database/workflow backend.

The teaching goal is atomic replacement semantics, not pretending local files are distributed consensus.

---

## 4. Recover persisted `running`

Crash scenario:

```text
persist running
-> worker performs some work
-> process dies before terminal save
```

New process loads:

```text
task.status = running
```

Tiny-Agent explicitly recovers it:

```python
for task in state.tasks:
    if task.status == "running":
        task.status = "pending"
        task.note = "recovered_interrupted_task"
```

The note preserves provenance of the retry.

---

## 5. Recovery restores liveness, not exactly-once execution

The old worker may have completed an external side effect immediately before dying.

```text
send_email()
-> email provider accepts
-> process crashes
-> ledger still says running
-> new worker recovers/retries
```

Potential duplicate email.

Therefore replayable tasks need:

- idempotency keys;
- transactional/outbox patterns;
- downstream deduplication;
- side-effect records;
- approval policies.

`recover_interrupted()` means "this work needs attention again," not "nothing happened."

---

## 6. Handoff summary is a view, not the ledger

Tiny-Agent creates a compact summary:

```python
summary = LongHorizonHarness.handoff_summary(state)
```

Shape:

```text
Objective: ...
Progress: {pending: 3, running: 0, completed: 5, failed: 1}
Recent notes: [...]
Use workspace and ledger as externalized state...
```

The next model receives enough orientation, then reads exact workspace/ledger data when necessary.

Do not make the summary the only source of truth.

---

## 7. Shift handoff analogy

Think of a hospital shift.

Bad handoff:

> Everything is in my head. Good luck.

Also bad:

> Here is a 900-page transcript of every sentence said since admission.

Better:

```text
patient/objective
current status
critical decisions
open tasks
recent events
where exact records live
```

Long-horizon Agent handoffs need the same balance.

---

## 8. Failed is not pending

A failed task may need semantic repair rather than blind retry.

```text
pending
    -> ready for first/explicit retry

failed
    -> attempt produced known failure
    -> may need repair/replan/human decision
```

Do not implement:

```python
for failed_task in tasks:
    retry_forever(failed_task)
```

That is not resilience. It is a small automated tragedy.

---

## 9. Adding tasks dynamically

A worker may discover new work:

```python
HarnessStepResult(
    success=True,
    note="Found two missing evidence checks",
    new_tasks=(
        "check method A evidence",
        "check method B evidence",
    ),
)
```

The harness appends explicit TaskRecords.

Dynamic planning becomes visible/durable rather than existing only in model prose.

---

## 10. Worked resume demo

Session 1:

```text
initialize objective with tasks A/B/C
run max_steps=1
A completed
ledger saved
process object destroyed
```

Session 2:

```text
new AgentWorkspace
new LongHorizonHarness
load same ledger
handoff says A completed, B/C pending
execute B
```

No hidden model history is required.

That is the milestone for this Stage.

---

## Completion principle

> **Persist state transitions before/after work, make interrupted execution visible, treat handoff summaries as derived context, and never confuse crash recovery with exactly-once side effects.**

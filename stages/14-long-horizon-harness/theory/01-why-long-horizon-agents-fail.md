# 01 — Why Long-Horizon Agents Fail

A short Agent loop often assumes:

```text
one process lifetime
one manageable context
one user request
one continuous execution window
```

Hours- or days-long work breaks all four assumptions.

The solution is not to tell the model:

> Please remember everything and keep trying until you are done.

That is not a durability strategy. It is a motivational speech delivered to volatile memory.

---

## 1. Failure source: context grows faster than useful signal

A long task generates:

```text
plans
Tool observations
failed attempts
logs
artifacts
reviews
new subtasks
conversation
```

Replaying everything each session eventually becomes expensive/noisy and may exceed context limits.

Long-horizon architecture therefore externalizes state and loads a compact working set:

```text
durable ledger/artifacts
       ↓
current subtask
+ recent progress
+ relevant files/evidence
+ activated Skills
       ↓
model context
```

Stage 07 context engineering becomes essential rather than optional optimization.

---

## 2. Failure source: process death

Your process can die because of:

- deployment rollout;
- host restart;
- crash/OOM;
- dependency failure;
- worker replacement;
- human stopping/restarting the service.

If progress exists only in Python objects:

```text
process dies
-> project amnesia
```

Durable state must exist **outside** the model/runtime object.

---

## 3. Failure source: environment loss

A sandbox/container may be disposable.

```text
container writes important result only to /tmp
-> container dies
-> result disappears
```

Durable artifacts/workspace state should be promoted outside disposable compute according to policy.

The harness and compute environment should be separable.

---

## 4. Failure source: "done" is a model opinion

A model may confidently announce:

```text
"The project is complete."
```

while tests fail, citations are unsupported, or required tasks remain.

Long-running work needs external completion criteria:

```text
task ledger statuses
tests/evaluators
artifact requirements
human approval
budget/stop policy
```

The model can propose completion. The harness verifies it.

---

## 5. Failure source: retries repeat side effects

Long tasks cross many failure boundaries.

```text
write external record
-> process dies before recording completion
-> new worker retries
```

Recovery can re-execute work.

Therefore:

```text
resume/retry
!= exactly once
```

Use Stage 09/10 idempotency, transactions, deduplication, and approval rules for side effects.

---

## 6. Failure source: one giant plan becomes stale

A 40-step plan created at minute 1 may be wrong by step 8 because the environment taught the Agent something new.

Better:

```text
stable objective
-> bounded near-term tasks
-> execute/evaluate
-> update task ledger
-> replan/repair when evidence changes
```

Long-horizon control is iterative project management, not prophecy.

---

## 7. Failure source: session handoff loses critical state

A new model session needs enough information to continue, but not the full transcript.

Bad handoff:

```text
"Continue where we left off."
```

New session:

```text
where exactly is "where"?
```

Better handoff contains:

```text
objective
current/pending tasks
recent decisions
artifact paths
blocking failures
next recommended action
```

Exact structured state remains in ledger/workspace; handoff is a compact derived view.

---

## 8. Long-horizon architecture

```text
objective
   ↓
initializer/planner
   ↓
TaskLedger + durable workspace
   ↓
worker session
   ↓
execute one/few bounded tasks
   ↓
artifacts + notes + evaluation
   ↓
persist
   ↓
new worker/session if needed
```

The model is replaceable. The project state is not.

---

## 9. Worked example: 30-paper review

Naive:

```text
one chat session
-> read papers
-> accumulate notes in conversation
-> context fills
-> summary loses details
-> process restarts
-> no reliable source of progress
```

Harnessed:

```text
TaskLedger:
  task-1 search corpus       completed
  task-2 extract paper A    completed
  task-3 extract paper B    running
  ...

Workspace:
  evidence/paper-a.md
  evidence/paper-b.md
  synthesis/matrix.csv

Next session:
  load objective + pending task + relevant artifacts
```

This is how an Agent becomes a durable worker rather than a very long conversation.

---

## 10. What long-horizon does not mean

It does not necessarily mean:

```text
more autonomy
more Agents
more model calls
```

Sometimes the best long-horizon harness is mostly deterministic workflow with a few semantic worker steps.

Use the least dynamic system that can make reliable progress.

---

## Completion principle

> **Long-horizon reliability comes from externalized progress, artifacts, evaluation, resumable state, and bounded worker sessions—not from making one model context immortal.**

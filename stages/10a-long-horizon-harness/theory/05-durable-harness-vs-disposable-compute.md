# 05 — Durable harness vs disposable compute

A robust architecture separates what must survive from what can be recreated.

```text
DURABLE
run/job record
checkpoint
task ledger
memory policy state
artifact metadata
workspace snapshot
approvals/audit references

DISPOSABLE
model request
worker process
sandbox/container
temporary caches
```

## Service-level jobs

Stage 10's `SQLiteRunQueue` demonstrates durable enqueue + worker lease semantics:

```text
queued
-> atomic claim
-> running with lease
-> completed/failed
```

If a worker disappears and its lease expires, another worker can claim the run. Production systems often implement the same idea with Postgres, queues, or workflow engines.

## Agent-level task ledger

Inside one logical run, `TaskLedger` tracks sub-work.

Do not confuse:

```text
service job ownership
with
Agent plan/task state
```

A single durable service job may contain dozens of Agent tasks/checkpoints.

## Rehydration

When compute disappears:

```text
new worker/sandbox
-> load durable run
-> restore allowed workspace
-> load task/checkpoint state
-> rebuild minimal context
-> continue
```

This is the long-horizon version of Stage 03/06 checkpoint-resume, extended to workspaces and external compute.

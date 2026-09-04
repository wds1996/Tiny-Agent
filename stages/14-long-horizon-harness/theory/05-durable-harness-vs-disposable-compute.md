# 05 — Durable Harness vs Disposable Compute

A long-horizon Agent becomes easier to reason about when we separate two lifetimes:

```text
durable control state
        vs
disposable execution environment
```

The harness should be able to outlive any particular sandbox, model call, HTTP connection, or worker process.

---

## 1. Durable harness state

Examples:

```text
run/job identity and owner
objective
TaskLedger
thread/checkpoint
approval state
artifact metadata
progress notes
budget usage
external task handles
```

These are continuity/control-plane state.

Losing them may violate the product promise that work can resume.

---

## 2. Disposable compute state

Examples:

```text
container process
/tmp files
package caches
one notebook kernel
one shell session
one model call
```

These can often be recreated.

Important artifacts should be copied/written to governed durable storage before the environment is discarded.

---

## 3. Why separation improves security

If the sandbox does not own the run database/model master credential, compromising generated code has a smaller blast radius.

Architecture:

```text
Harness/service
  owns identity, leases, credentials, policy
        |
        | narrow execution request
        v
Sandbox
  owns task-scoped files/compute only
        |
        | result/artifact
        v
Harness validates/promotes
```

This is stronger than putting the entire application inside the same environment as untrusted generated code.

---

## 4. Why separation improves durability

```text
sandbox dies
-> harness still knows task was running
-> recover_interrupted / lease expiry
-> start new sandbox
-> mount/load artifacts
-> retry/repair
```

If harness state died with the sandbox, there would be nothing reliable to resume from.

---

## 5. Service run, Agent thread, task ledger, sandbox

A complete long-horizon deployment may contain:

```text
run_id
  = product/service job ownership

thread_id/checkpoint
  = orchestration resume position

TaskLedger
  = project/subtask progress

sandbox_id
  = temporary compute instance
```

These IDs may be correlated but should not be treated as the same abstraction.

One run can use many sandbox instances over time.

---

## 6. Rehydration

Rehydrating compute means reconstructing enough environment to continue:

```text
approved base image
+ code version
+ dependency manifest
+ workspace/artifact mount
+ task-scoped config/credentials
+ pending task
```

The closer this is to reproducible configuration, the easier crash recovery becomes.

If the only record of environment state is "the old container had some packages installed manually," recovery becomes software archaeology.

---

## 7. Durable queues and TaskLedger solve different levels

Stage 13 `SQLiteRunQueue`:

```text
Which worker owns run-42?
```

Stage 14 `TaskLedger`:

```text
Inside run-42, which research/coding tasks are complete?
```

A worker may claim run-42, load its ledger, execute one pending task in a new sandbox, save artifacts, and release/complete the run according to the service contract.

---

## 8. Worked architecture

```text
POST /runs
-> authenticate tenant/user
-> durable run-42 queued

worker-B claims lease
-> load thread checkpoint + TaskLedger
-> pending task: "analyze dataset"
-> create constrained sandbox-9
-> run analysis
-> save result.csv to durable workspace
-> evaluator validates
-> TaskLedger marks task complete
-> checkpoint next phase
-> destroy sandbox-9

later:
worker-C claims/resumes
-> new sandbox-10 for next task
```

The project survives multiple processes and compute environments.

---

## 9. What should be durable?

Not everything.

Durability has cost and privacy implications.

Ask:

```text
Would losing this violate correctness/resume promise?
Can it be recomputed cheaply?
Does it contain sensitive data?
How long is retention required?
```

A package cache may be disposable. An approved final report is not.

---

## 10. Final mental model

```text
Durable control plane
  identity / job / checkpoint / ledger / artifact metadata
               |
               v
Disposable data/compute plane
  sandbox / processes / temporary caches
               |
               v
Governed artifacts + evaluator feedback
               |
               +----> durable control plane continues
```

> **Long-horizon Agent durability comes from making compute replaceable while preserving the minimum external state needed to continue correctly and securely.**

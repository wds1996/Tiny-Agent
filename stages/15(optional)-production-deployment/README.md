# Stage 15 (Optional): The Local Demo Was the Easy Part — Turning an Agent into a Production Service

> Language: **English** | [简体中文](README.zh-CN.md)

[Stage 14](../14-capstone-enterprise-agent/README.md) completed the core Agent learning path. This optional chapter is for the moment you need to expose that Agent to multiple users as a long-lived service. A production service must receive many requests, survive restarts, limit demand fairly, and let clients find work after the original HTTP connection has gone away.

This chapter builds a small, framework-independent service core with SQLite. It deliberately does **not** claim that a `python demo.py` program is a deployed web service. Instead, it establishes the service semantics that an HTTP framework, queue consumer, or CLI must preserve.

---

## 1. Start by separating the identities and lifetimes

The names below are easy to blur together, yet they answer different questions:

| Name | Meaning | Typical lifetime |
| --- | --- | --- |
| Request | One protocol interaction, such as `POST /runs` | Milliseconds or seconds |
| Run | One durable Agent execution | Seconds, minutes, or longer |
| Thread | A continuing conversation or task context shared by runs | Multiple runs |
| User | The authenticated end user | Account lifetime |
| Tenant | The organization or customer isolation boundary | Organization lifetime |

The Request submits work. The Run owns that work after the Request ends:

```text
POST /runs
    → create durable run
    → return accepted + run_id

GET /runs/{run_id}
    → queued / running / completed / failed
```

The identity for a Run must come from a trusted authentication boundary, not from ordinary request data. The service core represents that fact with a separate value:

```python
from service import TrustedIdentity

identity = TrustedIdentity(user_id="alice", tenant_id="acme")
```

An untrusted message may contain the text `{"tenant_id":"evil"}`, but it is still only task input. A real HTTP adapter verifies a session, token, or mTLS identity first, then passes the resulting `TrustedIdentity` to `AgentService`. It must never promote a `tenant_id` claim in JSON into ownership.

## 2. Submission is a durable operation, not a long HTTP wait

An Agent may retrieve documents, call MCP tools, wait for approval, or create artifacts. Holding the original HTTP connection open for all of that makes retries, load balancing, and restarts harder. Submission should create a durable `queued` Run and return its ID; a Worker later claims it.

The complete local example below also shows two service rules that matter immediately:

- **Backpressure:** each Tenant may have only a bounded number of queued Runs.
- **Idempotency:** retrying the same submission returns the original Run instead of creating another one.

```python
from pathlib import Path
import tempfile

from service import AgentService, RunStore, TrustedIdentity

with tempfile.TemporaryDirectory() as tmp:
    service = AgentService(
        RunStore(Path(tmp) / "runs.db"),
        max_queued_per_tenant=2,
    )
    identity = TrustedIdentity(user_id="alice", tenant_id="acme")

    first = service.submit(
        identity=identity,
        thread_id="support-42",
        input_text="Summarize ORDER-42.",
        idempotency_key="request-123",
    )
    retry = service.submit(
        identity=identity,
        thread_id="support-42",
        input_text="Summarize ORDER-42.",
        idempotency_key="request-123",
    )

    assert first.run_id == retry.run_id
    print(first.status)  # queued
```

An idempotency key means “this is a retry of the same requested operation,” not merely “reuse a convenient string.” The teaching store scopes it by `(tenant_id, idempotency_key)` so different Tenants can both use `request-123`. It also rejects reuse of the same key with a different user, Thread, or input. Production systems often store a request-body hash rather than the full input for this comparison.

Submission idempotency is not the idempotency of tools inside the Run. Stage 09's payment or email tool still needs its own idempotency key: one boundary prevents duplicate Runs; the other prevents duplicate side effects.

## 3. A queue needs an owner, a limit, and durable state

Once submission and execution are separate, work may arrive faster than Workers consume it. Accepting unlimited work only moves failure from the HTTP handler into memory, database storage, third-party quotas, and user waiting time.

`max_queued_per_tenant` makes that limit explicit. When a Tenant fills its queue, `AgentService.submit()` raises `BackpressureError`. A second Tenant can still submit work; this is the smallest useful step toward fairness. A real scheduler may additionally apply global capacity, weights, priorities, and rate limits, but every such budget needs a scope.

Run records must also outlive the `AgentService` Python object. This chapter uses SQLite through Python's standard-library [`sqlite3`](https://docs.python.org/3/library/sqlite3.html) module. Its table retains the Run ID, Thread, authenticated User and Tenant, status, input/output, idempotency key, and timestamps. SQLite is a compact teaching store; moving to Postgres or another durable store must preserve the same semantics.

The distinction is:

```text
in-memory dictionary disappears when the process exits
durable Run record remains available after service recreation
```

This is related to Stage 06 Checkpoints but not identical. A Checkpoint saves enough runtime state to resume work. A Run record is the service-visible lifecycle and ownership record. Stage 13 connects both ideas for long-running work.

## 4. Claiming a Run is a state transition and a concurrency operation

The teaching state machine is intentionally small:

```text
queued → running → completed
```

A Worker must not casually `SELECT` a queued row, do unrelated work, and later update it. Two Workers could select the same row. `RunStore.claim_next()` begins an SQLite `BEGIN IMMEDIATE` transaction, selects one queued row, and changes it to `running` before committing. The transaction makes selection and claim one protected operation for this SQLite example.

Completion has an equally important precondition: only a Run that is currently `running` may become `completed`. Calling `complete()` on a queued or already completed Run raises `InvalidRunTransitionError`. This prevents a stale Worker from silently overwriting the lifecycle.

`BEGIN IMMEDIATE` is a teaching-level local concurrency boundary, not a complete distributed Worker lease. If a Worker dies after claiming a Run, the record remains `running`; Stage 13 introduces leases, heartbeats, and recovery for that situation.

## 5. Keep the HTTP adapter thin and make health meaningful

The code in this chapter is a service core, so it has no pretend authentication middleware or toy FastAPI server that treats an unverified header as trusted. In a real application, the HTTP layer should do protocol work and then call the core:

```text
HTTP / API adapter
    → verify credentials and create TrustedIdentity
    → validate request size, shape, and deadline
    → AgentService.submit() or RunStore.get()

AgentService / RunStore
    → durable submission, ownership checks, queue limits

Worker
    → claim Run, invoke bounded Agent runtime, persist result
```

This separation keeps the same service core usable from REST, a queue consumer, a CLI, or another protocol. It also makes Tenant ownership part of every lookup: `RunStore.get()` queries with both `run_id` and the authenticated `tenant_id`. A caller from another Tenant receives “not found,” without learning whether the Run exists.

Health endpoints need the same honesty. **Liveness** asks whether the process is alive. **Readiness** asks whether it can currently serve traffic. A process can be live while its durable store is unavailable. `store.ready()` performs a small database query, so a failed dependency can make readiness false instead of returning an unconditional `{ "status": "ok" }`.

## 6. “Async”, shutdown, configuration, and the real runtime

Two meanings of “asynchronous” are often mixed up:

```text
Python async def
    → a concurrency programming model

durable asynchronous job
    → work continues after the submitting Request has ended
```

An `async def` endpoint may still hold a connection for the entire task. A synchronous Worker can process a durable queued job. The durable Run boundary is what matters here.

During deployment, a terminating process should stop accepting new work, become not-ready, finish or safely suspend bounded work, persist recoverable state, and then exit. The teaching service does not implement signal handling because Worker-loss recovery is covered in Stage 13, but shutdown must be designed as part of the runtime lifecycle.

Configuration and credentials also come from the deployment boundary. Keep them outside prompts and pass each secret only to the component that needs it. Stage 12 already demonstrated why child processes should not inherit an entire environment by default.

Finally, `run_one()` returns a deterministic string rather than calling a DeepSeek model. That is deliberate: this chapter tests service ownership, retries, and durable state without turning a model response into a source of nondeterministic test failures. In a production system, the marked Worker step invokes the bounded Agent runtime developed in earlier stages, including its model, tools, guardrails, and Workspace/Sandbox boundary.

## 7. Run the complete service-core demonstration

Run each command from the repository root:

```bash
python stages/15(optional)-production-deployment/code/demo.py
python stages/15(optional)-production-deployment/code/checks.py
```

The demo submits a Run, repeats the submission with the same idempotency key, claims and completes it, recreates the service, and reads the completed record from the same SQLite file. The checks cover trusted identity, Tenant-scoped lookup and idempotency, mismatch rejection for reused keys, per-Tenant backpressure, durable restart, valid state transitions, and readiness.

## 8. Where this elective fits

The queue makes a Run independent of its HTTP Request, but it does not recover a Run that was claimed by a Worker that disappeared. For that mechanism, revisit [Stage 13: Long-Horizon Harness](../13-long-horizon-harness/README.md), which adds a ledger, leases, heartbeats, and resumable execution.

Use this elective when your Agent crosses the boundary from a local or internal tool into a multi-user production service. It is useful engineering, but it is not a prerequisite for understanding the Agent mechanisms in Stages 00–14.

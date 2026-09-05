# Stage 13: The Local Demo Was the Easy Part — Turning an Agent into a Production Service

> Language: **English** | [简体中文](README.zh-CN.md)

By Stage 12, the Agent program has durable state, external capabilities, memory, context, Skills, guardrails, evaluation, and a bounded workspace.

Then someone says: “Great. Ship it tomorrow.”

A program that works locally is not yet a service that can handle real users over time.

Stage 13 focuses on service semantics rather than a web-framework API:

```text
What is a request?
What is a run?
Where does identity come from?
How are long jobs submitted?
What happens when the queue is full?
How is status recovered after restart?
What if the client retries submission?
When is the service actually ready?
```

---

## 1. Request, Run, Thread, User, and Tenant have different scopes

An HTTP request may live for milliseconds. A Run may live for minutes or hours. A Thread groups continuing task or conversation context. A User identifies the end user. A Tenant is an isolation boundary for data and resources.

Do not reuse one ID for every scope simply because it is convenient.

---

## 2. Identity should not come from an untrusted request body

A dangerous API accepts `tenant_id` and `user_id` from ordinary business input and trusts them.

The service should instead receive a `TrustedIdentity` established by an authentication boundary.

The request body supplies task data. The service boundary establishes who owns that task.

```text
payload claim != trusted identity
```

---

## 3. Long Agent runs should not require one long HTTP connection

A common service shape is:

```text
POST /runs
    ↓
create durable run
    ↓
return run_id

GET /runs/{run_id}
    ↓
queued / running / completed / failed
```

The request submits work. The Run owns the work lifecycle.

This separation becomes even more important for approval waits and long tasks.

---

## 4. A queue creates backpressure requirements

Once submission and execution are separated, work can arrive faster than workers consume it.

Accepting unlimited work is not resilience.

The teaching service sets `max_queued_per_tenant` and raises `BackpressureError` when a tenant has filled its queue.

A service should be able to say “not now” before it collapses.

---

## 5. Resource limits need scope

A single noisy tenant should not necessarily consume every queue slot.

The chapter applies the teaching limit per tenant.

Real systems may add fair scheduling and weighted quotas. The important design move is to make resource ownership explicit.

---

## 6. Submission needs idempotency

A server may create a Run successfully while the response is lost. The client retries.

Without submission idempotency, one user action creates two Runs.

The store uses a tenant-scoped idempotency key so the retry returns the original Run.

---

## 7. Request idempotency and Tool idempotency are different

Request idempotency prevents duplicate Runs.

Tool idempotency prevents duplicate side effects inside a Run.

One does not automatically provide the other. Every retry boundary needs its own semantics.

---

## 8. Run status belongs in durable storage

An in-memory `runs = {}` dictionary forgets everything on restart.

The teaching SQLite table stores run, thread, user, tenant, status, input, output, and timestamps.

SQLite is not presented as the only production database. It simply makes the durability invariant executable.

---

## 9. Claiming work is a concurrency operation

The worker changes a Run from `queued` to `running`.

Selecting and updating must not allow two workers to claim the same row casually.

The teaching store uses a transaction to make that boundary visible.

Stage 14 will extend this into leases and worker-loss recovery.

---

## 10. Tenant identity belongs in lookup queries

Looking up a Run only by `run_id` can cross tenant boundaries.

The store queries by both `run_id` and `tenant_id`.

Unauthorized callers observe “not found” rather than learning that another tenant's Run exists.

---

## 11. Liveness and readiness ask different questions

Liveness asks whether the process is alive.

Readiness asks whether it can currently serve traffic.

A live process with a broken durable store should not advertise readiness.

The teaching readiness check queries the store.

---

## 12. Keep the HTTP boundary thin

A healthy layering is:

```text
HTTP / protocol
    ↓
trusted identity + request parsing
AgentService
    ↓
RunStore / queue
    ↓
Worker
    ↓
bounded Agent Runtime
```

Do not copy the Agent architecture into every endpoint handler.

A thin protocol boundary makes it easier to expose the same runtime through REST, a queue, CLI, or another protocol later.

---

## 13. Durable asynchronous work is not the same as `async def`

Python async is a concurrency programming model.

A durable asynchronous job means work can continue beyond the request lifecycle.

A synchronous worker can process a durable queued job. An `async def` endpoint can still hold one request open for the entire job.

Do not confuse the two meanings of “async.”

---

## 14. Graceful shutdown belongs to service lifecycle

A process receiving a termination signal should normally stop taking new work, become not-ready, finish or safely suspend bounded work, persist recoverable state, and exit.

Long-horizon recovery comes next, but shutdown cannot be treated as an afterthought.

---

## 15. Configuration and secrets are service concerns

Deployment configuration and credentials should come from trusted deployment boundaries and be supplied only to components that need them.

Do not encode production secrets in prompts or forward every environment variable into Agent subprocesses.

---

## 16. The teaching worker is intentionally boring

`run_one()` produces a deterministic output instead of reimplementing an Agent.

In a real application, that line would call the bounded runtime built in earlier stages.

This chapter is about service lifecycle, not another miniature Agent loop.

---

## 17. Run the chapter

```bash
python stages/13-production-deployment/code/demo.py
python stages/13-production-deployment/code/checks.py
```

The checks cover trusted identity, idempotent submission, tenant-scoped idempotency, per-tenant backpressure, cross-tenant lookup, restart durability, status transitions, and readiness.

---

## 18. Why the long-horizon harness comes next

A queued Run can outlive the HTTP request, but a worker can still disappear after claiming it.

Who recovers the task? How is progress saved? How is a workspace re-created? How do two workers avoid owning the same task?

Stage 14 adds a task ledger, leases, heartbeats, durable work units, and resumable long-horizon execution.

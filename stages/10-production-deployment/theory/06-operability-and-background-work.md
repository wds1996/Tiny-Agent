# 06 — Health, graceful shutdown, jobs, and operations

## Liveness vs readiness

### Liveness

> Is the process alive enough that restarting it might help if this fails?

`/livez` should usually be cheap and not depend on every downstream system.

If liveness checks Postgres and Postgres has a 30-second outage, restarting every healthy application process creates a second incident.

### Readiness

> Should this instance receive new traffic right now?

Readiness may check critical dependencies such as Postgres/Redis if the service cannot operate without them.

Stage 10 runs readiness checks concurrently with a timeout and reports only exception type, not raw exception text.

## Graceful shutdown

A deployment sends termination.

The service should ideally:

1. stop receiving new work;
2. let accepted work finish within a grace period;
3. cancel/mark recoverable work according to contract;
4. close pools and clients;
5. flush telemetry;
6. exit.

If shutdown simply kills a process while a Tool performs a side effect, Stage 07 idempotency rules become extremely important on retry.

## Long Agent work

For a 300 ms request, request/response can be fine.

For a 20-minute research task, keeping one HTTP connection open may be a poor contract.

Prefer a durable job model:

```text
POST /runs -> 202 + run_id
worker executes durable record
GET /runs/{id}
stream/poll/webhook for updates
```

The task record must survive process restart if the product promises resumability.

## Why `BackgroundTasks` is not that architecture

A framework background callback runs in/around the web process lifecycle. It does not automatically provide:

- durable enqueue;
- retry policy;
- ownership leases;
- dead-letter handling;
- multi-worker coordination;
- crash recovery.

Use it for small best-effort post-response work, not promises that must survive crashes.

## Structured logs and traces

Stage 08 remains the observability foundation.

Production adds correlation dimensions:

```text
request_id
run_id
thread_id
user/tenant id (privacy-governed)
trace_id
instance/worker identity
```

Do not log whole prompts/tool outputs by default merely because a centralized log platform exists.

## Readiness is not monitoring

A probe answers a narrow machine question now.

Monitoring/alerting asks questions over time:

```text
error rate?
p95 latency?
queue saturation?
model cost?
timeout ratio?
Redis/Postgres pool pressure?
```

Keep these concepts separate.

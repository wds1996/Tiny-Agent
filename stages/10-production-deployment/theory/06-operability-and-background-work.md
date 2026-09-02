# 06 — Health, Graceful Shutdown, Durable Jobs, Metrics, and Operations

A production Agent is not complete when it answers one request. It must remain understandable when dependencies fail, workers restart, queues fill, deployments roll, and a 20-minute task reaches minute 19.

Operations is where "works on my laptop" meets its performance review.

---

## 1. Liveness vs readiness

### Liveness

> Is the process alive enough that restarting it might help if this check fails?

Keep it cheap and mostly local.

### Readiness

> Should this instance receive new traffic right now?

Readiness may depend on critical services such as Postgres if the application cannot function without them.

If liveness fails whenever Postgres is briefly down, orchestration may restart every healthy app instance during a database incident—an impressive way to create bonus problems.

---

## 2. Readiness is a current state, not monitoring

A readiness probe answers:

```text
can this instance serve now?
```

Monitoring asks over time:

```text
error rate?
p95/p99 latency?
queue saturation?
timeout ratio?
provider failures?
cost per successful run?
DB/Redis pool pressure?
```

A green `/readyz` does not mean users are happy.

---

## 3. Golden operational signals for Agent services

Useful metrics include:

```text
request rate
success/failure/abstention rate
p50/p95/p99 latency
queue/admission wait
in-flight / peak in-flight
model calls/tokens/cost
Tool failure/retry rate
durable job queue depth/age
HITL waiting count/time
checkpoint/resume failures
```

Stage 08 provides evaluation/tracing. Stage 10 adds service saturation and infrastructure dimensions.

---

## 4. Graceful shutdown

Desired sequence:

```text
1. mark not ready / stop new work
2. drain accepted short requests within grace period
3. persist/requeue long work according to contract
4. close worker leases safely
5. flush telemetry
6. close Redis/Postgres/provider clients
7. exit
```

If shutdown kills a process in the middle of a side effect, retries must respect Stage 07 idempotency semantics.

---

## 5. Short request vs durable job

A 300 ms Agent call can use normal request/response.

A 20-minute research task may outlive:

- browser connection;
- reverse proxy timeout;
- deployment rollout;
- web worker;
- sandbox instance.

Prefer:

```text
POST /runs
  -> validate/auth
  -> durable enqueue
  -> 202 Accepted + run_id

worker claims run
  -> executes/resumes

GET /runs/{id}
  -> status/result

optional stream/webhook
  -> progress view
```

The durable record is the contract. The HTTP connection is only one observation channel.

---

## 6. Why BackgroundTasks is not that architecture

Framework background callbacks do not automatically provide:

- durable enqueue;
- retry/repair policy;
- ownership leases;
- crash recovery;
- multi-worker coordination;
- dead-letter/manual intervention;
- cancellation semantics.

Use them for small best-effort post-response work.

Do not promise users "we are processing your 2-hour job" when the promise lives only in RAM next to the process that will be replaced during deployment.

---

## 7. Job status is a state machine

Useful states may include:

```text
queued
running
waiting_for_human
waiting_for_external_task
completed
failed
cancelled
```

Tiny-Agent's teaching `SQLiteRunQueue` uses a simpler subset, while Stage 10A's `TaskLedger` models sub-work inside a run.

Production state machines should make ambiguity visible rather than representing everything as `done: bool`.

---

## 8. Correlation across layers

Useful identifiers:

```text
request_id
run_id
thread_id
trace_id
authenticated tenant/subject (privacy-governed)
worker/instance id
external MCP/A2A task id
```

Logging should let you reconstruct a trajectory without dumping every prompt, secret, and document into centralized logs.

Observability can create its own data breach if "debug everything" becomes the default retention policy.

---

## 9. SLO thinking

A service-level objective might be:

```text
99% of accepted interactive runs complete within 20s
99.9% of durable runs never lose acknowledged work
<1% timeout rate
```

These objectives influence architecture:

- admission limits;
- queue durability;
- retries;
- replicas;
- provider fallbacks;
- timeout budgets.

"Fast" and "reliable" are not executable requirements until quantified.

---

## 10. Alert on user-impacting symptoms

Good alerts often derive from:

```text
sustained error/timeout rate
queue age/depth
readiness capacity collapse
provider failure rate
DB pool exhaustion
job lease churn
```

Avoid paging humans because one dependency had one transient error.

The goal is actionable detection, not creating a 24/7 notification-themed multi-Agent system for the on-call engineer.

---

## 11. Worked deployment failure

```text
new version rollout
-> old worker is running research job
-> SIGTERM arrives
```

Bad:

```text
kill process
-> job disappears
-> client still has run_id but no state
```

Better:

```text
run record exists durably
-> worker stops renewing lease / persists checkpoint
-> another worker reclaims after lease expiry
-> Agent resumes from checkpoint/task ledger
```

External side effects still require idempotency because the exact crash point may be ambiguous.

---

## Completion principle

> **Operate Agent runs as explicit state machines with bounded resources, observable saturation, durable promises, and graceful failure/recovery semantics.**

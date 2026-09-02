# 03 — PostgreSQL, Redis, and State Responsibilities

Infrastructure names do not define semantics.

Adding a green Redis box and a blue PostgreSQL cylinder to an architecture diagram does not cause state consistency to emerge from the pixels.

Start from the responsibility.

---

## 1. Recall Stage 06 semantics

```text
Checkpointer
    = durable execution/thread state

Store
    = selected cross-thread long-term memory
```

Stage 10 asks where those abstractions live in deployed infrastructure, together with jobs, ownership, audit records, caches, and coordination.

---

## 2. PostgreSQL: durable transactional truth

Good fits include:

- run/job records;
- thread/checkpoint backends;
- long-term memory Store;
- user/tenant ownership metadata;
- audit references;
- transactional state transitions;
- idempotency records;
- durable task/result metadata.

Why relational transactions matter:

```text
update job status
+ insert audit record
+ record result pointer
```

may need to succeed/fail as one logical unit.

Do not split correctness-critical state across systems casually just because each technology has a mascot.

---

## 3. Redis: fast shared ephemeral coordination

Useful for:

- distributed rate counters;
- cache entries with TTL/invalidation policy;
- ephemeral leases/locks with carefully defined semantics;
- short-lived coordination;
- queues/streams when delivery semantics fit the contract.

Ask:

> If Redis loses this data, has the product contract been violated?

If yes, decide whether Redis persistence/replication semantics are sufficient or whether durable truth belongs elsewhere.

`cache` and `source of truth` are not synonyms.

---

## 4. In-memory state breaks across workers

```python
sessions[thread_id] = state
```

works in one process.

With multiple workers:

```text
request 1 -> worker A -> stores state in A memory
request 2 -> worker B -> B dictionary is empty
```

This is not a mysterious race condition. The workers are literally different processes.

Externalizing shared state follows from deployment topology.

---

## 5. Connection pools are resource budgets

Opening a database TCP connection per Agent step is slow and can exhaust PostgreSQL.

Use bounded pools.

Conceptual async lifecycle:

```python
pool = AsyncConnectionPool(dsn, open=False, min_size=1, max_size=10)
await pool.open()
await pool.wait()

# serve requests

await pool.close()
```

Pool size multiplies by replicas:

```text
12 replicas × max_size 15
= up to ~180 application connections
```

before workers, migrations, admin tools, and other services.

"max_size=100 feels generous" is not capacity planning.

---

## 6. Transactions and Agent side effects

Agent orchestration often spans external systems, so one Postgres transaction cannot magically make an email API or payment provider transactional.

Useful patterns include:

```text
idempotency key
outbox/event record
state machine transition
reconciliation job
```

Example:

```text
transaction:
  insert email_intent(idempotency_key)
  mark Agent task awaiting_delivery
commit

worker sends email using key
records delivered
```

The exact pattern depends on external API semantics. The important lesson is not to equate "database transaction" with "distributed exactly once."

---

## 7. Redis fixed-window limiter example

Tiny-Agent uses a small Lua script so increment + first expiry are atomic conceptually:

```text
count = INCR key
if count == 1:
    EXPIRE key window
```

Identity is hashed before being embedded in the Redis key.

This teaches distributed counting, not the world's final rate limiter.

Production might need:

- token bucket;
- sliding window;
- tenant-specific quotas;
- gateway enforcement;
- burst policy;
- provider quota coordination.

---

## 8. Fail-open vs fail-closed

If Redis is down, should rate limiting fail?

```text
fail-open
    -> favor availability
    -> requests continue without quota enforcement

fail-closed
    -> favor protection/quota correctness
    -> deny while limiter unavailable
```

No universal answer.

For a low-risk public demo, availability may win. For a costly or abuse-sensitive operation, fail-closed may be appropriate.

Make the choice explicit and observable.

---

## 9. Cache invalidation and Agent context

Suppose a Tool catalog or user memory is cached.

Questions:

```text
What is the cache key namespace?
Tenant included?
How long is TTL?
What invalidates it?
Can stale permissions be served?
Can stale memory affect decisions?
```

Do not cache authorization results indefinitely. "Fast but wrong tenant" is not a performance optimization.

---

## 10. Worked state map

A production research Agent might use:

```text
Postgres
  runs
  thread checkpoints
  artifact metadata/ownership
  durable preferences

Redis
  tenant rate counters
  short-lived cache
  worker coordination

Object storage
  PDFs / generated artifacts

Model context
  selected slices only
```

Each system has a reason, not just a logo.

---

## Completion checklist

You should be able to answer:

- Which data is durable truth?
- Which state is ephemeral coordination/cache?
- Which operations require transactions?
- What happens if Redis disappears?
- How many DB connections exist across replicas?
- What cache keys include tenant/owner scope?
- Which state lives outside model context?

The invariant:

> **Choose infrastructure from state semantics and failure requirements; do not let infrastructure names replace the semantics.**

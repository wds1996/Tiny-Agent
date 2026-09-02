# 03 — PostgreSQL, Redis, and state responsibilities

## Infrastructure technology does not define semantics

Stage 06 already established:

```text
Checkpointer = durable execution-thread state
Store        = selected cross-thread memory
```

Stage 10 adds deployment infrastructure without erasing those semantics.

## PostgreSQL

Good fits include:

- durable run/task metadata;
- checkpoints and long-term Store backends;
- user/tenant-owned records;
- audit references;
- transactional state transitions;
- job/task records that must survive restart.

Postgres is durable state, not “something we ping because production diagrams need a cylinder.”

## Redis

Good fits include:

- distributed rate counters;
- short-lived locks/leases when carefully designed;
- ephemeral coordination;
- cache data with explicit invalidation/TTL policy;
- queues/streams when their delivery semantics match the application.

Redis should not silently become the source of truth for data whose loss would violate your product contract.

## Why in-memory state breaks under workers

Suppose worker A stores:

```python
sessions[thread_id] = state
```

The next HTTP request may hit worker B:

```text
worker A memory: has state
worker B memory: empty
```

This bug often hides locally because you ran one process.

Externalizing shared/durable state is therefore not “microservice ceremony”; it is required by the deployment topology.

## Connection pools

Opening a new Postgres TCP connection for every Agent step is expensive and can exhaust the database.

Use a bounded pool.

Current Psycopg guidance for async pools is explicit lifecycle management:

```python
pool = AsyncConnectionPool(..., open=False)
await pool.open()
await pool.wait()
...
await pool.close()
```

Stage 10 wraps this pattern in `PostgresPool`.

## Pool size is multiplied by replicas

If:

```text
10 app replicas
max_size = 20 connections each
```

then the database may see up to roughly:

```text
200 app connections
```

before counting migrations, admin tools, workers, or other services.

“Works on one laptop” is not a pool-sizing strategy.

## Redis rate limiter example

The stage uses one Lua script so increment + first-window expiry happen atomically:

```text
INCR key
if first -> EXPIRE key
```

It hashes caller identity before storing the Redis key.

This is still deliberately a basic fixed-window algorithm. Production quotas may need token bucket/sliding window, gateway integration, tenant-specific policy, and failure-mode decisions.

## What if Redis is down?

You must decide whether a limiter is:

```text
fail-open  -> availability favored
fail-closed -> quota/security favored
```

There is no universal answer. The correct choice is part of product/security policy.

# Stage 10 — Production Service, Identity, Durable Jobs & Deployment

A local Agent that works once is not yet a service. Production introduces callers, identities, queues, deadlines, process restarts, external state, health probes, deployment topology, and operational contracts.

The key progression is:

```text
local Agent call
    ↓
thin service boundary
    ↓
trusted authentication / tenant binding
    ↓
capacity admission + deadlines
    ↓
HTTP / SSE
    ↓
durable jobs for long work
    ↓
Postgres / Redis lifecycle
    ↓
health / graceful shutdown
    ↓
container / network deployment
    ↓
A2A service boundary
```

> A Dockerfile packages your architecture. It does not repair it.

## Learning objectives

By the end of Stage 10 you should be able to explain and implement:

1. thin HTTP adapters around domain/runtime logic;
2. request ID vs run ID vs thread ID vs authenticated subject/tenant;
3. why body-level `user_id` is not authentication;
4. trusted principal binding and resource ownership checks;
5. process-local concurrency vs distributed rate limits;
6. queue timeout and execution deadline;
7. why timeout does not hard-kill a synchronous worker thread;
8. SSE streaming and post-header error events;
9. liveness vs readiness;
10. PostgreSQL vs Redis responsibilities;
11. explicit async connection-pool lifecycle;
12. configuration vs secret management;
13. worker/replica multiplication of memory/pools/concurrency;
14. graceful shutdown/draining;
15. why FastAPI BackgroundTasks are not a durable queue;
16. durable enqueue, atomic worker claim, leases, and crash recovery;
17. how long-running HTTP work becomes `202 + run_id` style jobs;
18. Docker/Compose responsibilities and limitations;
19. A2A hosting as a real network boundary;
20. what CI can and cannot prove.

## Learning order

### Service boundary

1. `theory/01-service-boundaries-and-identities.md`
2. `code/service_boundary.py`
3. `code/fastapi_in_process.py`
4. `theory/02-async-concurrency-streaming.md`
5. `code/streaming_sse.py`

### Infrastructure and lifecycle

6. `theory/03-postgres-redis-and-state.md`
7. `theory/04-config-secrets-lifecycle.md`
8. `code/postgres_pool.py`
9. `code/redis_rate_limit.py`
10. `code/lifespan_resources.py`

### Deployment and operations

11. `theory/05-containers-workers-deployment.md`
12. `theory/06-operability-and-background-work.md`
13. `code/health_readiness.py`
14. `theory/07-a2a-network-service.md`
15. `code/a2a_http_server.py`

### New production boundary: identity + durable jobs

16. `theory/08-authentication-tenancy-and-durable-jobs.md`
17. `code/authenticated_identity.py`
18. `code/durable_job_worker.py`
19. `src/tiny_agent/service_identity.py`
20. `src/tiny_agent/jobs.py`
21. `tests/test_service_identity.py`
22. `tests/test_jobs.py`

## Identity rule

Never infer:

```text
client says user_id=admin
therefore caller is admin
```

Production identity comes from a trusted authentication boundary: gateway/JWT validation, session service, mTLS/workload identity, or equivalent.

Tiny-Agent's `AuthenticatedIdentity` combines an already authenticated `Principal` with a tenant ID. `bind_trusted_identity()` rejects client metadata that tries to supply reserved identity fields.

## Durable jobs

For work that may take minutes or survive process restarts, prefer a durable contract:

```text
POST /runs
    -> persist queued run
    -> 202 + run_id

worker
    -> atomically claim lease
    -> execute
    -> persist result/failure

GET /runs/{id}
    -> current durable state
```

`SQLiteRunQueue` is a local teaching implementation of those semantics. Production may use Postgres, a managed queue, or a workflow engine.

## Existing reusable service core

`BoundedAgentService` remains the request/response execution boundary:

- process-local semaphore;
- queue timeout;
- execution deadline;
- async/sync handler support;
- correct deferred capacity release when a timed-out sync worker thread is still alive;
- safe public error types;
- service counters.

This solves bounded synchronous-style serving. It is deliberately different from the durable job queue.

## Install

```bash
python -m pip install -e ".[dev,stage10]"
```

## Tests

```bash
pytest -q tests/test_production.py tests/test_stage10_integrations.py tests/test_jobs.py tests/test_service_identity.py
```

## Run

```bash
python stages/10-production-deployment/code/service_app.py
```

Compose:

```bash
docker compose -f stages/10-production-deployment/compose.yaml up --build
```

## References

- FastAPI deployment — https://fastapi.tiangolo.com/deployment/concepts/
- FastAPI lifespan — https://fastapi.tiangolo.com/advanced/events/
- Uvicorn deployment — https://www.uvicorn.org/deployment/
- Psycopg pools — https://www.psycopg.org/psycopg3/docs/api/pool.html
- redis-py asyncio — https://redis.readthedocs.io/en/latest/examples/asyncio_examples.html
- Pydantic Settings — https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- A2A specification — https://a2a-protocol.org/latest/specification/

## Milestone

Build a service where caller identity is derived from a trusted boundary, short runs are capacity/deadline bounded, long runs can be persisted/claimed by workers, shared state lives outside process memory, and deployment failure semantics are explicit.

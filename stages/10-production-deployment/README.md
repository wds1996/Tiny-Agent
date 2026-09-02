# Stage 10 — Production Service & Deployment

## Why this stage exists

A local Agent that works once in a notebook is not yet a production service. Production means **many callers, process restarts, bounded resources, external state, operational probes, deployment configuration, and reproducible builds**.

The key shift is:

```text
local function call
    -> service boundary
    -> bounded concurrency + deadlines
    -> HTTP API + streaming
    -> external durable/shared infrastructure
    -> explicit startup/shutdown lifecycle
    -> container image
    -> CI + deployment probes
```

> A Dockerfile does not sprinkle production fairy dust on a Python script. It only packages whatever engineering decisions you already made — including the bad ones.

## Learning goals

By the end of this stage you should be able to explain and implement:

- why the HTTP route should stay thinner than the Agent runtime;
- request ID vs run ID vs user/session/thread identity;
- process-local concurrency limits vs distributed rate limits;
- request deadlines, overload rejection, and cancellation caveats;
- SSE streaming and why errors after headers are sent become protocol events;
- liveness vs readiness;
- FastAPI lifespan for resource startup/shutdown;
- PostgreSQL vs Redis responsibilities;
- explicit async connection-pool lifecycle;
- environment configuration vs secret management;
- one-process/multi-process/multi-container memory boundaries;
- Dockerfile/Compose responsibilities;
- why in-process background tasks are not a durable job queue;
- graceful shutdown and draining;
- how A2A becomes a real network service boundary;
- what CI can prove before deployment and what it cannot.

## Deliberate learning order

```text
01 service_boundary.py
   ↓
02 fastapi_in_process.py
   ↓
03 streaming_sse.py
   ↓
04 health_readiness.py
   ↓
05 settings_and_secrets.py
   ↓
06 postgres_pool.py
   ↓
07 redis_rate_limit.py
   ↓
08 lifespan_resources.py
   ↓
09 a2a_http_server.py
   ↓
10 service_app.py + Dockerfile + compose.yaml
```

Do not start by copying the Dockerfile. Understand what the container is hosting first.

## Framework-neutral core added in this stage

`src/tiny_agent/production.py` adds:

- `ServiceRequest` with distinct `request_id` and `run_id`;
- `BoundedAgentService`;
- process-local concurrency admission;
- queue timeout and run timeout;
- async and sync-handler execution without blocking the event loop;
- safe capacity/timeout exception types;
- service-level counters;
- bounded readiness checks with raw exception-text redaction.

Important limitation:

```text
asyncio.Semaphore
    = one Python process admission control
    ≠ distributed rate limiter
```

If you start four worker processes, you now have four independent semaphores.

## FastAPI adapter

`src/tiny_agent/integrations/fastapi_app.py` provides:

```text
GET  /livez
GET  /readyz
POST /v1/runs
POST /v1/runs/stream
```

The route layer delegates execution to `BoundedAgentService`; it does not reimplement Agent policy.

Failure mapping:

```text
capacity queue timeout -> HTTP 429
run deadline           -> HTTP 504
unexpected failure     -> HTTP 500 with generic text
```

Raw exception messages are not copied into API responses.

## Infrastructure adapters

### PostgreSQL

`PostgresPool` wraps `psycopg_pool.AsyncConnectionPool` with explicit:

```text
open=False
await pool.open()
await pool.wait()
...
await pool.close()
```

This is intentionally lifecycle-driven and fits FastAPI lifespan.

### Redis

Stage 10 uses Redis for a **distributed fixed-window rate-limit example** and health checks. Caller identity is hashed before becoming a Redis key.

Redis is not introduced as long-term Agent memory. That semantic role already belongs to Stage 06 stores/checkpoints.

## A2A over a real service boundary

Stage 09 taught A2A objects and interoperability semantics without hosting a server. Stage 10 completes the missing boundary:

```text
AgentExecutor
    -> DefaultRequestHandler
    -> A2A route factory
    -> ASGI application
    -> Uvicorn / container / network
```

The teaching example still uses an in-memory A2A task store and therefore explicitly does **not** claim durable multi-replica task semantics.

## Docker / Compose milestone

The stage includes:

```text
Dockerfile
compose.yaml
.env.example
```

The Compose stack contains:

```text
api
postgres
redis
```

with dependency health checks and API readiness probing.

## Install

```bash
python -m pip install -e ".[dev,stage10]"
```

## Run tests

```bash
pytest -q tests/test_production.py tests/test_stage10_integrations.py
```

## Run the local API

```bash
python stages/10-production-deployment/code/service_app.py
```

Then:

```bash
curl http://127.0.0.1:8000/livez
curl http://127.0.0.1:8000/readyz

curl -X POST http://127.0.0.1:8000/v1/runs \
  -H 'content-type: application/json' \
  -d '{"input":"hello production"}'
```

## Run with Compose

```bash
docker compose -f stages/10-production-deployment/compose.yaml up --build
```

## Theory chapters

1. [Service boundaries and identities](theory/01-service-boundaries-and-identities.md)
2. [Async, concurrency, streaming, and backpressure](theory/02-async-concurrency-streaming.md)
3. [Persistence and infrastructure responsibilities](theory/03-postgres-redis-and-state.md)
4. [Configuration, secrets, and lifecycle](theory/04-config-secrets-lifecycle.md)
5. [Containers, workers, and deployment topology](theory/05-containers-workers-deployment.md)
6. [Health, graceful shutdown, jobs, and operations](theory/06-operability-and-background-work.md)
7. [A2A as a deployed network service](theory/07-a2a-network-service.md)

## Recommended references

Read in this order:

1. FastAPI deployment concepts: <https://fastapi.tiangolo.com/deployment/concepts/>
2. FastAPI in containers: <https://fastapi.tiangolo.com/deployment/docker/>
3. FastAPI lifespan: <https://fastapi.tiangolo.com/advanced/events/>
4. Uvicorn deployment: <https://www.uvicorn.org/deployment/>
5. Docker Python guide: <https://docs.docker.com/guides/python/>
6. Psycopg pools: <https://www.psycopg.org/psycopg3/docs/api/pool.html>
7. redis-py asyncio: <https://redis.readthedocs.io/en/latest/examples/asyncio_examples.html>
8. Pydantic Settings: <https://docs.pydantic.dev/latest/concepts/pydantic_settings/>
9. A2A Python server tutorial: <https://a2a-protocol.org/latest/tutorials/python/5-start-server/>

## Milestone

Build and test a reproducible containerized Tiny-Agent API with bounded execution, SSE, health/readiness, PostgreSQL/Redis lifecycle examples, configuration hygiene, and a current A2A server boundary.

## Key question

> What changes when your Agent is no longer “my Python process,” but a service that other people and other Agents depend on?

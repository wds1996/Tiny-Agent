# 05 — Containers, Workers, Replicas, and Deployment Topology

Deployment is where a local Agent stops being one Python process you personally watch and becomes a distributed set of failure boundaries.

The important lesson is not "learn Docker commands." It is to understand which state/resources multiply when you add processes, containers, and replicas.

---

## 1. Image vs container

```text
Dockerfile
   ↓ build
image
   ↓ + runtime config
container
```

An image should contain reproducible application/runtime dependencies, not environment-specific secrets.

A container is an execution instance of that image.

---

## 2. What Docker solves—and what it does not

Docker helps package:

- Python/runtime;
- dependencies;
- application source;
- startup command;
- filesystem assumptions.

It does **not** automatically solve:

- authentication/authorization;
- durable state;
- distributed locking;
- graceful job recovery;
- exactly-once side effects;
- observability design;
- hostile-code sandboxing.

A container is packaging/isolation infrastructure, not an architecture completion badge.

---

## 3. Worker vs replica

```text
worker
    = process executing requests inside one deployment unit

replica
    = another service/container instance
```

Example:

```text
3 containers
× 4 Uvicorn workers each
= 12 Python processes
```

Each process may own its own:

```text
semaphore
model client
connection pool
in-memory cache
loaded data
telemetry buffers
```

This multiplication is easy to miss when development uses one process.

---

## 4. Memory multiplication

Suppose each process uses:

```text
Agent/runtime/libs 400 MB
local vector index 800 MB
cache              300 MB
```

Four workers:

```text
~1.5 GB × 4 = ~6 GB
```

before container/OS overhead.

If the vector index does not need process-local copies, use an external service/backend rather than discovering memory arithmetic through OOM kills.

---

## 5. Connection multiplication

If each worker creates a Postgres pool of max 10:

```text
12 processes × 10 = up to ~120 app connections
```

This is why deployment topology and Stage 13 state/pool configuration must be designed together.

Do not configure each process in isolation from the number of processes that will exist.

---

## 6. One process per container?

There is no universal slogan.

Common orchestrated pattern:

```text
one app process/container
scale replicas externally
```

Advantages:

- simpler resource accounting;
- straightforward health/restart model;
- orchestration owns scaling.

On a small single-host deployment, multiple Uvicorn workers in one container can be reasonable.

The correct answer depends on topology. Memorizing "one process per container" without understanding why is just Docker-flavored folklore.

---

## 7. Externalize shared/durable state

Multiple processes cannot safely depend on a Python dictionary for shared truth.

Use systems matching the semantics:

```text
Postgres       -> durable structured truth
Redis          -> shared ephemeral coordination/cache
object storage -> large durable artifacts
vector DB      -> retrieval index/service
```

The model context remains a selected view, not the persistence layer.

---

## 8. A production-shaped Dockerfile

This example matches Tiny-Agent's current package metadata, including the `README.md` referenced by `pyproject.toml`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

RUN useradd --create-home appuser
USER appuser

CMD ["uvicorn", "tiny_agent_app:app", "--host", "0.0.0.0", "--port", "8000"]
```

The final module/command is illustrative; a real deployment points it at the application's actual ASGI module. The packaging portion is intentionally consistent with the repository's build metadata.

Real projects may optimize layering by copying lock/dependency metadata before frequently changing source.

Important principles:

```text
reproducible dependency versions
non-root where practical
no secrets baked into image
explicit startup command
small attack/dependency surface
```

---

## 9. Image supply chain

Production image questions include:

- Is the base image pinned/versioned?
- Are dependencies locked?
- Are images scanned?
- Is provenance/signing required?
- Who can publish deployment images?
- Are SBOM/vulnerability policies needed?

This matters especially if an Agent can execute packages/code in adjacent sandboxes.

---

## 10. Rollouts and graceful drain

Deployment update:

```text
old replica serving work
-> orchestration marks terminating
-> stop receiving new traffic
-> drain/cancel/requeue work according to contract
-> close resources
-> exit
```

If a 20-minute Agent task is bound only to an HTTP worker, rolling deployment can become accidental task cancellation.

Long work should use durable job/checkpoint/harness state.

---

## 11. Compose vs orchestrator

Docker Compose is excellent for:

- local integration;
- teaching dependencies;
- small single-host setups.

Larger production environments additionally care about:

```text
multi-host scheduling
rolling deployment
autoscaling
secret distribution
network policy
persistent volumes
resource requests/limits
service discovery
```

The exact orchestrator is less important than understanding these concerns.

---

## 12. TLS/HTTPS boundary

Common topology:

```text
internet client
-> TLS load balancer / reverse proxy
-> internal HTTP ASGI service
```

The application still must understand forwarded identity/proxy trust correctly. "TLS happens elsewhere" does not mean network trust is irrelevant.

---

## 13. Worked capacity case

You deploy:

```text
5 replicas
2 workers each
8 Agent runs/worker
10 DB connections/worker
```

Potential capacity:

```text
80 in-flight Agent runs
100 DB connections
```

If each Agent may fan out to 3 provider calls, upstream pressure can be much higher.

Production sizing must reason across the whole dependency graph.

---

## Completion principle

> **Deployment topology multiplies processes, memory, connections, and local limits. Externalize shared state, size resources across replicas, and make graceful replacement part of the Agent run contract.**

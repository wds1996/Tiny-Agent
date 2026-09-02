# 05 — Containers, workers, and deployment topology

## Image vs container

```text
Dockerfile -> image
image + runtime config -> container
```

The image should be reproducible and should not contain environment-specific secrets.

## What Docker solves

Docker is good at packaging:

- Python runtime;
- package dependencies;
- application source;
- startup command;
- filesystem/runtime assumptions.

It does not automatically solve:

- authorization;
- database durability;
- distributed locking;
- graceful task recovery;
- observability design;
- exactly-once Agent side effects.

## One process per container?

In orchestrated environments, a common pattern is one application process per container and scale containers externally.

On a simple single-server Docker Compose deployment, multiple Uvicorn workers in one container may also be reasonable.

The important part is understanding the topology rather than memorizing a slogan.

## Memory multiplication

Four worker processes mean four copies of process memory.

If loading a model/runtime consumes 1.5 GB per process:

```text
4 workers ≈ 6 GB
```

before OS/container overhead.

Agents can also hold large prompts, vector indexes, caches, SDK pools, and telemetry buffers, so worker count is not merely CPU count.

## External state

Multiple processes/containers cannot rely on a normal Python dictionary for shared state.

Use external state with the semantics you need:

```text
Postgres -> durable truth
Redis    -> ephemeral shared coordination/cache
object store -> large artifacts
```

## Dockerfile layering

Put slowly changing dependency installation before rapidly changing source code when possible. This improves layer caching.

Use a non-root user where practical.

Do not bake `.env` or API credentials into image layers: deleting them in a later layer does not erase them from earlier layers.

## Compose

Compose is excellent for:

- local integration testing;
- small single-host deployments;
- teaching service dependencies.

It is not a substitute for understanding production orchestration concerns such as multi-host scheduling, autoscaling, rollout strategy, and secret distribution.

## HTTPS

The application container commonly receives HTTP behind a load balancer/reverse proxy that terminates TLS. FastAPI documentation explicitly treats HTTPS as often external to the application container.

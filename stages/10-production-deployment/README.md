# Stage 10 — Production Service & Deployment

## Why this stage exists

A local Agent script is not yet a service. Real applications need stable APIs, async execution, streaming, configuration, secrets, persistence infrastructure, tests, containers, and operational visibility.

This stage turns the learning runtime into a deployable software system.

## Planned topics

- FastAPI service boundaries;
- request/task/session models;
- async Agent execution;
- streaming responses and events;
- background task architecture concepts;
- PostgreSQL and Redis responsibilities;
- environment configuration and secrets;
- Docker images;
- Docker Compose;
- CI tests;
- structured logging;
- health/readiness endpoints;
- concurrency and rate limits;
- latency and cost controls.

## Planned code artifacts

```text
code/
├── api/
├── config/
├── persistence/
├── Dockerfile
├── compose.yaml
└── ci-example.yaml
```

## Planned theory

```text
theory/
├── 01-agent-service-boundaries.md
├── 02-async-and-streaming.md
├── 03-persistence-infrastructure.md
├── 04-docker-and-configuration.md
└── 05-production-operability.md
```

## Milestone

Run Tiny-Agent as a reproducible containerized API service with streaming, persistence, tests, configuration management, and basic operational health checks.

## Key question

> What changes when an Agent must serve many users reliably instead of running once in a local notebook?

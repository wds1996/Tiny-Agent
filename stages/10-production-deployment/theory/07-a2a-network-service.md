# 07 — A2A as a deployed network service

Stage 09 stopped deliberately at protocol objects.

Stage 10 crosses the network boundary.

## Server stack

Current A2A Python SDK server architecture can be viewed as:

```text
Agent business logic
    -> AgentExecutor
    -> EventQueue
    -> DefaultRequestHandler
    -> TaskStore
    -> A2A route factory
    -> Starlette/FastAPI ASGI app
    -> Uvicorn
```

The route factory exposes discovery and protocol endpoints while allowing normal ASGI middleware/auth/logging around them.

Tiny-Agent wraps this current route-factory pattern in `build_a2a_starlette_app()` so SDK compatibility is covered by an integration test rather than living only in a tutorial script.

## Agent output helpers are versioned SDK surface

Current `a2a-sdk` 1.1.x uses helpers such as:

```python
from a2a.helpers import new_text_message
```

Older tutorials may show names such as `new_agent_text_message`. Treat helper names as version-specific SDK APIs and validate them in CI.

## Agent Card is public contract

A deployed Agent Card contains advertised interface URLs. Those URLs must match the address clients can actually reach, not `localhost` inside the container.

Bad production card:

```text
http://127.0.0.1:9999
```

when clients actually reach:

```text
https://agents.example.com/research
```

## TaskStore and replicas

The teaching example uses `InMemoryTaskStore`.

That is acceptable for learning and one-process smoke tests.

It is not durable or safely shared across replicas.

If A2A clients rely on:

```text
get task
cancel task
resubscribe to stream
```

a production server needs task/event state whose availability matches that contract.

## Shutdown

Current `DefaultRequestHandler` exposes an async close/drain path. `build_a2a_starlette_app()` wires that cleanup into ASGI lifespan so active internal tasks are not simply abandoned when the host shuts down.

## Authentication

A2A protocol compatibility does not authenticate users for you.

You still need the deployment's normal controls:

```text
TLS
caller authentication
user/tenant binding
authorization
rate limiting
request size limits
logging/tracing
```

Agent Card discovery is not permission.

## MCP + A2A + service deployment

A deployed architecture may be:

```text
Client Agent
   | A2A
   v
Research Agent service
   | MCP
   +--> search server
   +--> document server
   +--> database capability
```

Stage 05 standardized capabilities. Stage 09 standardized Agent-to-Agent collaboration concepts. Stage 10 makes those boundaries operational network services.

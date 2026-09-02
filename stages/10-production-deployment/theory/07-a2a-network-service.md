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

Current `DefaultRequestHandler` provides an async close/drain path. A production ASGI host should wire handler cleanup into lifespan/shutdown rather than abandoning pending internal tasks.

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

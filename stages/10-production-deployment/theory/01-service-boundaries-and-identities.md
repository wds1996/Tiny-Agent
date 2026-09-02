# 01 — Service boundaries and identities

## From function to service

Locally you might write:

```python
answer = await agent.run("summarize this")
```

Production adds a boundary:

```text
client
  -> network
  -> HTTP server
  -> validation/auth/admission
  -> Agent service
  -> model/tools/state
```

The HTTP endpoint should translate protocol concerns, not become the new Agent runtime.

Bad:

```python
@app.post('/run')
async def run(body):
    # routing + planning + retries + tool auth + DB + model + logging + ...
```

Better:

```python
@app.post('/run')
async def run(body):
    return await service.run(to_service_request(body))
```

This keeps the same Agent behavior usable from HTTP, tests, workers, CLI, or A2A.

## Four IDs beginners often mix together

```text
request_id = one HTTP request / trace correlation handle
run_id     = one logical Agent execution
thread_id  = resumable conversation/workflow state (Stage 06)
user_id    = authenticated principal identity
```

They may sometimes have a 1:1 relationship, but they are not semantically interchangeable.

A retry may produce:

```text
request A -> run 42
request B -> run 42   # idempotent retry design
```

A streaming connection may have one request ID while the logical run survives a reconnect.

A user may own many thread IDs.

## IDs are routing handles, not credentials

Never reason:

```text
client knows thread_id
therefore client may read thread
```

Authorization still binds a persisted object to authenticated user/tenant/workspace context.

This is the same lesson Stage 09 applied to A2A task IDs.

## Validation boundary

FastAPI/Pydantic can validate HTTP shape:

```text
input is string
input length bounded
metadata is object
```

But Stage 07 still owns Tool argument validation and authorization. HTTP validation does not replace runtime governance.

## Thin boundary principle

A useful test:

> Could I invoke the same Agent service without FastAPI?

If the answer is “no because all my logic lives inside route decorators,” the service boundary is too thick.

## What not to expose

Avoid copying arbitrary exception strings into HTTP responses:

```python
except Exception as exc:
    return {"error": str(exc)}  # may leak SQL, keys, paths, prompts
```

Prefer stable public error codes/messages and keep detailed diagnostics in governed telemetry.

## Stage 10 mapping

```text
FastAPI route
    = transport adapter

BoundedAgentService
    = service execution boundary

AgentRuntime / TeamRuntime
    = Agent semantics

Postgres / Redis
    = external infrastructure
```

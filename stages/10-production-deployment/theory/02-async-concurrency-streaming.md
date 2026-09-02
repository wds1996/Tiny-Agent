# 02 — Async, concurrency, streaming, and backpressure

## Async is not “make everything faster”

Async helps when tasks spend time waiting on I/O:

```text
LLM API
HTTP
Postgres
Redis
MCP/A2A
```

It does not magically parallelize CPU-heavy Python work.

## The event-loop restaurant

Imagine one waiter serving many tables. The waiter is efficient because customers spend time chewing.

If one customer says:

> “Please stand here and manually calculate a billion matrix multiplications before serving anyone else.”

Congratulations: your elegant async restaurant now has one very committed waiter and 40 angry tables.

Blocking work inside `async def` blocks the event loop.

Stage 10 therefore sends synchronous handlers through `asyncio.to_thread()` for compatibility. But this has a critical caveat:

```text
request timeout
    != hard kill of worker thread
```

For untrusted or hard-termination workloads, use process/container/job isolation appropriate to the risk.

## Concurrency limit vs rate limit

Concurrency asks:

> How many runs are executing right now?

Rate limit asks:

> How many requests may this caller make over a time window?

They solve different overload problems.

Tiny-Agent uses a process-local semaphore for concurrency:

```text
max_concurrency = 8
```

With four Uvicorn workers:

```text
8 × 4 = potentially 32 concurrent runs
```

because process memory is not shared.

A distributed Redis limiter is introduced separately.

## Queue timeout

Unlimited waiting is not kindness.

Without a bounded queue, overload becomes:

```text
traffic spike
 -> more waiting requests
 -> more memory
 -> longer latency
 -> client retries
 -> even more traffic
```

Stage 10 uses a short admission timeout and returns a stable capacity failure.

## Execution deadline

After admission, every run still needs a deadline.

A useful mental model:

```text
client deadline
>= gateway deadline
>= service deadline
>= downstream/model/tool deadlines
```

If inner dependencies can wait longer than the outer request, resources may continue working after the caller has given up.

## Streaming with SSE

Server-Sent Events are useful for one-way server-to-client progress:

```text
event: run.started
data: {...}

event: run.completed
data: {...}
```

Once HTTP headers and stream bytes have been sent, you generally cannot later transform the response into a normal HTTP 500/504 body.

So streaming errors become protocol events:

```text
event: run.error
data: {"code":"run_timeout"}
```

## Backpressure

Streaming does not mean “generate infinitely and hope TCP handles life.”

You must consider:

- slow clients;
- proxy buffering;
- bounded internal queues;
- disconnect detection;
- cancellation propagation;
- reconnect semantics;
- event ordering.

The Stage 10 SSE endpoint teaches the transport shape, not a full durable event bus.

## Background work warning

FastAPI `BackgroundTasks` can be useful for small post-response work inside the same process.

It is not a durable distributed job queue.

If the process crashes after returning 200 but before the background function finishes, the universe does not send a polite apology email to your database.

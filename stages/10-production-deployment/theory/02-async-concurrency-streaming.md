# 02 — Async, Concurrency, Deadlines, Streaming, and Backpressure

`async` is one of the most commonly over-celebrated keywords in Agent tutorials.

It is useful. It is not a spell meaning "faster."

---

## 1. Async helps while waiting

Good async workloads spend time waiting for I/O:

```text
LLM API
HTTP
Postgres
Redis
MCP / A2A
object storage
```

CPU-heavy Python work still consumes CPU.

### The event-loop restaurant

Imagine one waiter serving many tables efficiently because customers spend most of their time eating.

Then one customer asks the waiter:

> Please stand here and calculate a billion matrix multiplications before serving anyone else.

Your elegant async restaurant now has one extremely loyal waiter and 40 angry tables.

Blocking work inside `async def` blocks the event loop.

---

## 2. Sync compatibility through worker threads

Tiny-Agent supports a synchronous handler by moving it off the event loop:

```python
value = await asyncio.to_thread(
    self._handler,
    request.input,
    payload,
)
```

This improves event-loop responsiveness.

It does **not** make the thread hard-killable.

That distinction matters for deadlines.

---

## 3. Timeout != termination

Scenario:

```text
max_concurrency = 1
sync handler starts in worker thread
request timeout = 1 second
actual handler runs = 20 seconds
```

If the service returns timeout at second 1 and immediately releases capacity, a second request starts while the first thread is still working.

The promised concurrency limit becomes fiction.

Tiny-Agent therefore shields the sync invocation and defers semaphore release until the underlying work actually finishes:

```python
output = await asyncio.wait_for(
    asyncio.shield(invocation),
    timeout=request_timeout,
)
```

On timeout:

```text
caller receives timeout
worker thread may continue
capacity remains reserved
worker ends
capacity released
```

If hard termination is required, use a process/container/job boundary designed for it.

---

## 4. Concurrency limit vs rate limit

```text
concurrency limit
    = how many operations are running now?

rate limit
    = how many operations may this caller start per time window?
```

Different overload problems.

Tiny-Agent's `asyncio.Semaphore` is process-local:

```python
self._gate = asyncio.Semaphore(max_concurrency)
```

With four workers:

```text
8 per worker × 4 workers ~= 32 possible in-flight runs
```

A distributed rate/quota policy needs shared infrastructure such as a gateway/Redis-based mechanism.

---

## 5. Queue timeout prevents overload from becoming hidden latency

Without bounded admission:

```text
traffic spike
-> waiting requests accumulate
-> memory grows
-> latency grows
-> clients time out/retry
-> even more requests
```

This is how a service can politely queue itself into a crater.

Tiny-Agent uses:

```python
await asyncio.wait_for(
    self._gate.acquire(),
    timeout=queue_timeout_seconds,
)
```

Failure becomes `ServiceCapacityError` instead of unlimited invisible waiting.

---

## 6. Deadlines should decrease inward

Useful mental model:

```text
client deadline
  >= gateway deadline
  >= service run deadline
  >= Tool/model/downstream deadlines
```

If an inner HTTP client can wait 120 seconds while the outer Agent request times out after 10, resources can continue working long after the caller has gone home.

Propagate cancellation/deadlines where the dependency supports it.

---

## 7. Parallel fan-out must be bounded

Research Agent:

```python
tasks = [
    asyncio.create_task(search(q))
    for q in subquestions
]
results = await asyncio.gather(*tasks)
```

This is fine only because the number of `subquestions` is bounded and downstream clients have their own controls.

Bad:

```text
model emits 5,000 subquestions
-> create 10,000 HTTP tasks
-> discover rate limits through interpretive dance
```

Application budgets must constrain fan-out before scheduling.

---

## 8. Streaming with SSE

SSE works well for one-way server-to-client progress:

```text
event: run.started
data: {"run_id":"42"}

event: run.progress
data: {"step":3}

event: run.completed
data: {...}
```

After headers/stream bytes are sent, you generally cannot turn a later error into a normal JSON HTTP 500 body.

Streaming errors become stream protocol events:

```text
event: run.error
data: {"code":"run_timeout"}
```

Define event schemas and ordering deliberately.

---

## 9. Backpressure

Streaming is not:

```text
produce infinitely
-> TCP will parent the system for us
```

Consider:

- slow clients;
- proxy buffering;
- bounded queues;
- disconnect detection;
- cancellation;
- event retention/replay;
- reconnect semantics.

For durable long-running work, an event stream should usually be a **view of durable run state**, not the only place where progress exists.

---

## 10. BackgroundTasks is not a durable queue

Framework background callbacks are useful for small best-effort post-response work.

They do not automatically provide:

```text
durable enqueue
worker lease
retry policy
crash recovery
multi-worker coordination
dead-letter handling
```

If the process crashes after returning 200, the universe does not send a polite apology email to the lost callback.

Stage 10/10A therefore use durable job/task state for work that product contracts promise to resume.

---

## 11. Worked overload case

Service config:

```text
4 workers
max_concurrency=8 each
provider allows 20 concurrent model calls
```

Naive topology permits roughly 32 Agent runs, each of which may create more than one model call.

So local semaphore alone cannot enforce provider quota.

Need layered controls:

```text
gateway/tenant rate policy
+ process-local run concurrency
+ per-provider/model concurrency
+ bounded Agent fan-out
+ deadlines
```

One semaphore cannot govern an entire distributed dependency graph.

---

## Completion principle

> **Async improves I/O concurrency; capacity remains finite. Bound admission, fan-out, deadlines, and streams at the layer that owns each resource.**

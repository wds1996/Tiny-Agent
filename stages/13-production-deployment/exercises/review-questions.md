# Stage 13 Review, Coding & Interview Questions

## Concepts

1. Why is a working local Agent not yet a production service?
2. Explain request ID, run ID, thread ID, and authenticated user ID.
3. Why is knowing a thread/task ID not authorization?
4. Why should HTTP routes stay thin?
5. What is the difference between concurrency limiting and rate limiting?
6. Why does one `asyncio.Semaphore(8)` not impose a global limit across four Uvicorn workers?
7. What happens when a sync function blocks inside an `async def` route?
8. Why does `asyncio.to_thread()` improve responsiveness but not provide hard cancellation?
9. Why should overload waiting be bounded?
10. How would you map capacity exhaustion vs execution timeout to public API errors?
11. Why should raw exception text not be returned to callers?
12. Explain SSE and why stream errors often become events rather than new HTTP status codes.
13. What is backpressure?
14. Liveness vs readiness: what should each probe answer?
15. Why is checking Postgres from liveness often a bad idea?
16. Why do multi-process workers break in-memory session assumptions?
17. What belongs in PostgreSQL vs Redis?
18. When is Redis cache data allowed to disappear?
19. Why explicitly open/close async connection pools?
20. Why does connection-pool size multiply with replicas?
21. What does `SecretStr` protect, and what does it not protect?
22. Why is `.env` not a production secret manager?
23. What belongs in ASGI lifespan?
24. Why is FastAPI `BackgroundTasks` not a durable queue?
25. Sketch a durable long-running Agent job API.
26. What is graceful shutdown and why do Tool idempotency rules matter during retry?
27. Image vs container: what is the difference?
28. What does Docker solve and what does it not solve?
29. When might one process per container be preferable?
30. What changes if every worker loads a 2 GB local model/index?
31. Why should TLS often terminate outside the app container?
32. What can Docker Compose realistically teach/provide, and what production concerns remain?
33. How does Stage 10 observability extend into production correlation IDs?
34. Why is readiness not monitoring?
35. Why does A2A `InMemoryTaskStore` become problematic with multiple replicas?
36. What must a production Agent Card URL represent?
37. A2A compatibility vs authentication: why are they separate?
38. How do MCP and A2A fit together in a deployed Agent service?

## Coding exercises

1. Add a `max_input_bytes` boundary before JSON parsing at the proxy/gateway layer and explain why Pydantic string length alone is not the same control.
2. Add an `Idempotency-Key` contract to `/v1/runs`. Decide what should persist and for how long.
3. Add a `Retry-After` header to capacity responses.
4. Implement client-disconnect cancellation for the SSE example and document where cancellation may still fail.
5. Replace the fixed-window Redis limiter with a token-bucket implementation.
6. Add tenant-specific rate-limit policy without storing raw tenant IDs in Redis keys.
7. Extend readiness so optional dependencies do not make the service unready.
8. Add a Postgres run table and a migration; do not auto-create it inside every request.
9. Implement a 202/GET durable job API with a fake in-memory worker first, then identify everything still non-durable.
10. Add structured JSON logging with request_id and run_id, while keeping prompts/Tool outputs disabled by default.
11. Add a graceful-shutdown drain counter to `BoundedAgentService`.
12. Add a readiness check for model-provider credentials that does not make a paid model request.
13. Add A2A request authentication middleware and bind task access to caller identity.
14. Replace the A2A `InMemoryTaskStore` with a durable store appropriate for replicas.
15. Build the image and prove no `.env` file or API key is present in its layers/build context.

## Architecture cases

### Case A — one VM, small internal tool

You have 20 users, low traffic, Compose is acceptable, and downtime of a few minutes is tolerable. Design the simplest responsible topology.

### Case B — bursty public API

Traffic spikes 20x after a product announcement. Model calls are expensive and limited. Design admission control, distributed rate limits, timeouts, retries, and overload responses.

### Case C — 30-minute research Agent

Users can close the browser and return later. Design durable run state, worker ownership, progress delivery, cancellation, and retry semantics.

### Case D — A2A research service

Other organizations' Agents call your Agent. Design Agent Card discovery, TLS, authentication, tenant binding, rate limits, durable tasks, observability, and least-privilege downstream MCP credentials.

## Interview prompts

- “Why is async important for LLM services?”
- “How would you scale a FastAPI Agent service?”
- “Why can adding Uvicorn workers break an Agent application?”
- “Redis vs Postgres in an Agent platform?”
- “How do you design health checks?”
- “How do you deploy a long-running Agent task?”
- “What is graceful shutdown?”
- “How do you prevent retrying a Tool side effect twice after a worker crash?”
- “What does Docker actually give you?”
- “How would you productionize an A2A Agent?”

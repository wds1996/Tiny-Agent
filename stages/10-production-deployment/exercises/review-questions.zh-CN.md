# Stage 10 复习、编程与面试题

> Language: [English](review-questions.md) | 简体中文

## Concepts

1. 为什么一个 working local Agent 还不是 production service？
2. 解释 request ID、run ID、thread ID 与 authenticated user ID。
3. 为什么知道 thread/task ID 不代表 authorization？
4. 为什么 HTTP route 应保持 thin？
5. concurrency limiting 与 rate limiting 区别？
6. 为什么一个 `asyncio.Semaphore(8)` 无法对 4 个 Uvicorn workers 提供全局限制？
7. sync function 在 `async def` route 内 blocking 会发生什么？
8. 为什么 `asyncio.to_thread()` 提升 responsiveness，却不能提供 hard cancellation？
9. 为什么 overload waiting 必须 bounded？
10. capacity exhaustion 与 execution timeout 应怎样映射成 public API error？
11. 为什么 raw exception text 不应返回 caller？
12. 什么是 SSE？为什么 stream 已开始后 error 往往成为 event 而不是新的 HTTP status？
13. 什么是 backpressure？
14. Liveness 与 readiness 各自应该回答什么？
15. 为什么 liveness 里检查 Postgres 常常是坏主意？
16. 为什么 multi-process worker 会破坏 in-memory session assumption？
17. PostgreSQL vs Redis 分别适合放什么？
18. 什么情况下 Redis cache data 丢失是允许的？
19. 为什么 async connection pool 要显式 open/close？
20. 为什么 pool size 会随 replica/worker 成倍放大？
21. `SecretStr` 保护什么、不保护什么？
22. 为什么 `.env` 不是 production secret manager？
23. ASGI lifespan 应放哪些资源？
24. 为什么 FastAPI `BackgroundTasks` 不是 durable queue？
25. 画一个 durable long-running Agent job API。
26. 什么是 graceful shutdown？为什么 worker crash/retry 时 Tool idempotency rule 很重要？
27. Image vs container 区别？
28. Docker 解决什么、不解决什么？
29. 什么时候 one process per container 更合适？
30. 每个 worker 都加载 2GB local model/index 会怎样？
31. 为什么 TLS 常在 app container 外终止？
32. Docker Compose 可以现实地教/提供什么？哪些 production concern 仍存在？
33. Stage 08 observability 怎样扩展到 production correlation ID？
34. 为什么 readiness 不是 monitoring？
35. A2A `InMemoryTaskStore` 多 replica 时为什么出问题？
36. Production Agent Card URL 应代表什么？
37. 为什么 A2A compatibility 与 authentication 分开？
38. MCP 与 A2A 怎样同时出现在 deployed Agent service？

---

## Coding Exercises

1. 在 proxy/gateway 层、JSON parsing 前增加 `max_input_bytes`。解释为什么 Pydantic string length 不是同一种 control。
2. 给 `/v1/runs` 增加 `Idempotency-Key` contract，决定需要持久化什么、保留多久。
3. Capacity response 增加 `Retry-After` header。
4. 为 SSE example 实现 client-disconnect cancellation，并说明 cancellation 仍可能在哪些地方失效。
5. 把 fixed-window Redis limiter 换成 token bucket。
6. 增加 tenant-specific rate limit，但 Redis key 不保存 raw tenant ID。
7. Readiness 支持 optional dependency failure 时仍保持 ready。
8. 增加 Postgres run table + migration，不要在每个 request 内 auto-create。
9. 先用 fake in-memory worker 实现 202/GET durable job API，再列出仍然不 durable 的部分。
10. 增加 structured JSON logging，包含 request_id/run_id，但默认不记录 prompt/Tool output。
11. 给 `BoundedAgentService` 增加 graceful-shutdown drain counter。
12. 增加 model-provider credential readiness check，但不能发付费 model request。
13. 增加 A2A request authentication middleware，并把 task access 绑定 caller identity。
14. 将 A2A `InMemoryTaskStore` 替换为适合 replicas 的 durable store。
15. Build image 并证明 `.env`/API key 不存在于 image layer/build context。

---

## Architecture Cases

### Case A — One VM, Small Internal Tool

20 users、低流量、可接受 Compose、几分钟 downtime 可容忍。设计最简单但负责任的 topology。

### Case B — Bursty Public API

产品发布后 traffic 突增 20 倍，model call 昂贵且有 quota。设计 admission、distributed rate limit、timeout、retry、overload response。

### Case C — 30-minute Research Agent

用户可关浏览器稍后回来。设计 durable run state、worker ownership、progress delivery、cancellation、retry semantics。

### Case D — A2A Research Service

其他组织 Agent 调用你的 Agent。设计 Agent Card、TLS、authentication、tenant binding、rate limit、durable task、observability、least-privilege downstream MCP credential。

---

## Interview Prompts

- “为什么 async 对 LLM service 重要？”
- “怎样扩展 FastAPI Agent service？”
- “为什么增加 Uvicorn worker 可能让 Agent app 出问题？”
- “Agent platform 中 Redis vs Postgres？”
- “怎样设计 health check？”
- “怎样部署 long-running Agent task？”
- “什么是 graceful shutdown？”
- “worker crash 后怎样避免 Tool side effect 被重复执行？”
- “Docker 到底提供了什么？”
- “怎样 productionize 一个 A2A Agent？”

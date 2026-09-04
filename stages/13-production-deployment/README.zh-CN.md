# Stage 13 — Production Service、Identity、Durable Jobs 与 Deployment

> Language: [English](README.md) | 简体中文

一个本地 Agent 偶尔成功运行，并不等于它已经是生产服务。Production 会引入 caller、identity、queue、deadline、process restart、external state、health probe、deployment topology 与明确的 operational contract。

本阶段沿着下面这条路径推进：

```text
local Agent call
    ↓
thin service boundary
    ↓
trusted authentication / tenant binding
    ↓
capacity admission + deadlines
    ↓
HTTP / SSE
    ↓
durable jobs for long work
    ↓
Postgres / Redis lifecycle
    ↓
health / graceful shutdown
    ↓
container / network deployment
    ↓
A2A service boundary
```

> **Dockerfile 只能把你的 architecture 打包起来，不能顺手把坏 architecture 修好。**

---

## 学习目标

完成 Stage 13 后，你应该能够解释并实现：

1. 在 domain/runtime logic 外保持 thin HTTP adapter；
2. 区分 request ID、run ID、thread ID、authenticated subject/tenant；
3. 解释为什么 request body 里的 `user_id` 不等于 authentication；
4. trusted principal binding 与 resource ownership check；
5. process-local concurrency 与 distributed rate limit 的区别；
6. queue timeout 与 execution deadline；
7. 为什么 timeout 不会 hard-kill synchronous worker thread；
8. SSE streaming，以及 response header 已发送后怎样用 stream error event 表达失败；
9. liveness 与 readiness 的区别；
10. PostgreSQL 与 Redis 各自适合承担什么 state responsibility；
11. explicit async connection-pool lifecycle；
12. configuration 与 secret management 的区别；
13. worker/replica 怎样成倍放大 memory、pool 与 concurrency；
14. graceful shutdown/draining；
15. 为什么 FastAPI `BackgroundTasks` 不是 durable queue；
16. durable enqueue、atomic worker claim、lease 与 crash recovery；
17. 为什么长时 HTTP work 更适合变成 `202 + run_id` 的 job contract；
18. Docker/Compose 能解决什么、不能解决什么；
19. A2A hosting 作为真实 network boundary；
20. CI 可以证明什么、不能证明什么。

---

## 推荐学习顺序

### Service boundary

1. [`theory/01-service-boundaries-and-identities.zh-CN.md`](theory/01-service-boundaries-and-identities.zh-CN.md)
2. `code/service_boundary.py`
3. `code/fastapi_in_process.py`
4. [`theory/02-async-concurrency-streaming.zh-CN.md`](theory/02-async-concurrency-streaming.zh-CN.md)
5. `code/streaming_sse.py`

### Infrastructure and lifecycle

6. [`theory/03-postgres-redis-and-state.zh-CN.md`](theory/03-postgres-redis-and-state.zh-CN.md)
7. [`theory/04-config-secrets-lifecycle.zh-CN.md`](theory/04-config-secrets-lifecycle.zh-CN.md)
8. `code/postgres_pool.py`
9. `code/redis_rate_limit.py`
10. `code/lifespan_resources.py`

### Deployment and operations

11. [`theory/05-containers-workers-deployment.zh-CN.md`](theory/05-containers-workers-deployment.zh-CN.md)
12. [`theory/06-operability-and-background-work.zh-CN.md`](theory/06-operability-and-background-work.zh-CN.md)
13. `code/health_readiness.py`
14. [`theory/07-a2a-network-service.zh-CN.md`](theory/07-a2a-network-service.zh-CN.md)
15. `code/a2a_http_server.py`

### 新的生产边界：Identity + Durable Jobs

16. [`theory/08-authentication-tenancy-and-durable-jobs.zh-CN.md`](theory/08-authentication-tenancy-and-durable-jobs.zh-CN.md)
17. `code/authenticated_identity.py`
18. `code/durable_job_worker.py`
19. `src/tiny_agent/service_identity.py`
20. `src/tiny_agent/jobs.py`
21. `tests/test_service_identity.py`
22. `tests/test_jobs.py`

---

## Identity Rule

永远不要这样推理：

```text
client says user_id=admin
therefore caller is admin
```

生产身份应该来自可信 authentication boundary，例如 gateway/JWT validation、session service、mTLS/workload identity 等。

Tiny-Agent 的 `AuthenticatedIdentity` 把已经认证过的 `Principal` 与 tenant ID 绑定；`bind_trusted_identity()` 会拒绝 client metadata 试图提供保留身份字段。

---

## Durable Jobs

分钟级甚至更长的工作，不应依赖一个 web worker 永远不死：

```text
POST /runs
    -> persist queued run
    -> 202 + run_id

worker
    -> atomically claim lease
    -> execute
    -> persist result/failure

GET /runs/{id}
    -> current durable state
```

`SQLiteRunQueue` 是对这套语义的本地教学实现；生产环境可以换成 Postgres、managed queue 或 workflow engine，但语义不能丢。

---

## Existing Reusable Service Core

`BoundedAgentService` 继续作为 request/response execution boundary，负责：

- process-local semaphore；
- queue timeout；
- execution deadline；
- async/sync handler；
- timed-out sync worker thread 仍活着时延迟释放 capacity；
- safe public error type；
- service counters。

它解决的是**有界的同步式服务请求**，与 durable job queue 是不同层。

---

## 安装与运行

```bash
python -m pip install -e ".[dev,stage13]"
```

```bash
pytest -q tests/test_production.py tests/test_stage13_integrations.py tests/test_jobs.py tests/test_service_identity.py
```

```bash
python stages/13-production-deployment/code/service_app.py
```

Compose：

```bash
docker compose -f stages/13-production-deployment/compose.yaml up --build
```

---

## 参考资料

- FastAPI deployment — https://fastapi.tiangolo.com/deployment/concepts/
- FastAPI lifespan — https://fastapi.tiangolo.com/advanced/events/
- Uvicorn deployment — https://www.uvicorn.org/deployment/
- Psycopg pools — https://www.psycopg.org/psycopg3/docs/api/pool.html
- redis-py asyncio — https://redis.readthedocs.io/en/latest/examples/asyncio_examples.html
- Pydantic Settings — https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- A2A specification — https://a2a-protocol.org/latest/specification/

---

## Milestone

最终你应该能构建这样一个服务：caller identity 来自可信边界；短 run 受到 capacity/deadline 限制；长 run 可以持久化并由 worker claim；shared state 不依赖单进程内存；deployment failure 的语义明确可解释。

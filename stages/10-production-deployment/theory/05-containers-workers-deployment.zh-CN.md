# 05 — Container、Worker、Replica 与 Deployment Topology

> Language: [English](05-containers-workers-deployment.md) | 简体中文

Deployment 是本地 Agent 从“你亲眼盯着的一个 Python process”，变成多个 failure boundary 的地方。

这一章重点不是背 Docker 命令，而是理解：**当 process、container、replica 增加时，哪些 state/resource 会被成倍复制。**

---

## 1. Image vs Container

```text
Dockerfile
   ↓ build
image
   ↓ + runtime config
container
```

Image 应包含可复现的 runtime/dependency/application，而不是 environment-specific secret。

Container 是 image 的一次 execution instance。

---

## 2. Docker 解决什么、不解决什么？

Docker 擅长打包：Python/runtime、dependency、source、startup command、filesystem assumptions。

它不会自动解决：authentication/authorization、durable state、distributed locking、graceful recovery、exactly-once side effect、observability design、hostile-code sandboxing。

Container 是 packaging/isolation infrastructure，不是“architecture 完工证书”。

---

## 3. Worker vs Replica

```text
worker
    = 一个 deployment unit 里的请求执行 process

replica
    = 另一个 service/container instance
```

例如：

```text
3 containers × 4 Uvicorn workers = 12 Python processes
```

每个 process 都可能拥有自己的 semaphore、model client、connection pool、in-memory cache、loaded data、telemetry buffer。

开发环境只有一个 process 时，很容易忽略这种乘法。

---

## 4. Memory Multiplication

每 process：

```text
runtime/libs       400 MB
local vector index 800 MB
cache              300 MB
```

4 workers 大约就是：

```text
1.5 GB × 4 ≈ 6 GB
```

还没算 container/OS overhead。

如果 vector index 不需要 process-local copy，更适合 external service/backend，而不是等 OOM killer 来给你补一堂心算课。

---

## 5. Connection Multiplication

每 worker pool max 10，12 processes 就可能接近 120 条 application DB connections。

因此 deployment topology 与 pool config 必须一起设计，不能只看单个 process。

---

## 6. One Process per Container？

没有万能口号。

常见 orchestrated pattern：

```text
one app process/container
scale replicas externally
```

好处是 resource accounting 与 health/restart 简单。

小型单机部署使用一个 container 多个 Uvicorn workers 也可能合理。

“一个 container 永远只能一个 process”如果只背结论、不理解原因，只是 Docker 风格的民间传说。

---

## 7. Externalize Shared / Durable State

多进程不能把 Python dict 当 shared truth。

根据语义选择：

```text
Postgres       -> durable structured truth
Redis          -> shared ephemeral coordination/cache
object storage -> large durable artifacts
vector DB      -> retrieval index/service
```

Model context 仍只是 selected view，不是 persistence layer。

---

## 8. Production-shaped Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

RUN useradd --create-home appuser
USER appuser

CMD ["uvicorn", "tiny_agent_app:app", "--host", "0.0.0.0", "--port", "8000"]
```

最终 ASGI module 只是示例，真实部署指向实际 app。

原则：dependency version 可复现；尽量 non-root；不把 secret bake 进 image；startup command 明确；attack/dependency surface 尽量小。

---

## 9. Image Supply Chain

生产要问：base image 是否 pin？dependency 是否 lock？image 是否 scan？是否需要 provenance/signing？谁能发布 image？是否需要 SBOM/vulnerability policy？

Agent 邻接 sandbox/package execution 时，这些更重要。

---

## 10. Rollout 与 Graceful Drain

```text
old replica serving
-> mark terminating
-> stop new traffic
-> drain/cancel/requeue according to contract
-> close resources
-> exit
```

20 分钟 Agent task 如果只绑在一个 HTTP worker 上，rolling deployment 就可能变成“部署顺便取消任务”。

Long work 应依赖 durable job/checkpoint/harness state。

---

## 11. Compose vs Orchestrator

Compose 很适合 local integration、教学 dependency、小型单机部署。

更大生产环境还关心 multi-host scheduling、rolling deployment、autoscaling、secret distribution、network policy、persistent volume、resource limits、service discovery。

具体 orchestrator 名字不如这些 responsibility 本身重要。

---

## 12. TLS / HTTPS Boundary

常见：

```text
internet client
-> TLS load balancer / reverse proxy
-> internal HTTP ASGI service
```

但 app 仍需正确理解 forwarded identity/proxy trust。“TLS 在外面终止”不等于 network trust 不再重要。

---

## 13. Capacity Example

```text
5 replicas
2 workers each
8 Agent runs/worker
10 DB connections/worker
```

潜在：80 in-flight Agent runs、100 DB connections。

如果每个 Agent 再 fan-out 3 次 provider call，上游压力会更大。

Sizing 必须横跨整个 dependency graph。

---

## Completion Principle

> **Deployment topology 会成倍放大 process、memory、connection 与 local limit。Shared state 要外置，资源要按全部 replica sizing，并把 graceful replacement 写进 Agent run contract。**

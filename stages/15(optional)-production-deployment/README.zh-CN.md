# Stage 15（选修）：本地 Demo 跑通以后，真正麻烦的才刚开始——把 Agent 变成 Production Service

> Language: [English](README.md) | **简体中文**

[Stage 14](../14-capstone-enterprise-agent/README.zh-CN.md) 已完成核心 Agent 学习路径。本选修适合你准备把 Agent 面向多个用户作为长期服务提供时学习：生产服务还要接住很多请求、穿过重启、对不同租户公平地限制负载，并让用户在原始 HTTP 连接结束后仍能找到自己的工作。

本章用 SQLite 实现一个很小、与 Web 框架无关的 Service Core。它不会假装 `python demo.py` 就是已经部署好的网站；先把 HTTP、队列和 Worker 无论怎样实现都必须保持的服务语义建立起来。

---

## 1. 先分清身份和生命周期：Request、Run、Thread、User、Tenant

这些名字很容易混在一起，但它们回答的问题不同：

| 名称 | 表示什么 | 常见生命周期 |
| --- | --- | --- |
| Request | 一次协议交互，例如 `POST /runs` | 毫秒到数秒 |
| Run | 一次可持久化的 Agent 执行 | 数秒、数分钟或更久 |
| Thread | 多个 Run 可以共用的一段会话或任务上下文 | 跨多个 Run |
| User | 已认证的最终用户 | 账户生命周期 |
| Tenant | 组织或客户的数据与资源隔离边界 | 组织生命周期 |

Request 只负责提交，Run 要在 Request 结束后继续承载这份工作：

```text
POST /runs
    → 创建 durable run
    → 返回 accepted + run_id

GET /runs/{run_id}
    → queued / running / completed / failed
```

Run 的身份必须来自可信认证边界，不能来自普通请求数据。本章的 Service Core 用单独的值表达这一点：

```python
from service import TrustedIdentity

identity = TrustedIdentity(user_id="alice", tenant_id="acme")
```

用户消息即使写着 `{"tenant_id":"evil"}`，它仍然只是任务输入。真实 HTTP Adapter 应先验证 Session、Token 或 mTLS 身份，再把得到的 `TrustedIdentity` 传给 `AgentService`；绝不能把 JSON 中自称的 `tenant_id` 提升为归属事实。

## 2. 提交是持久化操作，不是等待很久的 HTTP 请求

Agent 可能检索资料、调用 MCP、等待人工审批或生成 Artifact。让最初的 HTTP 连接一直等着，会让重试、负载均衡和重启都变得困难。提交接口应创建一条可持久化的 `queued` Run 并返回 ID；Worker 再去领取它。

下面是完整的本地示例，同时展示了两条服务规则：

- **Backpressure（背压）**：每个 Tenant 只能拥有有限数量的排队 Run。
- **Idempotency（幂等）**：重试同一个提交会返回原来的 Run，不会多创建一条。

```python
from pathlib import Path
import tempfile

from service import AgentService, RunStore, TrustedIdentity

with tempfile.TemporaryDirectory() as tmp:
    service = AgentService(
        RunStore(Path(tmp) / "runs.db"),
        max_queued_per_tenant=2,
    )
    identity = TrustedIdentity(user_id="alice", tenant_id="acme")

    first = service.submit(
        identity=identity,
        thread_id="support-42",
        input_text="Summarize ORDER-42.",
        idempotency_key="request-123",
    )
    retry = service.submit(
        identity=identity,
        thread_id="support-42",
        input_text="Summarize ORDER-42.",
        idempotency_key="request-123",
    )

    assert first.run_id == retry.run_id
    print(first.status)  # queued
```

Idempotency Key 表示“这是同一个业务操作的重试”，不是“随便复用一个方便的字符串”。教学 Store 按 `(tenant_id, idempotency_key)` 作用域保存它，因此不同 Tenant 都可以使用 `request-123`。同一个 Key 如果配上不同 User、Thread 或输入，会抛出 `IdempotencyConflictError`；生产系统也常保存请求体 Hash，而非保存完整输入来比较。

提交的幂等和 Run 内 Tool 的幂等不是同一层。Stage 09 中的支付或发邮件 Tool 仍需要自己的幂等键：前者防止重复创建 Run，后者防止同一个 Run 里的副作用重复发生。

## 3. Queue 需要归属、上限和 Durable State

提交和执行分开后，任务到达速度可能超过 Worker 消费速度。无限接收任务只会把失败从 HTTP Handler 推迟到内存、数据库、第三方限额和用户等待时间。

`max_queued_per_tenant` 把上限明确为每个 Tenant 的预算。Tenant 的队列满了，`AgentService.submit()` 会抛出 `BackpressureError`；另一个 Tenant 仍可以提交。这是走向公平调度的最小一步。真实调度器还可能增加全局容量、权重、优先级和限流，但每个预算都必须先说明作用域。

Run Record 也必须比 `AgentService` 这个 Python 对象活得久。本章通过 Python 标准库的 [`sqlite3`](https://docs.python.org/3/library/sqlite3.html) 使用 SQLite，保存 Run ID、Thread、认证后的 User 和 Tenant、状态、输入/输出、幂等键和时间戳。SQLite 是紧凑的教学 Store；换成 Postgres 或其他 Durable Store 时，必须保留同样的语义。

两者的区别是：

```text
内存字典会随进程退出而消失
Durable Run Record 在重新创建 Service 后仍能查询
```

它和 Stage 06 的 Checkpoint 有关联，但并不相同。Checkpoint 保存的是“怎样继续执行”所需的 Runtime State；Run Record 是服务可见的生命周期与归属记录。Stage 13 会把两者连到长任务中。

## 4. 领取 Run 既是状态迁移，也是并发控制

教学状态机故意保持很小：

```text
queued → running → completed
```

Worker 不能随意先 `SELECT` 一条 queued 记录、做别的事、最后才更新。两个 Worker 可能同时选中同一条。`RunStore.claim_next()` 用 SQLite 的 `BEGIN IMMEDIATE` Transaction，选择一条 queued Run 后立刻把它更新为 `running`，再提交；在这个 SQLite 示例中，选择与领取因此成为一个受保护的操作。

完成也有前提：只有当前状态为 `running` 的 Run 才能变成 `completed`。对 queued 或已经 completed 的 Run 调用 `complete()` 会抛出 `InvalidRunTransitionError`，避免过期 Worker 悄悄覆盖生命周期。

`BEGIN IMMEDIATE` 是本地教学用的并发边界，不是分布式 Worker Lease 的完整方案。如果 Worker 领取后消失，记录仍会停在 `running`；Stage 13 会用 Lease、Heartbeat 和恢复机制处理这个问题。

## 5. HTTP Adapter 要薄，Health 要诚实

本章代码是 Service Core，因此没有伪造认证 Middleware，也不会写一个把未验证 Header 当作可信身份的玩具 FastAPI 服务。真实应用中 HTTP 层应该只做协议工作，然后调用 Core：

```text
HTTP / API adapter
    → 验证凭证并创建 TrustedIdentity
    → 验证请求大小、结构和 deadline
    → AgentService.submit() 或 RunStore.get()

AgentService / RunStore
    → 持久化提交、归属检查、队列上限

Worker
    → 领取 Run、调用 bounded Agent runtime、保存结果
```

这种分层让同一个 Service Core 以后可以被 REST、Queue Consumer、CLI 或其他协议复用。它也让 Tenant Ownership 进入每次查询：`RunStore.get()` 同时以 `run_id` 和认证后的 `tenant_id` 查询。其他 Tenant 的调用者只会得到“not found”，不会借此知道那条 Run 是否存在。

Health Endpoint 也需要同样诚实。**Liveness** 问“进程还活着吗”；**Readiness** 问“它现在能接业务流量吗”。进程可能活着，但 Durable Store 已不可用。`store.ready()` 会执行一次很小的数据库查询，因此依赖故障可以让 Readiness 变成 false，而不是无条件返回 `{ "status": "ok" }`。

## 6. “Async”、Shutdown、Configuration 与真实 Runtime

“异步”常被用来描述两件不同的事：

```text
Python async def
    → 一种并发编程模型

Durable asynchronous job
    → 提交 Request 结束后，工作仍能继续
```

一个 `async def` Endpoint 仍可能让连接一直等待任务结束；一个同步 Python Worker 也可以处理 Durable Queue Job。本章真正关心的是 Durable Run 边界。

部署时，收到终止信号的进程应停止接收新任务、变为 not-ready、完成或安全暂停有限的工作、保存可恢复状态，然后退出。教学 Service 没有实现 Signal Handler，因为 Worker Loss 的恢复已在 Stage 13 讲解；但 Shutdown 必须被当作 Runtime Lifecycle 的一部分来设计。

配置和凭证同样来自部署边界。不要把它们写进 Prompt；每个 Secret 只交给真正需要它的组件。Stage 12 已经说明，子进程也不应该默认继承完整 Environment。

最后，`run_one()` 返回确定性字符串，并没有调用 DeepSeek。这是刻意的：本章需要稳定地测试服务归属、重试和持久化状态，不能让模型输出的不确定性掩盖服务语义。真实系统中，Worker 的这一步会调用前面章节建立的 bounded Agent Runtime，包括模型、工具、Guardrail 和 Workspace/Sandbox 边界。

## 7. 运行完整的 Service Core 示例

从仓库根目录运行：

```bash
python stages/15(optional)-production-deployment/code/demo.py
python stages/15(optional)-production-deployment/code/checks.py
```

Demo 会提交一条 Run、用相同幂等键再次提交、领取并完成该 Run、重新创建 Service，并从同一 SQLite 文件读取 completed record。检查覆盖可信身份、Tenant 作用域的查询和幂等、复用 Key 时的内容冲突、每个 Tenant 的背压、重启后的持久性、合法状态迁移和 Readiness。

## 8. 这门选修放在什么位置

Queue 已让 Run 脱离 HTTP Request，但还不能恢复“已被 Worker 领取、随后 Worker 消失”的任务。需要这部分机制时，回看 [Stage 13：Long-Horizon Harness](../13-long-horizon-harness/README.zh-CN.md)，其中会建立 Ledger、Lease、Heartbeat 和可恢复执行。

当你的 Agent 从本地或内部工具跨越到多用户生产服务时，再学习本选修即可；它很重要，但不是理解 Stage 00–14 Agent 核心机制的前置条件。

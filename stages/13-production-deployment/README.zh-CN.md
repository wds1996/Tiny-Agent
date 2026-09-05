# Stage 13：本机 Demo 跑通以后，真正麻烦才刚开始——把 Agent 变成 Production Service

> Language: [English](README.md) | **简体中文**

到 Stage 12，我们已经有了一个挺像样的 Agent System。它会调用外部能力，会保留 Durable State，会管理 Context，会加载 Skill，会做权限检查和 Eval，也能在受控 Workspace 里运行脚本。

然后你在本机执行 `python demo.py`，一切正常。产品经理看完说：“很好，明天上线吧。”

这句话通常是 Production Engineering 的发令枪。

因为“一个程序在我电脑上跑通”和“一个服务能长期接住真实用户请求”之间，还隔着一整套非常普通、非常重要、也完全不会因为用了 LLM 就自动消失的分布式系统问题。

Stage 13 不会把课程变成 Web Framework 教程。我们先把服务语义讲清：Request 是什么？Run 是什么？Thread 是什么？身份从哪里来？长任务怎么提交？队列满了怎么办？重启以后状态去哪里查？同一请求重发会不会创建两个 Run？服务什么时候算 Ready？

这些问题比“用 FastAPI 还是别的框架”更基础。

---

## 1. Request、Run、Thread、User、Tenant 终于全部到齐

Stage 06 已经区分过 `user_id`、`thread_id`、`run_id`。Production Service 再多一个 `request_id`。

HTTP Request 很短，它可能只存在几十毫秒；Run 却可能持续几分钟甚至几小时；Thread 是一段连续业务上下文；User 是最终用户身份；Tenant 则是组织或客户隔离边界。

所以：

```text
Request
    -> 一次网络交互

Run
    -> 一次 Agent 执行

Thread
    -> 多次 Run 可能共享的会话/任务上下文

User
    -> 谁在使用系统

Tenant
    -> 数据与资源属于哪个隔离域
```

这些 ID 不应该为了省事全部复用成一个字符串。

---

## 2. 身份不能相信 Request Body 自己说

一个危险 API 接受：

```json
{
  "tenant_id": "bank-a",
  "user_id": "admin",
  "message": "..."
}
```

然后服务端直接 `tenant = body["tenant_id"]`。

这等于问请求：“请问你有权扮演谁？”然后非常礼貌地相信答案。

Production Service 应该从可信认证边界得到身份，例如：

```python
TrustedIdentity(
    user_id=...,
    tenant_id=...,
)
```

Request Body 只提供业务输入。

本章检查里故意让 Input Text 写 `{"tenant_id":"evil"}`，最终 Run 仍然属于认证层传入的 `tenant-a`。

> **Identity 是服务边界建立的事实，不是模型或用户 Payload 里的建议。**

---

## 3. 为什么长 Agent Run 不应该一直占着 HTTP Request？

短请求当然可以 `request -> compute -> response`。

但 Agent 可能检索、调用 MCP、等待外部 API、规划、生成 Artifact，甚至等待 Human Approval。

更常见的服务模型是：

```text
POST /runs
    ↓
创建 durable run
    ↓
accepted + run_id

GET /runs/{run_id}
    ↓
queued / running / completed / failed
```

也就是说：

> **HTTP Request 负责提交工作，Run 负责承载工作生命周期。**

Stage 14 会把这个模型继续扩展到真正 Long-Horizon Task。

---

## 4. Queue 不是“以后再做”的抽象

只要提交和执行分离，中间就自然出现 `queued`。

这时服务需要考虑：如果请求来得比 Worker 处理得快怎么办？

最危险的答案是“先全部收下来”，因为内存、数据库、第三方 Rate Limit 和用户耐心都不是无限资源。

所以本章 `AgentService` 有：

```python
max_queued_per_tenant
```

队列满了以后抛出 `BackpressureError`。

Backpressure 不是“不够智能”，它是系统诚实地说：“我现在接不了更多工作。”比接受一百万个任务然后一起超时强得多。

---

## 5. 为什么 Backpressure 还要按 Tenant？

如果全局 Queue 只有 100 个位置，Tenant A 突然提交 100 个任务，Tenant B 的一个正常请求可能直接饿死。

所以本章最小示例按 Tenant 统计 Queue。

这还不是完整 Fair Scheduling，但它已经展示一个 Production 事实：

> **资源上限也需要作用域。**

和 Memory、Context、Permission 一样，Production Budget 不能永远只有一个 Global Counter。

---

## 6. Idempotent Submission：用户重试不应该自动创建两个任务

网络世界很喜欢发生这种事情：Server 创建 Run 成功，但 Response 在路上丢失；Client 以为失败，于是 Retry POST。

如果每次都创建新 Run，同一业务动作可能执行两次。

所以提交接口支持 Idempotency Key。本章 Store 用：

```text
UNIQUE(tenant_id, idempotency_key)
```

相同 Tenant + 相同 Key 再次提交，会返回原 Run。

为什么 Key 还要 Tenant Scoped？因为两个客户都写 `request-123` 不应该互相撞车。

---

## 7. Submission Idempotency 和 Tool Idempotency 不是一回事

Stage 09 已经学过 Side Effect Retry。这里又出现 Idempotency，但层级不同：

```text
Request Idempotency
    -> 不重复创建 Run

Tool Idempotency
    -> 不重复产生具体 Side Effect
```

你可以只创建一个 Run，但 Run 内部仍可能对支付服务重复退款；也可以 Tool 完全幂等，但客户端重发却创建两个独立 Run。

不同边界需要不同 Idempotency。

---

## 8. Durable Run Store：Status 不能只活在内存字典

一个最常见 Demo 是：

```python
runs = {}
```

服务器重启以后，所有用户突然集体失忆。

所以本章使用 SQLite 保存 `run_id`、`thread_id`、`user_id`、`tenant_id`、`status`、输入、输出和时间戳。

它不是在宣称 SQLite 是所有生产场景的最终答案，而是让一个关键语义真的成立：

> **Service Object 消失以后，Run Record 还在。**

之后可以把实现换成 Postgres 或其他 Durable Store，语义不应该跟着变。

---

## 9. Worker Claim 是 Queue 到 Execution 的边界

本章 Worker 调：

```python
run = store.claim_next()
```

把 `queued` 改成 `running`，然后执行，再变成 `completed`。

最小状态机：

```text
queued
    ↓
running
    ↓
completed
```

真实系统还会有 Failed、Cancelled、Waiting Approval、Expired 等状态，但不要一上来画 18 个状态。先把 Durable Status Transition 理解清楚。

---

## 10. `BEGIN IMMEDIATE` 为什么出现在教学代码里？

`claim_next()` 不能只是先 SELECT 一个 Queued，晚点再 UPDATE，因为两个 Worker 可能同时看见同一条 Run。

本章使用 SQLite Transaction 在选择和更新之间建立更强的串行边界。

这仍然不是分布式 Worker 的最终 Lease 方案。Stage 14 会专门讲 Lease、Heartbeat 和 Worker Loss。

这里先看到核心问题：

> **领取任务本身也是并发控制动作。**

---

## 11. Tenant Boundary 也要进入 Query

用户查 `GET /runs/{run_id}` 时，不能只写 `WHERE run_id = ?`，还要把 Tenant 放进条件：

```sql
WHERE run_id = ?
  AND tenant_id = ?
```

否则只要猜到别人的 Run ID，就可能读取跨 Tenant 状态。

本章跨 Tenant Lookup 返回“找不到”，而不是额外泄露“这个 Run 存在，只是你没权限看”。

---

## 12. Readiness 和 Liveness 不应该是同一个问题

Liveness 问“进程还活着吗？”

Readiness 问“它现在有能力接业务流量吗？”

一个进程可以活得很好，但数据库已经断了。此时应该是：

```text
live = yes
ready = no
```

本章 `store.ready()` 用一次最小 DB Query 检查 Durable Dependency。

生产服务还可能检查 Migration、关键配置和 Queue Connection。

不要把所有 Health Endpoint 都写成 `return {"status": "ok"}` 然后祈祷编排系统不较真。

---

## 13. Thin Service Boundary：HTTP 层应该尽量薄

一个比较健康的结构：

```text
HTTP / API
    ↓ parse request + trusted identity
AgentService
    ↓
RunStore / Queue
    ↓
Worker
    ↓
Bounded Agent Runtime
```

不要把 Router、RAG、Permission、Memory、SQL、模型调用全部塞进 `/chat` Handler。

HTTP Framework 应该主要处理协议输入输出、认证信息、状态码、请求大小和 Deadline。业务执行仍然属于内部 Service / Runtime。

这样以后从 REST 换成 Queue Consumer、CLI 或 A2A Endpoint 时，不需要把整个 Agent 复制一次。

---

## 14. “异步任务”不等于 Python `async def`

这里有一个术语陷阱。

`async def` 解决的是 Python 并发编程模型。

Async Job 解决的是：请求提交以后，工作可以脱离当前 Request 生命周期继续。

一个 `async def /run()` 仍然可能一直占着连接；一个 Durable Queue Job 即使 Worker 用同步 Python，也依然是异步业务任务。

```text
async Python
!=
durable asynchronous job
```

不要被同一个单词骗两次。

---

## 15. Graceful Shutdown：进程收到终止信号以后怎么办？

生产发布时旧进程会退出。如果它正在执行 Run，立刻 Kill 可能留下半完成状态。

更稳妥的思路是：停止接新任务、标记 Not Ready、等待或取消正在执行的有限任务、保存可恢复状态、最后退出。

本章标准库 Demo 没写完整 Signal Handler，因为长任务恢复属于下一章。但现在至少知道 Shutdown 是 Runtime Lifecycle 的一部分，不是容器平台自动送你的礼物。

---

## 16. Configuration 和 Secret 也应该来自服务边界

不要把生产配置写死在 Agent Prompt。Config 与 Secret 应由部署环境提供，再通过最小权限传给真正需要的组件。

Stage 12 已经看到，子进程也不应该默认继承所有 Environment。这条原则到了 Production 只会更重要。

---

## 17. Demo 的 Worker 故意很笨

本章 `run_one()` 只产生一条确定性输出。

为什么不把前面所有 Agent 功能复制进来？因为本章在教 Service Semantics。

真正项目里，这一行应该调用你已经有的 Bounded Agent Runtime。如果为了让 Demo “像 AI”，再塞一套新的简易 Agent Loop，反而会把章节重点弄乱。

---

## 18. 运行完整代码

```bash
python stages/13-production-deployment/code/demo.py
python stages/13-production-deployment/code/checks.py
```

Demo 会提交 Run、用相同 Idempotency Key 再提交、确认返回同一 Run、让 Worker 完成任务、重新创建 Service，再从同一 SQLite Store 读到 Completed Run。

检查覆盖 Trusted Identity、Request Idempotency、Tenant-scoped Idempotency、Per-tenant Backpressure、Cross-tenant Run Lookup、Restart Durability、Queued → Running → Completed 和 Readiness。

---

## 19. 为什么下一章是 Long-Horizon Harness？

现在 Run 已经可以脱离 HTTP Request，进入 Durable Queue。

但 `claim_next()` 还有一个很大的问题：Worker 领取任务后状态变成 Running，然后机器直接消失。谁把它捡回来？如果任务要跑两个小时，中途 Workspace 被回收怎么办？如何保存 Progress？如何让另一个 Worker 从 Durable State 重新接手？如何避免两个 Worker 同时认为任务属于自己？

这些都已经不是普通“请求处理”问题。

所以下一章 Stage 14，我们把 Run Queue 继续升级成 **Long-Horizon Agent Harness**。任务会拥有 Ledger、Lease、Heartbeat、Artifact 和可恢复 Work Unit。

Agent 终于开始学会“换班”。

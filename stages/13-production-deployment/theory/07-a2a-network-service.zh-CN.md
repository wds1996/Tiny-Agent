# 07 — A2A 作为真实 Network Service

> Language: [English](07-a2a-network-service.md) | 简体中文

Stage 11 介绍 Agent-to-Agent collaboration 与 A2A protocol concept。Stage 13 继续追问：当这个 Agent 真正变成一个网络服务，拥有 public discovery、authentication、task state、streaming、replica 与 shutdown 行为时，哪些 production concern 会出现？

> **Protocol compatible != production ready。**

---

## 1. Conceptual Server Stack

当前 A2A Python SDK server 可以按下面这些 responsibility 理解：

```text
Agent business logic
    ↓
AgentExecutor
    ↓
EventQueue / task events
    ↓
request handler
    ↓
TaskStore
    ↓
A2A route factory
    ↓
Starlette/FastAPI ASGI app
    ↓
Uvicorn / deployment
```

具体 helper/class name 属于 versioned SDK surface。Tiny-Agent 用显式 integration tests 覆盖这些 integration code，是为了避免教程把某一版 SDK snapshot“冻成永恒真理”。

先学 responsibility，再记 API。

---

## 2. Agent Card 是 Public Contract

Agent Card 会公布 capability 与 reachable endpoint。

如果外部 client 实际访问：

```text
https://agents.example.com/research
```

却在 card 里写：

```text
http://127.0.0.1:9999
```

那只是把 container 内部地址当成了公共世界地图。

Agent Card discovery 回答：

```text
什么 Agent/service 存在？怎样联系它？
```

它**不**回答：

```text
当前 caller 是否有权使用它的每项能力？
```

---

## 3. Discovery != Authentication != Authorization

和 MCP 一样：

```text
discovery
    -> endpoint/capability 信息

authentication
    -> 谁/什么在调用？

authorization
    -> 该 principal 能否对这个 task/resource 执行动作？
```

Public Agent Card 不是所有 backend Tool 的游客通行证。

---

## 4. Task ID 必须绑定 Ownership

Remote Agent 可能支持：create/send task、get task、cancel、resubscribe/stream。

知道 task ID 仍然不等于有权读取/取消它。

持久化 ownership：

```text
task_id
subject_id
tenant_id
created_at
status
```

并在 read/cancel/resume 时 enforcement。

---

## 5. `InMemoryTaskStore` 只是 Teaching Backend

单 process smoke test 可以用 in-memory store。

有 replica 后：

```text
request creates task on replica A
next request lands on replica B
```

如果 B 有另一个独立 in-memory store，task continuity 直接断掉。

Production Task/Event state 必须足够 shared/durable，才能兑现 protocol 对 client 的 promise。

---

## 6. Streaming / Resubscription 会改变 Storage Requirement

如果 client 可以断开后再订阅，progress 就不能只存在 live socket buffer 里。

```text
Agent execution
-> durable task state/events
-> stream projects updates to client
```

Stream 是 view；task record 才是 durable continuity boundary。

是否每个 event 都必须 replay，是 product/protocol contract 的选择。

---

## 7. Gateway / Middleware 仍然正常工作

A2A 服务依然可以放在：TLS termination、auth middleware、request-size limit、rate limit、WAF/network policy、logging/tracing 后面。

不要因为“Agent 在和 Agent 说话”就绕过普通 service control。

Agent 仍然是软件 client。它们不会因为名字里有 Agent，就在 load balancer 那里自动获得外交豁免权。

---

## 8. Shutdown / Drain

Host shutdown：

```text
stop admission
-> drain/persist task state
-> close handler/runtime resources
-> release leases
-> exit
```

Long-running work 应通过 durable task/checkpoint state 生存，而不是要求原 process 永远不被替换。

---

## 9. MCP + A2A + HTTP 是不同 Boundary

现实架构可能是：

```text
User/client application
       | HTTP
       v
Research product service
       | A2A
       v
Research Agent
       | MCP
       +--> search capability
       +--> document capability
       +--> database capability
```

可以理解为：

```text
HTTP -> product/service API
A2A  -> Agent collaboration/task protocol
MCP  -> capability/context protocol
```

不要强迫一个 protocol 包办所有 boundary。

---

## 10. Remote Delegation 示例

Supervisor 想让 specialist 做 citation analysis：

```text
Supervisor
-> discover CitationReview Agent Card
-> authenticate as service principal
-> send bounded task + evidence refs
-> receive remote task_id
-> persist mapping in local run state
-> stream/poll progress
-> receive artifact/result
-> validate before use
```

Remote Agent output 在 Host 决定如何使用之前，仍然是 external/untrusted data。

A2A 不会把 remote Agent 变成不会犯错的同事；它只是让同事变成了网络同事——反而更需要清晰 contract。

---

## 11. Version-aware SDK Usage

保持：

```text
protocol semantics
    -> stable mental model

SDK helper names
    -> versioned adapter + integration tests
```

旧教程和当前 tested SDK range 冲突时，以 current official docs 与仓库测试结果为准，不要把不同时代的 snippet 拼成一锅。

---

## Completion Principle

> **Deployed A2A Agent 本质上仍然是一个受到普通网络服务治理、但带有 Agent-specific task semantics 的 service，而不是 trust shortcut。Client 依赖哪些 continuity promise，就必须据此持久化 task ownership/state。**

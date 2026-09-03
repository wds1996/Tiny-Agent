# 08 — Authentication、Multi-Tenancy、Durable Jobs 与 Lease

> Language: [English](08-authentication-tenancy-and-durable-jobs.md) | 简体中文

Agent 加上 HTTP endpoint 后，仍然很常见两个生产缺口：

1. 身份来自 request body 自报；
2. 长时任务仍依赖某一个 web worker 一直活着。

这两件事都是 demo convenience，不是 durable production contract。

---

## 1. Authentication vs Authorization

```text
authentication
    = 谁/什么发起了请求？

authorization
    = 这个 principal 是否能对该 resource 执行该 action？
```

Tiny-Agent service path：

```text
credential
-> trusted authenticator
-> AuthenticatedIdentity(subject, tenant, roles)
-> normalized service/domain request
-> resource/Tool authorization
```

Request body 没资格重写 authenticated identity。

---

## 2. Reject Identity Smuggling

`bind_trusted_identity()` 保留：

```python
_RESERVED_IDENTITY_KEYS = {
    "subject_id",
    "tenant_id",
    "roles",
    "user_id",
}
```

```python
metadata = bind_trusted_identity(
    {"thread_id": body.thread_id},
    authenticated_identity,
)
```

如果 client metadata 试图提供 `tenant_id`，直接 `IdentityBindingError`。

这比“body tenant_id 看起来不太可疑时就相信它”容易审计得多。

---

## 3. Tenant Scope 属于 Resource Identity

不同 tenant 完全可能都有：

```text
user-17
thread-1
run-42
```

所以 ownership 往往需要同时包含：subject_id、tenant_id，以及必要时 workspace/project scope。

Tiny-Agent `require_owner()` 同时检查 subject 与 tenant，避免相同 user ID 在不同 tenant 中“意外成为室友”。

---

## 4. Long Work 需要 Durable Ownership

长 Agent 可能比 client connection、proxy timeout、deployment、web worker、sandbox/container 活得都久。

因此：

```text
POST /runs
-> durable job record
-> return run_id

worker claims run
-> executes
-> persists terminal result
```

Web process 是 admission/API layer，不是承诺“这个任务存在”的存储介质。

---

## 5. Lease State Machine

`SQLiteRunQueue` 教学模型：

```text
queued
  -> running(worker_id, lease_expiry)
      -> completed
      -> failed

running + expired lease
  -> claimable by another worker
```

Lease 表示：

> 这个 worker 在时间 T 前拥有执行权，前提是按 contract renew/finish。

它不是永恒 ownership。

---

## 6. Atomic Claim

教学实现使用 transaction：

```text
BEGIN IMMEDIATE
SELECT one queued/expired run
UPDATE -> running + owner + expiry
COMMIT
```

防止两个本地 worker 有意同时 claim 同一 queued row。

生产数据库/queue 可以有其他 atomic-claim primitive，但语义必须保留。

---

## 7. Stale Worker 不能 Complete 新 Owner 的 Job

场景：

```text
worker A claims
A stalls
lease expires
worker B claims
A wakes up and tries to complete
```

Terminal update 必须带：

```text
WHERE run_id=?
  AND status='running'
  AND lease_owner=?
```

A 已经失去 lease，就不能覆盖 B 的 ownership。

这防止“僵尸 worker”仅凭自己还记得 run ID 就回头改最终状态。

---

## 8. Exactly-once Warning

Lease 只解决 ownership coordination，不解决 exactly-once side effect。

```text
A sends email
-> crashes before marking completed
-> lease expires
-> B retries
-> email may be sent twice
```

还需要 operation-specific protection：idempotency key、transaction/outbox、API native idempotency、dedup record、risky repeat human review。

Durable queue 无法穿越时间，替你查清外部世界刚才到底有没有收到 side effect。

---

## 9. Run Queue vs Checkpoint vs TaskLedger

绝不能合并：

```text
Run queue
    = 哪个 service worker 拥有 logical job？

Agent checkpoint
    = orchestration 可以从哪里 resume？

TaskLedger
    = long-horizon run 内还有哪些 sub-work/progress？
```

一个生产 Agent 可以同时有：

```text
run-42 claimed by worker B
thread checkpoint at graph node "review"
TaskLedger: 7/10 subtasks complete
```

三者回答不同问题。

---

## 10. Cancellation 也有多个层

用户 cancel run-42：

```text
mark durable cancellation requested
-> worker stops new sub-work
-> cancel downstream MCP task if supported
-> stop sandbox safely
-> preserve useful artifacts
-> update checkpoint/ledger
-> publish cancelled terminal status
```

关闭浏览器标签页不是 durable cancellation protocol。

---

## 11. Tenant-safe Resume

```text
GET /runs/run-42
credential -> tenant-B/user-17
DB record  -> tenant-A/user-17 owns run-42
```

subject 相同也必须 deny，因为 tenant 不同。

合法 owner resume：load run -> claim/lease -> load checkpoint -> recover TaskLedger -> continue。

---

## Completion Checklist

解释 authentication vs authorization；为什么 body identity 不可信；tenant-scoped ownership；durable run vs web connection；lease claim/reclaim/stale worker；exactly-once limitation；run queue vs checkpoint vs TaskLedger；downstream cancellation。

核心 invariant：

> **Identity 来自 trusted server-side authentication boundary；durable job 把 ownership/progress 外置；lease 协调 worker，但不会把 side effect 变成 exactly-once。**

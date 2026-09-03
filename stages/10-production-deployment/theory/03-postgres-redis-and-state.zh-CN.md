# 03 — PostgreSQL、Redis 与 State Responsibility

> Language: [English](03-postgres-redis-and-state.md) | 简体中文

Infrastructure 名字不会自动定义 semantics。

在架构图里画一个绿色 Redis 方块和一个蓝色 PostgreSQL 圆柱，并不会让 state consistency 从像素里自然长出来。

先问 responsibility。

---

## 1. 先回忆 Stage 06

```text
Checkpointer = durable execution/thread state
Store        = selected cross-thread long-term memory
```

Stage 10 只是在部署环境中继续问：这些 abstraction 以及 job、ownership、audit、cache、coordination 分别应落在哪种 infrastructure。

---

## 2. PostgreSQL：Durable Transactional Truth

适合：run/job record、thread/checkpoint backend、long-term Store、user/tenant ownership metadata、audit ref、transactional transition、idempotency record、durable task/result metadata。

Relational transaction 可以保证同一逻辑单元中的多条 durable state 一起成功/失败。

不要只因为不同技术都有吉祥物，就把 correctness-critical state 随手拆散到多个系统。

---

## 3. Redis：Fast Shared Ephemeral Coordination

适合 distributed rate counter、TTL cache、short-lived coordination、carefully designed lease/lock、delivery semantics 合适的 queue/stream。

关键问题：

> **如果 Redis 丢掉这份数据，product contract 是否被破坏？**

如果会，就必须确认 Redis persistence/replication 是否足够，或者 durable truth 应放别处。

```text
cache != source of truth
```

---

## 4. In-memory State 无法跨 Worker

```python
sessions[thread_id] = state
```

单进程没问题；多 worker 时 request 1 在 A 写，request 2 到 B，B 的字典当然是空的。

这不是神秘 race condition——两个 worker 本来就是两个不同 process。

---

## 5. Connection Pool 也是 Resource Budget

```text
12 replicas × max_size 15 ≈ 180 app connections
```

还没算 migration/admin/other service。

“`max_size=100` 看起来很豪爽”不是 capacity planning。

Pool size 必须结合 replica/worker 数量设计。

---

## 6. DB Transaction != Distributed Exactly-once

Postgres transaction 无法把 email/payment API 一起变成同一个 ACID transaction。

常见模式：idempotency key、outbox/event record、state machine、reconciliation job。

例如先 transaction 写 email intent + task state，再由 worker 按 key 发送并标记 delivered。

---

## 7. Redis Fixed-window 教学 Limiter

Tiny-Agent 用小型 Lua script 让 `INCR` + 首次 `EXPIRE` 原子化，并在 key 中使用 identity hash。

它教的是 distributed counting，不是“世界最终版限流算法”。生产还可能需要 token bucket、sliding window、tenant quota、gateway enforcement、provider quota coordination。

---

## 8. Fail-open vs Fail-closed

Redis down 时 rate limiter 怎么办？

```text
fail-open  -> 优先 availability
fail-closed -> 优先 protection/quota correctness
```

没有 universal answer。低风险 demo 和昂贵/滥用敏感 operation 的取舍可以不同，但必须明确并可观察。

---

## 9. Cache Invalidation 与 Agent Context

缓存 Tool catalog/user memory 时要问 tenant scope、TTL、invalidator、stale permission/memory 是否会影响决策。

“速度很快，但读错 tenant”绝不算性能优化。

---

## 10. State Map 示例

```text
Postgres
  runs
  thread checkpoints
  artifact ownership metadata
  durable preferences

Redis
  tenant rate counters
  short-lived cache
  worker coordination

Object storage
  PDFs / generated artifacts

Model context
  selected slices only
```

每个系统都应该有语义理由，而不是只有 logo。

---

## Completion Checklist

你应能回答：哪些是 durable truth？哪些是 ephemeral coordination/cache？哪些 operation 要 transaction？Redis 消失会怎样？replica 总共多少 DB connection？cache key 是否带 tenant/owner scope？哪些 state 不该进入 model context？

核心 invariant：

> **根据 state semantics 与 failure requirement 选择 infrastructure；不要让 infrastructure 名字替代语义设计。**

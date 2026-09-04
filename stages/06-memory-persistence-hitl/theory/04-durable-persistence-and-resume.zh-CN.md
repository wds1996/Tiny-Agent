# Durable Persistence、Resume 与 Recovery

Stage 03 用 `InMemorySaver` 教了第一层 persistence：

```text
pause
  -> checkpoint in process memory
  -> resume
```

Stage 06 追问更难的问题：

> 如果 pause 与 resume 之间，整个 process 消失了呢？

如果答案是“那 approval workflow 全忘了”，你做的是戏剧化 pause button，不是 durable execution。

---

# 1. Persistence 是 runtime property，不是 Agent long-term memory

始终区分：

```text
Checkpointer
    -> persists thread execution state

Store
    -> persists selected cross-thread memory/data
```

它们完全可以都使用 PostgreSQL，但仍然做不同工作。

```text
same database technology != same application semantics
```

---

# 2. Durable checkpoint 带来什么

它可以支持：

- human review 几小时后 resume；
- process restart 后恢复；
- inspect thread history；
- fault recovery；
- time-travel/replay workflow；
- horizontal service deployment 中后续 request 落到另一 worker。

Lifecycle：

```text
runtime A
   ↓
execute step
   ↓
write checkpoint
   ↓
process dies / deployment happens / user goes home

... time passes ...

runtime B
   ↓
load same thread_id
   ↓
recover checkpoint
   ↓
continue
```

这与一个 process-local Python dict 是质的区别。

---

# 3. InMemorySaver vs SQLite vs Postgres

## InMemorySaver

```text
scope: one Python process
best for: unit tests, tutorials, local exploration
survives process restart: no
```

很适合学语义，不适合当 disaster-recovery plan。

## SQLiteSaver

```text
scope: local DB file
best for: local apps, experimentation, lightweight durable workflow
survives process restart: yes
shared multi-worker production backend: usually not first choice
```

教学特别好，因为可以真的 close 第一个 saver，再创建第二个，并证明 state 留在 file 中。

## PostgresSaver

```text
scope: shared DB service
best for: production-oriented durable workflow
survives process restart: yes
shared across workers: yes
```

但 production suitability 仍取决于 HA、backup、pooling、migration、retention、deployment 等真实运维设计。

类名叫 `PostgresSaver` 并不会顺便替你配置一支 SRE 团队。

---

# 4. SQLite restart 示例

见：

```text
code/sqlite_durable_checkpoint.py
```

核心 pattern：

```python
with SqliteSaver.from_conn_string(path) as first_saver:
    graph = build_graph(first_saver)
    graph.invoke({"count": 0}, config=config)

# first graph/saver objects are gone

with SqliteSaver.from_conn_string(path) as second_saver:
    graph = build_graph(second_saver)
    recovered = graph.get_state(config)
```

Checkpoint 属于 durable storage，而不是 original graph object。

---

# 5. Postgres `setup()` 是 schema initialization

当前 LangGraph Postgres persistence package 首次使用需要：

```python
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()
```

Store 同样：

```python
with PostgresStore.from_conn_string(DB_URI) as store:
    store.setup()
```

教程这样方便；生产中 schema create/migration 通常应是 deployment operation，而不是每个 request handler 的 surprise side effect。

用户只是发了句“hello”，web request 不应该因此被临时晋升为 DBA。

---

# 6. Thread identity 开始成为 infrastructure

Checkpoint durable 后，`thread_id` 就不再是随手写的 demo string。

它影响：

- recovery；
- user routing；
- privacy boundary；
- deletion；
- retention；
- support/debug tooling；
- idempotency / duplicate request。

好的 thread identifier 应：

- 对 logical execution 稳定；
- 足够 unique；
- 但不能本身被当作 authorization credential。

知道一个 thread ID，不应该自动获得读它 state 的权限。

---

# 7. Recovery 不等于 retry

假设 Agent：

```text
charge_credit_card()
```

调用完成后，下一 checkpoint commit 前 process crash。

Recovery 后 runtime 可能再次走到这一步。

因此 durable system 仍需考虑：

```text
at-most-once?
at-least-once?
exactly-once illusion?
idempotency key?
external transaction status?
```

Persistence 可以恢复 internal state。

它不会魔法般让 external side effect 与 checkpoint DB 成为同一 transaction。

---

# 8. Idempotency key

常见做法：

```python
idempotency_key = f"{thread_id}:{operation_id}"

payment_api.charge(
    amount=100,
    idempotency_key=idempotency_key,
)
```

如果 retry，external system 能识别同一 logical request。

其他策略：

- 重复前先查询 external status；
- outbox/transactional messaging；
- prepare/commit 分离；
- 让 operation 天然 idempotent。

Stage 09 会继续深入 reliability。

---

# 9. Checkpoint history / time travel

Checkpoint 形成 execution history，可用于：

- debug 某 route 为什么被选择；
- 比较 before/after state；
- 从旧 point replay；
- reproduction failure。

但 time travel 不是 external world 的时间机器。

如果 checkpoint 4 写着：

```text
email_sent = False
```

但现实世界中 email 已发出，replay internal state 不会让收件箱礼貌地把邮件“退回未发送状态”。

State replay 与 external side-effect replay 必须分开设计。

---

# 10. Serialization 是 persistence boundary

Durable checkpoint 必须跨 serialization boundary。

因此适合 state 的通常是：

```text
strings
numbers
booleans
lists
dictionaries
well-supported framework primitives
```

而不是任意 live object：

```text
open socket
DB cursor
thread lock
mystery vendor client
```

不能可靠 reconstruct 的东西，通常就不应该放进 durable execution state。

---

# 11. Deserialization 也是 security boundary

Persistence backend 之后还会 deserialize。

如果 checkpoint storage 被 compromise，而 serializer 又允许任意 object instantiate，风险会放大。

Tiny-Agent Stage 06 CI 对 Postgres persistence test 设置：

```bash
LANGGRAPH_STRICT_MSGPACK=true
```

更一般的原则：

> persisted workflow state 是跨 trust boundary 的 data，不是“反正是内部 bytes”。

除非真正理解 trust model，否则不要随便依赖 pickle-style fallback。

---

# 12. Retention 与 cleanup

Checkpointer 会积累一个 thread 的多个 checkpoint version。

生产问题包括：

```text
How long should completed threads remain?
How many checkpoint versions should be kept?
Do users have deletion rights?
How do backups age out?
What does legal hold mean?
What gets archived for audit vs deleted for privacy?
```

“我们用了数据库”不是 retention strategy。

---

# 13. Checkpoint migration

State schema 会演进。

今天：

```python
{"status": "pending"}
```

下个月：

```python
{
    "status": "pending_review",
    "approval_policy_version": 2,
}
```

旧 durable checkpoint 仍可能保留旧 shape。

成熟系统需要考虑：

- backward-compatible state reader；
- schema/version fields；
- migration strategy；
- 新 code 是否能 resume old thread。

Durability 的现实含义之一是：旧数据未来也有“投票权”。

---

# 14. Durable HITL 是 Stage 06 的核心演示

见：

```text
code/durable_hitl_resume.py
```

流程比 Stage 03 更强：

```text
runtime A
  -> prepare risky action
  -> interrupt
  -> checkpoint in SQLite
  -> close runtime A completely

runtime B
  -> recreate graph + saver
  -> same thread_id
  -> Command(resume=...)
  -> continue
```

Human 不需要在下一次 deploy 前赶紧点 approve。

这才是 durable interruption 的 operational meaning。

---

## 完成检查

你应该能解释：

1. Checkpointer vs Store，即使都用 PostgreSQL；
2. InMemorySaver vs SQLiteSaver vs PostgresSaver；
3. durable persistence 如何支持 restart recovery；
4. recovery 为什么不保证 external side effect exactly-once；
5. idempotency 为什么重要；
6. checkpoint replay vs external-world replay；
7. serialization/deserialization 为什么是 security boundary；
8. retention/schema migration 为什么属于 persistence design；
9. 什么让 HITL 从 process-local 变成真正 durable。
# 02 — Async、Concurrency、Deadline、Streaming 与 Backpressure

> Language: [English](02-async-concurrency-streaming.md) | 简体中文

`async` 是 Agent 教程里最容易被过度宣传的关键词之一。

它很有用，但它不是一个写上去就自动“更快”的咒语。

---

## 1. Async 擅长的是等待 I/O

典型场景：LLM API、HTTP、Postgres、Redis、MCP/A2A、object storage。

CPU-heavy Python 仍然需要 CPU。

可以把 event loop 想成一个服务很多桌的高效服务员：顾客大多数时间在吃饭，所以服务员可以轮流服务。突然有一桌要求：

> “你站在这里先帮我算十亿次矩阵乘法，算完再去管别人。”

这时再漂亮的 async 餐厅，也只剩一个极其敬业的服务员和四十桌生气的顾客。

Blocking work 放在 `async def` 里，仍然会 block event loop。

---

## 2. Sync Compatibility：Worker Thread

Tiny-Agent 用：

```python
value = await asyncio.to_thread(
    self._handler,
    request.input,
    payload,
)
```

把 sync handler 移出 event loop。

它提升 event-loop responsiveness，但不会让 thread 变得 hard-killable。

---

## 3. Timeout != Termination

例如 max concurrency=1，sync handler 在线程里跑 20 秒，request timeout=1 秒。

如果 1 秒时立刻返回 timeout 并释放 semaphore，第二个请求会启动，而第一个线程仍在工作——所谓 concurrency limit 就失真了。

Tiny-Agent 因此：

```python
output = await asyncio.wait_for(
    asyncio.shield(invocation),
    timeout=request_timeout,
)
```

Timeout 时 caller 收到失败，但 capacity 继续保留，直到 underlying thread 真正结束。

如果真的需要 hard termination，请换 process/container/job boundary。

---

## 4. Concurrency Limit vs Rate Limit

```text
concurrency limit = 当前同时跑多少？
rate limit        = 单位时间允许启动多少？
```

`asyncio.Semaphore` 只在单进程有效。4 个 worker 每个 8，就可能有约 32 个 in-flight run。

Distributed quota 需要 gateway/Redis 等 shared infrastructure。

---

## 5. Queue Timeout 阻止 Overload 变成隐形延迟

无界等待会：traffic spike -> queue grows -> memory/latency grows -> client timeout/retry -> traffic 再增加。

这就是服务“非常礼貌地排队把自己排进坑里”的过程。

Tiny-Agent 用 bounded semaphore acquire，把无限等待转换成明确 `ServiceCapacityError`。

---

## 6. Deadline 应该向内递减

```text
client deadline
  >= gateway deadline
  >= service run deadline
  >= Tool/model/downstream deadlines
```

Outer 10 秒、inner HTTP client 120 秒，会导致 caller 走了很久后 resource 仍在工作。

Dependency 支持时，应向内传播 deadline/cancellation。

---

## 7. Parallel Fan-out 必须有界

有界 subquestion 可以 `create_task`/`gather`。

坏情况：model 输出 5000 个 subquestion，系统创建 10000 个 HTTP task，然后通过一场行为艺术表演来“发现” provider rate limit。

Fan-out 应在 scheduling 前由 application budget 限制。

---

## 8. SSE Streaming

```text
event: run.started
data: {"run_id":"42"}

event: run.progress
data: {"step":3}

event: run.completed
data: {...}
```

一旦 header/stream bytes 已发送，后续错误通常不能再回普通 JSON HTTP 500 body。

因此需要 stream protocol event：

```text
event: run.error
data: {"code":"run_timeout"}
```

Event schema/order 应明确设计。

---

## 9. Backpressure

Streaming 不是：

```text
produce infinitely
-> 让 TCP 替系统带孩子
```

要考虑 slow client、proxy buffering、bounded queue、disconnect detection、cancellation、retention/replay、reconnect semantics。

Durable long-running work 中，stream 最好只是 durable run state 的**视图**，而不是 progress 唯一存在的地方。

---

## 10. `BackgroundTasks` 不是 Durable Queue

Framework background callback 适合小型 best-effort post-response work。

它不自动提供 durable enqueue、lease、retry、crash recovery、multi-worker coordination、dead-letter、cancellation semantics。

Process 返回 200 后若突然 crash，宇宙不会替丢失的 callback 给用户发一封道歉邮件。

---

## 11. Overload Case

4 workers × 每 worker 8 concurrency，大约可跑 32 Agent run；如果 provider 只允许 20 concurrent model call，而每个 Agent 又可能 fan-out，那么 local semaphore 根本无法控制全局 provider quota。

需要 layered control：

```text
gateway/tenant rate policy
+ process-local run concurrency
+ per-provider/model concurrency
+ bounded Agent fan-out
+ deadlines
```

一个 semaphore 管不了整个 distributed dependency graph。

---

## Completion Principle

> **Async 提高 I/O 并发能力，但 capacity 永远有限。Admission、fan-out、deadline 与 stream backpressure 应由真正拥有对应资源的层负责。**

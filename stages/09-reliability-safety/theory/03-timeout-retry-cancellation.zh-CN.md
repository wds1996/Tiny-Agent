# 03 — Timeout、Cancellation、Retry、Backoff 与 Fallback

> Language: [English](03-timeout-retry-cancellation.md) | 简体中文

一个可靠 Agent 不只问：

> Tool 失败了吗？

它真正应该问：

> **它是怎么失败的？我们已经等了多久？这个 operation 能不能安全重复？下一步应该是什么？**

---

## 1. Timeout 是“等待”这件事的 Budget

没有 timeout：

```text
Agent
  -> tool call
  -> waiting...
  -> waiting...
  -> waiting...
```

一个卡死 dependency 就能把整个 Agent 一起扣留。

Python 当前 `asyncio.wait_for()` / `asyncio.timeout()` 会在 deadline 超过后取消 overdue async work，并向调用者暴露 `TimeoutError`。

Stage 09 用同样思路包住 async Tool execution。

---

## 2. Async Timeout 与 Sync Timeout 不一样

真实 coroutine：

```python
await asyncio.wait_for(
    remote_call(),
    timeout=2.0,
)
```

Cancellation 可以传递进 task。

但 blocking sync function：

```python
def legacy_sdk_call():
    time.sleep(60)
```

如果直接在 event loop 中执行，会把整个 loop 堵死。

Tiny-Agent 因此把 sync handler 放进：

```python
asyncio.to_thread(...)
```

再对等待过程施加 async timeout。

这样 event loop 能保持响应。

但必须记住：

> **等待超时，并不会神奇地杀死 worker thread。**

底层 sync function 可能仍然在运行。

真正需要 hard termination 时，需要 process/container/VM 之类更强 boundary。

---

## 3. Cancellation 是 Control Flow

Caller 可能取消 Agent task，因为：

- 用户按了 Stop；
- HTTP request disconnected；
- deployment 正在 shutdown；
- parent workflow 取消了 branch。

Stage 09 不把 `asyncio.CancelledError` 转成：

```text
ToolFailure[internal_error]
```

Cancellation 应该继续向外传播。

否则 runtime 就变成：

> “我听见你说停止了，所以我把它记录成 warning，然后继续干。”

---

## 4. 只 Retry Transient Failure

适合 retry 的失败：

```text
temporary 503
connection reset
short-lived rate limit
transient service unavailable
```

通常不值得 retry：

```text
invalid arguments
permission denied
unknown tool
business rule violation
malformed schema
programming bug
```

Retry predicate 应该窄。

Tiny-Agent 用 typed exception 表示已知 retryable operational failure：

```python
TransientToolError(...)
ToolTimeoutError(...)
```

Unexpected exception 默认 non-retryable。

---

## 5. Retryable Failure != Retry-Safe Operation

这是最重要的 retry lesson。

例如：

```text
send_email()
    -> server accepted email
    -> network response lost
    -> client timeout
```

failure 看起来很 retryable。

但再调用一次，很可能发送两封邮件。

因此 Tiny-Agent 要求：

```text
failure.retryable
AND
tool_policy.retry_safe
```

才允许 scheduling next attempt。

`ToolExecutionPolicy` 甚至会拒绝这种构造：

```python
ToolExecutionPolicy(
    retry_policy=RetryPolicy(max_attempts=3),
    retry_safe=False,
)
```

目的是逼 developer 在打开 retries 之前先想清楚 duplicate side effect。

---

## 6. Idempotency Key 可以让更多操作 Retry-Safe

例如 payment-like operation：

```python
charge(
    amount=100,
    idempotency_key="thread-7:payment-2",
)
```

Downstream service 可以记住这个 logical operation，避免重复应用 business side effect。

因此：

```text
HTTP request repeated
```

不必等于：

```text
business action repeated
```

好的 idempotency design，就是让前者可以发生而不导致后者重复。

---

## 7. Exponential Backoff

服务过载时立即 retry 只会雪上加霜。

简单 backoff：

```text
0.5s
1.0s
2.0s
4.0s
...
```

Tiny-Agent 的小型 `RetryPolicy` 实现 bounded exponential backoff，便于学习公式。

生产 retry library 如 Tenacity 支持：

- stop by attempts；
- stop by elapsed time；
- fixed/random/exponential waits；
- exception predicates；
- result predicates；
- async retry；
- callbacks/logging。

Library 能帮你省 plumbing，但**不知道你的 business action 是否 idempotent**。

---

## 8. Jitter

假设 500 个 Agent worker 同时收到 503。

没有 jitter：

```text
all wait 1s
all retry together
all receive 503
all wait 2s
all retry together
```

恭喜，客户端们成功组成了一支“同步拒绝服务合唱团”。

Jitter 加一点随机性，让 retries 分散开。

Tiny-Agent 会显式建模它。

---

## 9. Retry Budget 与 Per-call Attempts 要分开

单个 Tool：

```text
max_attempts = 3
```

整个 Agent run 还需要 global retry budget。

否则十个 Tool 各 retry 三次，整体负载远高于预期。

所以 Stage 09 区分：

```text
per-tool retry policy
```

与：

```text
run-wide BudgetLedger.max_retry_attempts
```

两边都允许，才可以继续 retry。

---

## 10. Fallback != Retry

Retry：

> 再做一次同样操作。

Fallback：

> 换一个 implementation 或 degraded mode。

例如：

```text
primary search API fails
    -> fallback cached index
```

```text
premium model unavailable
    -> fallback smaller model
```

但 fallback 同样需要 policy：small model 可能不满足原质量/安全要求，backup source 可能 stale。

不要写：

```text
if anything fails:
    silently use something else
```

Silent degradation 很难 debug，也很难 eval。

Stage 09 聚焦 retry/timeout mechanism；Stage 10 会让 fallback/degradation 可观察。

---

## 11. 一个更好记的比喻

Retry 就像敲门后没听见回应，于是再敲一次。

Retry `delete_database()` 则更像：你不确定第一锤有没有把窗户砸碎，所以决定再抡一锤。

机制一样，policy 完全不同。

---

## Code to Inspect

- `src/tiny_agent/reliability.py`
- `src/tiny_agent/guarded_runtime.py`
- `code/retry_policy.py`
- `code/guarded_tool_runtime.py`

运行：

```bash
python stages/09-reliability-safety/code/retry_policy.py
python stages/09-reliability-safety/code/guarded_tool_runtime.py
```

---

## 完成检查

解释：

1. timeout vs cancellation；
2. 为什么 sync thread timeout 不是 hard termination；
3. retryable failure vs retry-safe operation；
4. 为什么 idempotency key 重要；
5. exponential backoff 与 jitter；
6. per-tool retry attempts vs global retry budget；
7. retry vs fallback；
8. 为什么 cancellation 应传播，而不是普通 `ToolFailure`。

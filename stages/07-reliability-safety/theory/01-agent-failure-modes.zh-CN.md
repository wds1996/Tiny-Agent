# 01 — Agent Failure Modes 与 Safe Error Model

> Language: [English](01-agent-failure-modes.md) | 简体中文

Stage 07 从一个听起来很无聊、但非常能避免线上“精彩事故”的事实开始：

> **Failure 是 Agent protocol 的正常组成部分，不是一个应该羞于承认的异常分支。**

Demo 往往长这样：

```text
model proposes tool
    -> tool succeeds
    -> model continues
```

生产环境更像：

```text
model proposes tool
    -> malformed arguments
    -> permission denial
    -> network timeout
    -> 429 / 503
    -> partial side effect
    -> provider bug
    -> repeated call loop
    -> internal exception containing secrets
```

如果所有情况最后都变成：

```python
except Exception as exc:
    return str(exc)
```

那这个 runtime 并没有 failure model，它只是给 stack trace 修了一间“忏悔室”，然后把所有内部细节念给模型听。

---

## 1. 为什么 Stage 01 的 Error Handling 是故意不完整的？

最早的 Tiny-Agent runtime 先教一个核心概念：

```text
tool failure
    -> observation
    -> model can recover
```

这对理解 ReAct 很重要。

但早期 integrated runtime 会把 arbitrary exception text 直接复制进 model transcript。

例如：

```python
raise RuntimeError(
    "postgresql://admin:super-secret@prod-db/internal"
)
```

Naive observation 变成：

```text
ToolError[RuntimeError]:
postgresql://admin:super-secret@prod-db/internal
```

于是一次内部 diagnostic，直接升级成了 model context。

Stage 07 把边界改成：

```text
known operational failure
    -> deliberately safe message may cross boundary

unknown exception
    -> generic safe message
    -> internal exception type retained for audit
    -> raw message stays internal
```

---

## 2. Typed Failure 回答的是 Operational Question

有用的 failure model 至少要能回答：

```text
What happened?
Can it be retried?
Can the model see a safe explanation?
Should execution stop?
Should a human be involved?
```

Tiny-Agent 使用类似：

```text
invalid_arguments
unknown_tool
permission_denied
approval_required
timeout
transient_error
permanent_error
budget_exceeded
loop_detected
internal_error
```

这些 code 是 application control data。

它们远比让模型从一句：

```text
"Oops, network maybe failed? Try again if you feel like it."
```

里自己猜 retry policy 更可靠。

---

## 3. `SafeToolError`

已知 application failure 可以显式声明一条经过 sanitize 的 message：

```python
from tiny_agent import TransientToolError

raise TransientToolError(
    "Upstream service is temporarily unavailable."
)
```

它可以变成：

```text
ToolFailure[transient_error]:
Upstream service is temporarily unavailable.
```

这个类叫 `SafeToolError`，而不是 `PublicException`，就是为了强调 contract：

> Developer 已经明确决定，这条 message 可以安全跨越 model boundary。

不要这样做：

```python
raise TransientToolError(str(raw_provider_exception))
```

那只是给不干净的 payload 套了一个看起来更干净的 class name。

---

## 4. Unknown Exception 必须 Redact

默认 classifier：

```python
failure = failure_from_exception(exc)
```

遇到：

```python
RuntimeError("secret-token=abc123")
```

模型只看到：

```text
ToolFailure[internal_error]: Tool execution failed.
```

内部 metadata 可以保留：

```text
internal_exception_type = RuntimeError
```

为什么保留 type？因为 Stage 08 observability 需要回答：

```text
Which internal exception types are rising?
Which tool is failing most often?
How many failures are transient vs permanent?
```

模型并不需要完整 stack trace 才能向用户解释失败。

---

## 5. Retryable 与 Retry-Safe 是两个维度

这是本章最重要的区分之一。

一个 timeout 可以属于：

```text
retryable failure
```

但这次 operation 可能不是：

```text
retry-safe action
```

例如：

```text
charge_card($100)
    -> client times out
```

到底是 payment 没成功？还是 server 已经扣款，只是 response 丢了？runtime 不知道。

因此：

```text
failure.retryable == True
```

**绝不足以**决定 retry。

Tiny-Agent 还要求：

```text
ToolExecutionPolicy.retry_safe == True
```

典型 retry-safe：

- read-only GET-like operation；
- 带 downstream idempotency key 的 operation；
- 明确设计成可容忍 duplicate 的 application operation。

默认不安全：

- send email；
- charge payment；
- delete resource；
- publish release；
- 没有 idempotency key 的 create operation。

---

## 6. Expected Failure vs Bug

不要因为“重试一次测试通过了”，就把所有错误都归为 transient。

例如：

```python
def calculate(x):
    return None + x
```

产生 `TypeError`。

这更像 code bug，而不是：

```text
invalid user arguments
```

Stage 07 故意不猜“每一个 `TypeError` 都一定来自坏 ToolCall”。

正确顺序：

```text
schema validation before execution
        ↓
known operational errors typed explicitly
        ↓
unexpected exceptions -> internal_error
```

这样才能保留 diagnostic integrity。

---

## 7. Failure Class 不是 User-facing UX

Model-safe observation 仍然可能过于技术化。

内部 observation：

```text
ToolFailure[permission_denied]:
Principal does not have an allowed role for this tool.
```

最终 user response 可以是：

```text
I can't perform that operation with the current permissions.
```

要区分三个 audience：

```text
runtime
    -> structured code / retryability

model
    -> safe operational observation

engineer
    -> detailed logs / traces / stack
```

不要把它们压成一个字符串。

---

## 8. 一个更容易记住的比喻

Exception stack trace 很像服务器自己的日记。

对 engineer 有用吗？当然。

打印机卡纸时，有必要把整本日记复印给每一次模型调用吗？通常没有。

---

## Code to Inspect

- `src/tiny_agent/reliability.py`
- `src/tiny_agent/runtime.py`
- `code/error_model.py`

运行：

```bash
python stages/07-reliability-safety/code/error_model.py
```

---

## 完成检查

解释：

1. 为什么 arbitrary `str(exc)` 不应进入 model context；
2. typed safe error 与 arbitrary exception 的区别；
3. retryable failure vs retry-safe operation；
4. 为什么 unknown `TypeError` 不应自动归类成 input error；
5. model-safe observation vs developer log；
6. 为什么在 Stage 08 observability 前就需要 structured failure code。

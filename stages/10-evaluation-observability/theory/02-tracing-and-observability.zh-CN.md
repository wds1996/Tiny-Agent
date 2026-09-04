# 02 — Tracing 与 Observability

> Language: [English](02-tracing-and-observability.md) | 简体中文

Stage 09 让 execution 更安全。Stage 10 接下来必须回答：

> 一次 Agent run 内部到底发生了什么？

当 execution 中有 nested model call、retrieval、Tool call、retry、interrupt 与 remote service 时，打印几行 `print()` 已经不够了。

---

## 1. Logging、Metrics、Tracing、Evaluation

### Logging

```text
2026-09-02 14:03 tool=search status=ok
```

适合 discrete record 与 diagnostics。

### Metrics

```text
tool_calls_total = 12842
p95_latency = 2.4 s
error_rate = 0.7%
```

适合 aggregate system behavior。

### Tracing

```text
invoke_agent
├── model_call
├── retrieval
└── execute_tool search
    └── retry
```

适合解释一次 execution 的 causal structure。

### Evaluation

```text
answer_correctness = 0.9
trajectory_policy_ok = 1.0
```

用于按明确 criterion 判断行为。

一个 tracing UI 有再漂亮的嵌套方框，也不会自动证明 Agent 做得很好；它只代表你现在能以更漂亮的方式看见这些方框。

---

## 2. Trace 与 Span

**Trace** 表示一次 end-to-end execution。

**Span** 表示 trace 中一个有时长的 operation。

```text
Trace: user task #123

Span A: invoke_agent
Span B: model decision
Span C: retrieval
Span D: execute_tool
```

典型 span 需要：

```text
trace_id
span_id
parent_span_id
name
start/end time
status
attributes
```

Tiny-Agent `SpanRecord` 就是这个最小模型。

---

## 3. Parent-child Structure 是关键

没有 parent relationship，只知道：

```text
model = 400 ms
tool  = 900 ms
retrieval = 150 ms
```

却不知道哪个 model call 触发哪个 ToolCall。

有结构：

```text
invoke_agent
├── decide
│   └── model
├── retrieve
└── execute_tool search
    ├── attempt 1
    └── attempt 2
```

才有因果可解释性。这也是 tracing 与普通 timestamp logging 的根本差别。

---

## 4. Context Propagation

Nested operation 必须知道 current parent。

`LocalTracer` 使用 Python `ContextVar`：

```python
with tracer.span("agent"):
    with tracer.span("tool"):
        ...
```

Child 自动继承 trace ID，并记录 current span 为 parent。

在 async server 中，一个全局：

```python
CURRENT_SPAN = root
```

很危险。Concurrency 一来，很容易出现：

> “恭喜，Alice 的 ToolCall 现在成了 Bob 的 Agent trace 的 child。”

---

## 5. Span Name vs Attribute

优先把稳定 operation category 放 attribute：

```text
gen_ai.operation.name = execute_tool
tool.name             = search
```

span name 可用：

```text
execute_tool search
```

不要把无限长度 user content 塞进 span name：

```text
BAD: span name = user's 4000-token question...
```

会造成 high cardinality、敏感内容泄漏、昂贵索引和不可读 dashboard。

---

## 6. Raw Prompt Capture 是 Privacy Decision

Naive tracer：

```python
span.set_attribute("prompt", full_prompt)
span.set_attribute("output", full_output)
```

可能把 credentials、PII、proprietary docs、internal prompts、memory、Tool result、customer data 全复制到 telemetry backend。

所以 Tiny-Agent 默认：

```python
TraceCapturePolicy(
    capture_inputs=False,
    capture_outputs=False,
)
```

必须显式 opt-in。

---

## 7. Opt-in 之后仍然需要 Redaction

例如：

```python
{
    "api_key": "sk-...",
    "query": "hello"
}
```

应变成：

```python
{
    "api_key": "<redacted>",
    "query": "hello"
}
```

并对超长 string truncate。

这是教学安全层，不是完整 enterprise DLP。生产还可能需要 field allowlist、data classification、PII detector、pseudonymization、retention、regional storage 与 trace backend access control。

---

## 8. Unknown Object 不要 Blind `repr()`

某 SDK object：

```python
def __repr__(self):
    return "Client(api_key='secret', endpoint='internal')"
```

Generic serializer 如果 `repr(value)`，就可能泄密。

Tiny-Agent 对未知对象默认只保留：

```text
<ClassName>
```

除非 application 显式提取 safe attributes。

Observability 应让 failure 可见，而不是让 secret 可见。

---

## 9. Observe Policy，不要 Duplicate Policy

```text
ObservedGuardedToolExecutor
        ↓
GuardedToolExecutor
```

Observed layer 记录 Tool name、attempt、status、safe failure code、latency。

它不决定 validation、permission、approval、retry safety、budget。

如果 telemetry 变成第二套 permission engine，那么“关闭 tracing”甚至可能把 security 一起关闭。这种 coupling 必须避免。

---

## 10. Failure Telemetry 保留 Classification，不保留 Secret Text

Stage 09：

```text
ToolFailure[internal_error]: Tool execution failed.
```

Stage 10 记录：

```text
error.type = internal_error
```

而不是 raw connection string/password。

Operationally 真正常问的是 timeout 数量、permission denial 数量、哪个 Tool transient failure 高，而不是“把所有 exception 全文塞进 trace”。

---

## 11. Trace != Audit Log

Audit log 通常要求：who、what authorized、exact resource identity、tamper resistance、retention、completeness、legal/compliance contract。

Observability trace 却可能被 sampled、dropped、redacted、短期保留。

所以：

```text
Trace != Audit Log
```

两者可共享数据，但 contract 不同。

---

## 12. Sampling

小规模可 trace 100%。大规模则可能昂贵。

```text
head sampling
    trace 开始时决定

tail sampling
    看见更多 trace 后决定

priority sampling
    failure/high-risk 保留更多
```

通常希望优先保留 error、policy denial、high latency/cost、unusual trajectory，以及一部分 normal success。

但 sampled telemetry 不是完整 count；aggregate metric 需要独立语义。

---

## 13. High-cardinality Attribute

例如：

```text
user_id
thread_id
document_id
Tool arguments
URL
prompt hash
```

都可能让 index cardinality/cost 爆炸。

问题不是“能不能 attach”，而是“真的需要在 backend 里 query/group by 它吗？”

只保留能支持具体 debugging/eval use case 的 attribute。

---

## 14. 先 LocalTracer，再 OpenTelemetry

Tiny-Agent 先实现：

```text
SpanRecord
InMemorySpanSink
LocalTracer
```

让你先理解 identity、hierarchy、timing、attributes、capture policy、sink/export boundary。

然后 OpenTelemetry 才会显得是成熟 generalization，而不是一团 instrumentation 魔法。

```text
Application operation
      -> instrumentation
      -> span/log/metric API
      -> processor
      -> exporter
      -> backend
```

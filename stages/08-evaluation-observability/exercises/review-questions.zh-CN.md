# Stage 08 复习、编程与面试练习

> Language: [English](review-questions.md) | 简体中文

阅读全部理论并运行每个 example 后完成。

---

## A. 核心概念

1. 解释 logging、tracing、metrics、evaluation、audit logging 的区别。
2. trace 与 span 有什么区别？
3. 为什么 span 需要 `parent_span_id`？
4. 为什么 async server 里一个 global `CURRENT_SPAN` 不安全？
5. 为什么 Tiny-Agent 默认关闭 raw input/output trace capture？
6. 为什么 generic telemetry serialization 中 `repr()` 可能危险？
7. 为什么 tracing 不应该变成第二套 authorization engine？
8. 为什么 trace 不能证明 Agent behavior 正确？
9. 为什么 tracing dashboard 不自动等于 evaluation platform？
10. 为什么 final answer 正确仍然可能是 Agent failure？

---

## B. Trace Design

对每个事件判断更适合 span、metric、log/event-like record、evaluation score 还是 audit record，并解释：

1. `invoke_agent` 用时 1.8s。
2. Tool `search` 返回 HTTP 503。
3. 用户批准 production deployment。
4. 最近五分钟 `tool_calls_total`。
5. Candidate answer helpfulness=0.86。
6. Model 输出 2,430 tokens。
7. API key 被 rotated。
8. Agent 500ms 后 retry Tool。
9. Agent 使用 forbidden capability。
10. p95 latency 超过 SLO。

---

## C. Privacy / Telemetry

1. 为什么 prompt 不应自动写入 trace attribute？
2. 设计一个比 teaching redactor 更严格的 allowlist capture policy。
3. 下面数据 export 前应怎样处理？

```python
{
    "authorization": "Bearer abc",
    "question": "hello",
}
```

4. 区分 redaction、pseudonymization、encryption、retention。
5. 为什么 observability backend 会成为高价值攻击目标？
6. 什么是 high-cardinality telemetry？举三个 Agent 例子。
7. 为什么不能把 full user prompt 当 span name？

---

## D. Tool Evaluation

Expected：

```python
ToolInvocation("weather", {"city": "Tokyo"})
```

分别判断：

```python
weather(city="Tokyo")
calculator(expression="Tokyo")
weather(city="Osaka")
weather(city="Tokyo"), search(q="Tokyo weather")
```

哪些影响 Tool precision、recall、argument accuracy、efficiency？

---

## E. Trajectory Evaluation

Reference requirement：

```text
search -> read -> summarize
```

Forbidden Tool：`delete_file`；max Tool calls=4。

分析：

```text
1. search -> read -> summarize
2. search -> inspect_metadata -> read -> summarize
3. read -> search -> summarize
4. search -> delete_file -> read -> summarize
5. search -> search -> search -> read -> summarize
```

逐个讨论 required-sequence recall、policy compliance、efficiency，以及 exact matching 是否公平。

---

## F. Offline vs Online Evaluation

判断主要属于 offline、online 或两者：

1. release 前比较两个 prompt；
2. monitor live latency drift；
3. replay previous production incident；
4. score thumbs-up/down feedback；
5. test new Tool schema；
6. detect real production prompt-injection attempt；
7. build gold reference set；
8. sample real conversations for LLM judge。

解释原因。

---

## G. Dataset Design

为拥有以下 Tool 的 Agent 设计 `EvalExample`：

```text
search_docs
read_doc
create_ticket
send_email
```

至少包括：2 个 happy path、1 个 no-Tool、1 个 wrong-argument trap、1 个 forbidden-action safety case、1 个 previous-bug regression、1 个 ambiguous case、1 个 long-tail case。

每个 case 写：input、reference output（若适用）、expected Tools、reference args（若适用）、required sequence、forbidden Tools、max Tool calls、metadata/split。

---

## H. LLM-as-Judge

1. 为什么 LLM judge 不是 ground truth？
2. 举一个 deterministic code 明显更好的评价任务。
3. 举一个 LLM judge 合理的任务。
4. 写一个基于 retrieved evidence 的 factual-faithfulness rubric。
5. 怎样对 human label calibration？
6. pairwise judging 的 position bias 是什么？
7. 为什么 evaluated text 本身可以 prompt-inject judge？
8. 为什么 online LLM judge 通常应该 sampling，而不是每 trace 都跑？
9. 为 reproducibility 应记录 judge 的哪些 model/config？

---

## I. Regression Gate

Baseline：

```text
execution_success = 1.00
quality           = 0.94
tool_f1           = 0.97
safety            = 1.00
latency_ms        = 900
cost_task_usd     = 0.015
```

Candidate A：

```text
execution_success = 1.00
quality           = 0.96
tool_f1           = 0.96
safety            = 1.00
latency_ms        = 1150
cost_task_usd     = 0.018
```

Candidate B：

```text
execution_success = 1.00
quality           = 0.98
tool_f1           = 0.98
safety            = 0.99
latency_ms        = 850
cost_task_usd     = 0.014
```

回答：

1. 哪个 automatically better？
2. safety 是否应 hard gate？
3. 提出 absolute thresholds。
4. 提出最大 allowed regression。
5. 哪些 higher-is-better，哪些 lower-is-better？

---

## J. Missing Metric Coverage

100 examples：50 crash，50 finish，所有 finished correctness=1.0。

1. execution-success rate？
2. scored examples correctness mean？
3. correctness coverage？
4. 为什么只报告 `correctness=1.0` 会误导？
5. regression gate 应如何处理？

---

## K. OpenTelemetry

1. 解释 `Tracer -> Span -> SpanProcessor -> SpanExporter`。
2. OTel 解决了 LocalTracer 没解决的什么问题？
3. OTel **没有**解决 Agent evaluation 的什么问题？
4. 为什么 2026 Stage 08 不新增 `Span.add_event()`？
5. event-like telemetry 的新方向是什么？
6. 为什么 GenAI semantic convention 要当 versioned/evolving？
7. 为什么 Tiny-Agent-specific attribute 放 project namespace？

---

## L. LangSmith

用自己的话解释：

```text
trace/run
dataset
experiment
evaluator
feedback
online evaluation
```

再映射到 Stage 08 handwritten abstraction。

为什么 CI 用 `@traceable` + `tracing_context(enabled=False)`？

---

## M. 编程练习

### Exercise 1 — Latency Evaluator

实现：

```text
1.0 if latency <= 1000 ms
0.5 if latency <= 2000 ms
0.0 otherwise
```

并解释为什么仍要单独保留 raw latency。

### Exercise 2 — Forbidden Sequence

扩展 `TrajectoryEvaluator`，拒绝：

```text
read_secret -> send_email
```

即使两个 Tool individually allowed。

### Exercise 3 — Numeric Argument Tolerance

让：

```text
100
100.0
```

等价，同时仍拒绝 string。

### Exercise 4 — Trace Metrics

从 `SpanRecord` list 计算：

```text
tool_call_count
failed_span_count
total_tool_duration_ms
```

### Exercise 5 — Dataset Slices

按：

```python
example.metadata["category"]
```

报告 grouped mean metrics。

### Exercise 6 — Judge Calibration

给 100 human binary labels 和 100 LLM-judge labels，计算 precision、recall、F1，并列出 disagreement examples。

### Exercise 7 — CI Gate

写 script：当 `RegressionGateResult.passed` 为 false 时 non-zero exit。

---

## N. 面试题

1. 怎样评价 Agent，而不是普通 chatbot？
2. 什么是 trajectory evaluation？
3. 为什么 exact trajectory matching 可能太严格？
4. 怎样测 Tool-selection quality？
5. offline vs online evaluation？
6. 什么时候用 LLM-as-judge？
7. 怎样 validate LLM judge？
8. 怎样防被评估文本 prompt-inject evaluator？
9. 怎样决定保留哪些 telemetry？
10. OpenTelemetry 与 LangSmith 区别？
11. tracing 与 evaluation 什么关系？
12. 为什么 p95/p99 latency 有用？
13. 怎样在 CI 检测 quality regression？
14. metric coverage 为什么重要？
15. Stage 07 budget 与 Stage 08 metric 如何互补？

---

## Completion Checklist

你应该不看笔记解释：

```text
trace != metric != evaluation != audit log
final answer quality != trajectory quality
Tool selection != Tool arguments
Offline eval != online eval
LLM judge != oracle
OpenTelemetry != LangSmith
observability != authorization
```

并能够搭建可重复的：

```text
dataset -> target -> evaluator -> report -> regression gate
```

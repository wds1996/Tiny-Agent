# 07 — OpenTelemetry、LangSmith 与 Production Observability

> Language: [English](07-opentelemetry-langsmith-and-production.md) | 简体中文

在先理解 local mechanism 后，本章把它映射到两个解决不同层问题的 mainstream tool。

---

## 1. OpenTelemetry：Vendor-neutral Telemetry Infrastructure

OpenTelemetry 提供统一概念：traces、metrics、logs、context propagation、processors、exporters。

简化 tracing path：

```text
application
    -> Tracer
    -> Span
    -> SpanProcessor
    -> SpanExporter
    -> backend
```

Tiny-Agent local mapping：

```text
LocalTracer -> SpanRecord -> SpanSink
```

---

## 2. 为什么使用 OpenTelemetry？

优势：vendor-neutral instrumentation、cross-service context、existing exporters/backends、ecosystem integration、semantic conventions，以及未来 Stage 13 service tracing。

但 OTel 不会自动告诉你：

```text
calling this Tool was the correct decision
```

它能告诉你 `execute_tool took 830ms`，前者仍是 evaluation 问题。

---

## 3. GenAI Semantic Conventions

当前 conventions 包括 `invoke_agent`、`plan`、`retrieval`、`execute_tool` 等 operation concept。

Tiny-Agent 只用小而清楚的 subset，把项目字段放在 `tiny_agent.*` namespace，并记录 convention version。

不要把每一个当前 OTel attribute 复制成 domain model；telemetry naming 未来可能变化，domain model 应该活得更久。

---

## 4. 2026 Span Events API 变化

OpenTelemetry 2026 年 3 月宣布 deprecate Span Events API。

方向：

```text
old new-code pattern: span.add_event(...)
recommended: log-based event correlated with current span
```

所以 Stage 10 不新增 `Span.add_event()` / `Span.record_exception()` instrumentation。

Operation 保持 span；event-like record 在 Stage 13 扩展 telemetry 时使用 correlated log。

旧数据不会突然失效，只是新 instrumentation 应跟随新方向。

---

## 5. OTel Success/Error Status

Tiny-Agent local span 有 `unset/ok/error`；OTel adapter 对 error 用 `StatusCode.ERROR`，成功不强制设置显式 OK，因为 OTel 常允许 successful span 保持 unset。

Adapter 应保留 semantic intent，而不是强迫两个 library enum 一模一样。

---

## 6. Nested Attribute 为什么要 Serialize？

OTel span attribute 不是任意 nested Python dict。

Tiny-Agent sanitized object 如：

```python
{"filter": {"type": "report"}, "top_k": 3}
```

必要时会转 stable JSON string。

真正需要 query 的字段，生产 semantic convention 更适合 explicit scalar：

```text
retrieval.top_k = 3
```

不要把整个巨大 object dump 到一个 attribute。

---

## 7. LangSmith：Agent/LLM-oriented Tracing + Evaluation Workflow

映射：

```text
trace/run    -> 一次 execution + nested operations
dataset      -> evaluation examples
experiment   -> target × dataset + evaluator scores
online eval  -> selected production runs/threads
feedback     -> attached human/programmatic signals
```

因此我们是在学完 `RunArtifact/EvalExample/EvaluationSuite` 后才引入 LangSmith。

---

## 8. `@traceable`

```python
from langsmith import traceable

@traceable(name="research_agent")
def run_agent(question):
    ...
```

Nested `@traceable` 自动形成 child run，与 LocalTracer parent-child concept 一致。

---

## 9. Runtime Tracing Control

环境配置：

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=tiny-agent-stage10
```

也可以：

```python
with tracing_context(enabled=False):
    ...
```

Tiny-Agent CI 用 disabled context，所以可测试当前 API，同时不需要 API key、不上传 trace、不依赖 network。

---

## 10. LangSmith Offline Evaluation

```text
dataset -> target -> evaluators -> experiment -> analysis
```

Evaluator 可用 deterministic code、human、LLM judge、pairwise comparison。

Platform 增加 persistence、visualization、comparison、collaboration、production workflow；基础 eval design 仍由你定义。

---

## 11. Online Evaluation

Production trace 可采样评价 reference-free quality、policy、user feedback、failure、latency/cost；有价值 failure 再沉淀成 offline dataset，形成闭环。

---

## 12. OpenTelemetry vs LangSmith

不是二选一竞争关系。

```text
Application
   +--> OpenTelemetry -> general infra/backend
   +--> LangSmith      -> Agent-specific debugging/experiments
```

| Concern | OpenTelemetry | LangSmith |
|---|---|---|
| vendor-neutral telemetry | strong | 非主要目标 |
| distributed tracing | strong | Agent-focused |
| Agent trace UI | 取决于 backend | built for it |
| datasets/experiments | 非主要目标 | built in |
| LLM evaluators | 非主要目标 | built in |
| online Agent eval | 需外部系统 | built in |
| export ecosystem | broad | platform-oriented |

---

## 13. Observability 不能破坏 Stage 09 Security

“只是 telemetry”不是泄露 secret 的理由。

要审查 prompt/input capture、Tool args、retrieved docs、headers/tokens、memory、user IDs、retention、backend access。

Instrumentation 本身就是另一条 data pipeline。

---

## 14. Sampling 与 Cost

100% capture 所有 LLM I/O 会消耗 bandwidth、ingestion、storage、indexing、privacy review。

例如可以：

```text
trace 20% normal
trace 100% errors
run deterministic online graders on 100%
run LLM judge on 2%
```

比例产品自定。**Trace sampling 与 evaluation sampling 是两个独立决定。**

---

## 15. Traces / Metrics / Logs / Eval / Audit

```text
Traces -> causal execution debugging
Metrics -> aggregate health/SLO
Logs -> event records/diagnostics
Evaluation records -> quality measurements
Audit logs -> security/compliance evidence
```

强迫一张表同时承担所有职责，只会制造混乱的 retention/trust contract。

---

## 16. Stage 10 Production Rule

> **Instrumentation 应让我们能够解释 behavior，Evaluation 应按显式 criteria 判断 behavior，而 telemetry 本身也必须处在 privacy/security boundary 内。**

看不见系统很难 debug；看得见但从不评价，只是把谜团记录得更完整。

# 07 — OpenTelemetry, LangSmith & Production Observability

After building the local mechanism, Stage 08 maps it to two mainstream tools that solve different layers.

---

# 1. OpenTelemetry: vendor-neutral telemetry infrastructure

OpenTelemetry provides common APIs/SDK concepts for:

```text
traces
metrics
logs
context propagation
processors
exporters
```

A simplified tracing path is:

```text
application
    -> Tracer
    -> Span
    -> SpanProcessor
    -> SpanExporter
    -> backend
```

Tiny-Agent's local equivalents make this mapping visible:

```text
LocalTracer
    -> SpanRecord
    -> SpanSink
```

---

## 2. Why use OpenTelemetry?

Benefits include:

- vendor-neutral instrumentation;
- shared context across services;
- existing exporters/backends;
- ecosystem instrumentation;
- standardized semantic conventions;
- easier Stage 10 service-to-service tracing.

It does not provide an Agent evaluation strategy by itself.

OpenTelemetry can tell you:

```text
execute_tool took 830 ms
```

but not automatically:

```text
calling this Tool was the correct decision
```

That second question is evaluation.

---

## 3. GenAI semantic conventions

OpenTelemetry maintains GenAI semantic conventions for operations such as model/Agent/retrieval/Tool behavior.

Current conventions include operation concepts such as:

```text
invoke_agent
plan
retrieval
execute_tool
```

This is useful because different Agent systems can describe similar telemetry using shared vocabulary.

However, the GenAI conventions are evolving rapidly. Tiny-Agent therefore:

- uses only a small understandable subset in examples;
- keeps project-specific attributes under `tiny_agent.*`;
- documents the convention version target rather than pretending attribute names are permanent.

Do not copy every current semantic-convention field into your domain model.

Your domain model should survive a telemetry naming revision.

---

## 4. OpenTelemetry Span Events change in 2026

OpenTelemetry announced the deprecation of the Span Events API in March 2026.

The important migration direction is:

```text
old new-code pattern:
span.add_event(...)

recommended direction:
log-based event correlated with current span
```

The goal is to avoid overlapping event concepts between traces and logs.

Tiny-Agent's Stage 08 OpenTelemetry adapter therefore does not introduce new `Span.add_event()` or `Span.record_exception()` instrumentation.

Operations remain spans. Event-like records should be modeled as correlated logs when Stage 10 expands telemetry.

This does not mean old span-event data suddenly stops working. It means new instrumentation should follow the updated direction.

---

## 5. OpenTelemetry success/error status

Tiny-Agent local spans use:

```text
unset
ok
error
```

The OpenTelemetry adapter marks errors with `StatusCode.ERROR`.

For successful operations it does not force an explicit OpenTelemetry OK status, because leaving successful spans unset is a common OpenTelemetry convention unless the instrumentation has a reason to set status.

This is a useful lesson:

> An adapter should preserve semantic intent without forcing two libraries to have identical internal enums.

---

## 6. Why the OTel adapter serializes nested attributes

OpenTelemetry span attributes are not arbitrary nested Python dictionaries.

Tiny-Agent may have a sanitized object such as:

```python
{
    "filter": {"type": "report"},
    "top_k": 3,
}
```

The adapter encodes nested structures as stable JSON strings where needed.

A production semantic convention should prefer explicit scalar attributes for fields you need to query:

```text
retrieval.top_k = 3
```

rather than dumping an entire object into one attribute.

---

# 7. LangSmith: Agent/LLM-oriented tracing and evaluation workflow

LangSmith is more application-specific than OpenTelemetry.

Its current concepts map naturally to Stage 08:

```text
trace/run
    -> one execution and nested operations

dataset
    -> evaluation examples

experiment
    -> run a target on a dataset and collect evaluator scores

online evaluation
    -> evaluate selected production runs/threads

feedback
    -> human/programmatic signals attached to runs
```

This is why we introduce it after building `RunArtifact`, `EvalExample`, and `EvaluationSuite` ourselves.

---

## 8. `@traceable`

Current LangSmith Python documentation recommends `@traceable` for most custom instrumentation.

Example:

```python
from langsmith import traceable

@traceable(name="research_agent")
def run_agent(question):
    ...
```

Nested `@traceable` calls automatically form child runs.

This is conceptually the same parent-child structure you built with `LocalTracer`.

---

## 9. Runtime tracing control

LangSmith supports environment configuration such as:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=tiny-agent-stage08
```

It also supports Python runtime control using:

```python
with tracing_context(enabled=False):
    ...
```

Tiny-Agent's CI uses the disabled context so:

- the current API is imported/tested;
- no API key is needed;
- no trace is uploaded;
- tests remain offline.

That is a better CI boundary than silently requiring developer credentials.

---

## 10. LangSmith offline evaluation

The current LangSmith evaluation model uses:

```text
dataset
-> target
-> evaluators
-> experiment
-> analysis
```

Evaluator styles include:

- deterministic code;
- human review;
- LLM-as-judge;
- pairwise comparison.

This maps directly to the Tiny-Agent local learning model.

The platform adds persistence, visualization, comparison, collaboration, and production workflows.

---

## 11. LangSmith online evaluation

Production traces can be selected or sampled for online evaluation.

Useful signals include:

- reference-free quality judge;
- policy checks;
- user feedback;
- failure classification;
- latency/cost monitoring.

A good workflow promotes useful production failures back into offline datasets.

This closes the loop between observability and regression evaluation.

---

# 12. OpenTelemetry vs LangSmith

Do not frame them as mutually exclusive competitors.

A reasonable architecture can be:

```text
Application
   |
   +--> OpenTelemetry instrumentation
   |       -> general infra/backend
   |
   +--> LangSmith tracing/evaluation
           -> Agent-specific debugging/experiments
```

or use one depending on organizational requirements.

Broadly:

| Concern | OpenTelemetry | LangSmith |
|---|---|---|
| vendor-neutral telemetry model | strong | not primary goal |
| distributed tracing infrastructure | strong | Agent-focused |
| LLM/Agent trace UI | depends on backend | built for it |
| datasets/experiments | not primary | built in |
| LLM evaluators | not primary | built in |
| online Agent evaluation | external system needed | built in |
| telemetry export ecosystem | broad | platform-oriented |

---

# 13. Observability must respect Stage 07 security

Never assume:

```text
"It is only telemetry, so secrets are fine."
```

Observability data is often highly sensitive because it collects many internal systems in one place.

Review:

- prompt/input capture;
- Tool arguments;
- retrieved documents;
- headers/tokens;
- memory contents;
- user identifiers;
- data retention;
- backend access controls.

Instrumentation is another data pipeline and deserves the same security thinking as a database.

---

# 14. Sampling and cost

Tracing 100% of every LLM input/output can be expensive in:

- network bandwidth;
- backend ingestion;
- storage;
- indexing;
- privacy review.

Production policies may sample normal traffic while retaining more failures/outliers.

Evaluation sampling is a separate decision from trace sampling.

For example:

```text
trace 20% of normal traffic
trace 100% of errors
run deterministic online graders on 100%
run LLM judge on 2%
```

The percentages are product-specific; the separation is the important concept.

---

# 15. Traces, metrics, logs, audits

A mature production architecture may separate:

```text
Traces
    -> causal execution debugging

Metrics
    -> aggregate health / SLOs

Logs
    -> event records / diagnostics

Evaluation records
    -> quality measurements

Audit logs
    -> security/compliance evidence
```

Trying to force one database/table/signal to serve every purpose creates confusing retention and trust contracts.

---

# 16. Stage 08 production rule

The final principle is:

> **Instrument the system so you can explain behavior, evaluate the behavior against explicit criteria, and keep the telemetry itself within privacy/security boundaries.**

A system you cannot observe is difficult to debug.

A system you can observe but never evaluate is only a better-recorded mystery.

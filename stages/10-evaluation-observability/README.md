# Stage 10 — Observability, Tracing & Evaluation

> A demo answers: **"Can it work once?"**  Stage 10 asks: **"What actually happened, how good was it, and did the new version regress?"**

Stage 09 gave Tiny-Agent deterministic execution controls. Stage 10 makes those behaviors **inspectable and measurable**.

The stage deliberately does **not** begin with a hosted tracing dashboard. We first build a small local trace model and evaluation harness, then map those concepts to OpenTelemetry and LangSmith.

---

## Why this stage exists

Agent systems are harder to evaluate than ordinary request/response functions because the final answer is only one part of the behavior.

An Agent may:

- give the right answer with the wrong Tool;
- call the right Tool with the wrong arguments;
- reach the right result through five unnecessary retries;
- produce a useful answer after touching a forbidden capability;
- become slower or more expensive while answer quality stays flat;
- pass a hand-picked demo and fail the long tail in production.

So this stage separates three questions:

```text
Logging
    -> What textual records were emitted?

Tracing
    -> What happened during this execution, in what causal structure?

Evaluation
    -> Was that behavior good according to an explicit criterion?
```

A trace is evidence. An evaluator is a judge. A dashboard is a view. None of them automatically implies the other two.

---

## Central mental model

```text
Agent execution
      |
      +--> spans / trace ----------------------+
      |                                        |
      +--> final output                        |
      +--> Tool trajectory                     |
      +--> failures / retries                  |
      +--> latency / tokens / cost             |
                                               v
                                      RunArtifact
                                               |
                          +--------------------+-------------------+
                          |                    |                   |
                          v                    v                   v
                    deterministic          LLM judge        human feedback
                       graders
                          |                    |                   |
                          +--------------------+-------------------+
                                               |
                                               v
                                       EvaluationReport
                                               |
                                      RegressionGate
                                               |
                                      CI / release decision
```

The recurring Tiny-Agent rule still applies:

> **Models propose; application code observes, evaluates, and gates releases.**

---

## Learning objectives

By the end of Stage 10 you should be able to explain and implement:

1. logging vs tracing vs metrics vs evaluation;
2. trace / span / parent-child relationships;
3. privacy-aware capture of Agent inputs and outputs;
4. tracing Tool execution without changing Tool governance semantics;
5. evaluation datasets as executable behavioral specifications;
6. final-response evaluation;
7. single-step Tool selection and argument evaluation;
8. full-trajectory evaluation;
9. why exact trajectory matching can be too strict;
10. deterministic graders vs LLM-as-judge;
11. judge calibration and variance concerns;
12. offline evaluation vs online evaluation;
13. quality / latency / token / cost metrics;
14. metric coverage and why missing scores can hide crashes;
15. regression gates for CI;
16. OpenTelemetry as vendor-neutral telemetry infrastructure;
17. current OpenTelemetry GenAI semantic-convention caveats;
18. LangSmith traces, datasets, experiments, and online evaluation;
19. why traces are not automatically audit logs;
20. sampling, retention, PII, secrets, and high-cardinality production concerns.

---

## Stage boundary

Stage 10 builds an **evaluation and observability foundation**. It does not claim to solve:

- production-scale telemetry storage;
- enterprise audit/compliance retention;
- distributed tracing across every future Stage 13 service;
- perfect automatic task-success grading;
- fully calibrated LLM judges;
- causal attribution of model quality changes;
- A/B experimentation platforms;
- adversarial red-team evaluation at enterprise scale;
- full SLO/alerting operations.

Those are larger production systems. This stage makes their abstractions understandable first.

---

# Learning order

Follow the files in this order.

## 1. Why Agent evaluation is different

Read:

- [`theory/01-why-agent-evaluation-is-hard.md`](theory/01-why-agent-evaluation-is-hard.md)

Run:

```bash
python stages/10-evaluation-observability/code/eval_dataset.py
```

Main idea:

```text
final answer quality != execution quality
```

---

## 2. Build traces from first principles

Read:

- [`theory/02-tracing-and-observability.md`](theory/02-tracing-and-observability.md)

Run:

```bash
python stages/10-evaluation-observability/code/trace_model.py
python stages/10-evaluation-observability/code/local_tracer.py
python stages/10-evaluation-observability/code/traced_guarded_tool.py
```

Mental model:

```text
Trace = one end-to-end execution
Span  = one timed operation inside that execution
```

The local tracer uses a `ContextVar` to maintain parent-child context and stores completed spans in an in-memory sink.

Raw inputs/outputs are **disabled by default**. Stage 10 must not undo Stage 09's secret-redaction work just because a dashboard would look prettier with everything captured.

---

## 3. Evaluate Tools and trajectories

Read:

- [`theory/03-tool-and-trajectory-evaluation.md`](theory/03-tool-and-trajectory-evaluation.md)

Run:

```bash
python stages/10-evaluation-observability/code/tool_call_evaluator.py
python stages/10-evaluation-observability/code/trajectory_evaluator.py
```

We score separately:

```text
Tool selection
Tool arguments
Required trajectory steps
Forbidden actions
Tool-call budget
Final answer
```

Why separate them?

Because:

```text
right Tool + wrong arguments
```

is a different engineering failure from:

```text
wrong Tool + valid arguments
```

A single `agent_quality = 0.63` hides that distinction.

---

## 4. Build offline evaluation datasets

Read:

- [`theory/04-offline-online-and-datasets.md`](theory/04-offline-online-and-datasets.md)

A useful evaluation example may contain:

```python
EvalExample(
    id="weather-tokyo",
    inputs={"question": "Weather in Tokyo?"},
    reference_output="...",
    expected_tools=("weather",),
    reference_tool_calls=(...),
    forbidden_tools=("shell",),
    max_tool_calls=1,
    metadata={"split": "regression"},
)
```

This is more than a prompt collection. It is an executable specification of expected behavior.

---

## 5. Understand LLM-as-judge

Read:

- [`theory/05-graders-and-llm-as-judge.md`](theory/05-graders-and-llm-as-judge.md)

Run:

```bash
python stages/10-evaluation-observability/code/llm_judge_boundary.py
```

Rule of thumb:

```text
Can ordinary code judge it reliably?
    yes -> use code
    no  -> consider human or LLM judge
```

Do not hire a stochastic language model to verify `2 + 2 == 4` unless your budget has developed feelings.

---

## 6. Turn metrics into regression gates

Read:

- [`theory/06-quality-cost-latency-and-regression.md`](theory/06-quality-cost-latency-and-regression.md)

Run:

```bash
python stages/10-evaluation-observability/code/regression_gate.py
python stages/10-evaluation-observability/code/end_to_end_eval.py
```

A release gate can express:

```text
execution_success >= 1.00
exact_match       >= 0.95
tool_f1           >= 0.95
trajectory_policy == 1.00
latency_p95       <= threshold
cost_per_task     <= threshold
```

Tiny-Agent's teaching gate also checks **metric coverage**. If half the candidate runs crash and therefore never receive a quality score, the surviving half must not make the average look perfect.

---

## 7. Map the mechanism to OpenTelemetry and LangSmith

Read:

- [`theory/07-opentelemetry-langsmith-and-production.md`](theory/07-opentelemetry-langsmith-and-production.md)

Run:

```bash
python stages/10-evaluation-observability/code/opentelemetry_tracing.py
python stages/10-evaluation-observability/code/langsmith_traceable.py
```

The two tools solve different layers:

```text
OpenTelemetry
    -> vendor-neutral telemetry APIs, context, processors, exporters,
       traces/metrics/logs and evolving GenAI semantic conventions

LangSmith
    -> LLM/Agent-oriented tracing UI, datasets, experiments,
       evaluators, feedback, online/offline evaluation workflows
```

Neither replaces the evaluation design you learned first.

---

# New reusable Tiny-Agent APIs

## Local tracing

```python
from tiny_agent import InMemorySpanSink, LocalTracer

sink = InMemorySpanSink()
tracer = LocalTracer(sink)

with tracer.span("invoke_agent", kind="agent"):
    with tracer.span("execute_tool search", kind="tool") as span:
        span.set_attribute("tool.name", "search")
```

## Privacy-aware capture

```python
from tiny_agent import TraceCapturePolicy

policy = TraceCapturePolicy(
    capture_inputs=True,
    capture_outputs=True,
    max_text_chars=256,
)
```

Even when capture is enabled, mappings with keys such as `password`, `token`, `api_key`, and `authorization` are redacted.

This is a teaching safeguard, **not a complete DLP system**.

## Observe the Stage 09 guarded executor

```python
observed = ObservedGuardedToolExecutor(
    guarded_executor,
    tracer,
)
```

The adapter observes. It does not replace:

- validation;
- permission checks;
- approval binding;
- budget enforcement;
- retry policy;
- timeout policy.

## Evaluation dataset

```python
example = EvalExample(
    id="case-001",
    inputs={"question": "..."},
    reference_output="...",
    expected_tools=("search",),
)
```

## Evaluation suite

```python
suite = EvaluationSuite([
    ExactMatchEvaluator(),
    ToolSelectionEvaluator(),
    TrajectoryEvaluator(),
])

report = suite.run(dataset, target)
```

## Regression gate

```python
gate = RegressionGate([
    MetricGateRule(
        "execution_success",
        absolute_limit=1.0,
    ),
    MetricGateRule(
        "trajectory_policy_ok",
        absolute_limit=1.0,
    ),
])
```

---

# Metrics: do not flatten everything into one number

A useful evaluation report may contain:

| Dimension | Example metric | Why it exists |
|---|---|---|
| execution | `execution_success` | did the target crash? |
| answer | `exact_match`, correctness judge | was the result useful/correct? |
| Tool choice | precision / recall / F1 | did the Agent choose appropriate capabilities? |
| Tool arguments | argument accuracy | were inputs to the Tool correct? |
| trajectory | sequence recall | were required steps present? |
| safety | `trajectory_policy_ok` | were forbidden tools/budgets respected? |
| reliability | failure/retry rate | did transient problems dominate? |
| latency | mean/p50/p95 | how long did users wait? |
| usage | tokens | how much model capacity was consumed? |
| economics | cost/task | did a quality improvement become uneconomical? |

A weighted composite can be useful for ranking experiments, but keep component scores visible.

Otherwise this can happen:

```text
quality improved +2%
safety regressed -100%
weighted average: looks fine 😬
```

---

# Offline vs online evaluation

## Offline

Use before release for:

- regression testing;
- prompt/model comparison;
- Tool policy changes;
- retrieval changes;
- reproducible benchmarks;
- backtesting historical cases.

Offline datasets may contain trusted reference outputs and exact expected Tool calls.

## Online

Use production traces for:

- real user distribution;
- drift;
- rare failures;
- feedback;
- latency/cost monitoring;
- sampling expensive evaluators;
- turning production failures into future regression cases.

Do not blindly send every production trace to an expensive LLM judge.

---

# OpenTelemetry note for 2026

OpenTelemetry announced the deprecation of the **Span Events API** in March 2026. New event-like instrumentation should move toward log-based events correlated with the current span.

Therefore Tiny-Agent Stage 10 teaches:

```text
span hierarchy for operations
+ logs for event-like records when needed
```

rather than introducing new `span.add_event(...)` instrumentation.

OpenTelemetry's GenAI semantic conventions are also still evolving. Treat current attribute names as versioned conventions, not eternal law.

---

# LangSmith note

Current LangSmith documentation separates:

```text
Trace
    -> inspect one execution

Dataset
    -> collection of evaluation examples

Experiment
    -> run a target over a dataset and attach evaluator scores

Online evaluation
    -> evaluate selected production runs/threads
```

Stage 10 uses LangSmith **after** the local model so the platform vocabulary maps to concepts you already understand.

The runnable LangSmith example disables trace submission with `tracing_context(enabled=False)`, so CI does not need an API key or network call.

---

# Installation

Core tracing/evaluation mechanisms remain dependency-free:

```bash
python -m pip install -e ".[dev]"
```

For Stage 10 integrations:

```bash
python -m pip install -e ".[dev,stage10]"
```

---

# Suggested reading order

## LangSmith official

1. [Observability](https://docs.langchain.com/langsmith/observability)
2. [Custom instrumentation](https://docs.langchain.com/langsmith/annotate-code)
3. [Evaluation](https://docs.langchain.com/langsmith/evaluation)
4. [Evaluation concepts](https://docs.langchain.com/langsmith/evaluation-concepts)
5. [Application-specific evaluation approaches](https://docs.langchain.com/langsmith/evaluation-approaches)

## OpenTelemetry official

1. [Python manual instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/)
2. [Python exporters](https://opentelemetry.io/docs/languages/python/exporters/)
3. [GenAI semantic conventions repository](https://github.com/open-telemetry/semantic-conventions-genai)
4. [Deprecating Span Events API](https://opentelemetry.io/blog/2026/deprecating-span-events/)

When a vendor SDK example disagrees with current official documentation, prefer the current official documentation and the version tested by this repository's CI.

---

# Exercises

After the theory and examples, complete:

- [`exercises/review-questions.md`](exercises/review-questions.md)

The exercises include conceptual questions, coding tasks, evaluation-design cases, and interview questions.

---

# Milestone

You have completed Stage 10 when you can build and explain this pipeline:

```text
Agent run
  -> privacy-aware trace
  -> RunArtifact
  -> final/Tool/trajectory evaluators
  -> multi-dimensional report
  -> regression gate
  -> OpenTelemetry/LangSmith integration
```

and, more importantly, when you can answer:

> **If the Agent reaches the correct final answer through a wasteful, unsafe, or unauthorized trajectory, should that execution pass evaluation?**

For Tiny-Agent, the answer is **no**.

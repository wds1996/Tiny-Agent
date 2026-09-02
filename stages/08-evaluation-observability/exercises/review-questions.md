# Stage 08 Review, Coding & Interview Exercises

Use these after reading the theory and running every example.

---

## A. Core concepts

1. Explain the difference between logging, tracing, metrics, evaluation, and audit logging.
2. What is the difference between a trace and a span?
3. Why does a span need a `parent_span_id`?
4. Why is one global `CURRENT_SPAN` unsafe in an async server?
5. Why does Tiny-Agent disable raw input/output trace capture by default?
6. Why can `repr()` be dangerous in generic telemetry serialization?
7. Why should tracing not become a second authorization engine?
8. Why is a trace not proof that an Agent behaved correctly?
9. Why is a tracing dashboard not automatically an evaluation platform?
10. Why can a correct final answer still be an Agent failure?

---

## B. Trace design

For each operation, decide whether it should normally be a span, a metric, a log/event-like record, an evaluation score, or an audit record. Explain your choice.

1. `invoke_agent` took 1.8 seconds.
2. Tool `search` returned HTTP 503.
3. User approved a production deployment.
4. `tool_calls_total` over the last five minutes.
5. A candidate answer scored 0.86 on helpfulness.
6. A model emitted 2,430 tokens.
7. An API key was rotated.
8. The Agent retried a Tool after 500 ms.
9. The Agent used a forbidden capability.
10. p95 latency exceeded the SLO.

---

## C. Privacy / telemetry

1. Why should prompts not automatically be stored in trace attributes?
2. Design an allowlist-based capture policy stricter than Tiny-Agent's teaching redactor.
3. What should happen to:

```python
{
    "authorization": "Bearer abc",
    "question": "hello",
}
```

before telemetry export?
4. Explain the difference between redaction, pseudonymization, encryption, and retention.
5. Why can observability backends become high-value security targets?
6. What is high-cardinality telemetry? Give three Agent examples.
7. Why should a full user prompt not be used as a span name?

---

## D. Tool evaluation

Suppose the expected Tool is:

```python
ToolInvocation("weather", {"city": "Tokyo"})
```

Evaluate the failure category for each candidate:

```python
weather(city="Tokyo")
calculator(expression="Tokyo")
weather(city="Osaka")
weather(city="Tokyo"), search(q="Tokyo weather")
```

Which affect:

- Tool precision;
- Tool recall;
- argument accuracy;
- efficiency?

---

## E. Trajectory evaluation

Reference requirement:

```text
search -> read -> summarize
```

Forbidden Tool:

```text
delete_file
```

Max Tool calls:

```text
4
```

Evaluate these trajectories conceptually:

```text
1. search -> read -> summarize
2. search -> inspect_metadata -> read -> summarize
3. read -> search -> summarize
4. search -> delete_file -> read -> summarize
5. search -> search -> search -> read -> summarize
```

For each, discuss:

- required sequence recall;
- policy compliance;
- efficiency;
- whether exact trajectory matching would be fair.

---

## F. Offline vs online evaluation

Classify each task as primarily offline, online, or both:

1. compare two prompts before release;
2. monitor live latency drift;
3. replay a previous production incident;
4. score user thumbs-up/down feedback;
5. test a new Tool schema;
6. detect real production prompt-injection attempts;
7. build a gold reference set;
8. sample real conversations for an LLM judge.

Explain why.

---

## G. Dataset design

Design an `EvalExample` set for an Agent that can:

```text
search_docs
read_doc
create_ticket
send_email
```

Include at least:

- two happy paths;
- one no-Tool case;
- one wrong-argument trap;
- one forbidden-action safety case;
- one previous-bug regression case;
- one ambiguous case;
- one long-tail case.

For each example specify:

```text
input
reference output if appropriate
expected Tools
reference Tool arguments if appropriate
required sequence
forbidden Tools
max Tool calls
metadata/split
```

---

## H. LLM-as-judge

1. Why is an LLM judge not ground truth?
2. Give an example where deterministic code is better than an LLM judge.
3. Give an example where an LLM judge may be appropriate.
4. Write a rubric for factual faithfulness using retrieved evidence.
5. How would you calibrate that judge against humans?
6. What is position bias in pairwise judging?
7. Why can evaluated text itself prompt-inject the judge?
8. Why should online LLM judging usually be sampled rather than blindly run on every trace?
9. What information should be recorded about the judge model/config for reproducibility?

---

## I. Regression gates

A baseline has:

```text
execution_success = 1.00
quality           = 0.94
tool_f1           = 0.97
safety            = 1.00
latency_ms        = 900
cost_task_usd     = 0.015
```

Candidate A:

```text
execution_success = 1.00
quality           = 0.96
tool_f1           = 0.96
safety            = 1.00
latency_ms        = 1150
cost_task_usd     = 0.018
```

Candidate B:

```text
execution_success = 1.00
quality           = 0.98
tool_f1           = 0.98
safety            = 0.99
latency_ms        = 850
cost_task_usd     = 0.014
```

Questions:

1. Which candidate is automatically better?
2. Should safety be a hard gate?
3. Propose absolute thresholds.
4. Propose maximum allowed regressions.
5. Which metrics are higher-is-better vs lower-is-better?

---

## J. Missing metric coverage

100 examples are evaluated.

- 50 crash;
- 50 finish;
- all finished runs have correctness score 1.0.

Answer:

1. What is execution-success rate?
2. What is correctness mean among scored examples?
3. What is correctness coverage?
4. Why is reporting only `correctness=1.0` misleading?
5. How should a regression gate treat this candidate?

---

## K. OpenTelemetry

1. Explain `Tracer -> Span -> SpanProcessor -> SpanExporter`.
2. What problem does OpenTelemetry solve that Tiny-Agent's `LocalTracer` does not?
3. What problem does OpenTelemetry **not** solve for Agent evaluation?
4. Why does Stage 08 avoid introducing new `Span.add_event()` calls in 2026?
5. What is the newer direction for event-like telemetry?
6. Why should current GenAI semantic-convention attributes be treated as versioned/evolving?
7. Why keep Tiny-Agent-specific attributes under a project namespace?

---

## L. LangSmith

Explain these concepts in your own words:

```text
trace/run
dataset
experiment
evaluator
feedback
online evaluation
```

Then explain how each maps to the handwritten Stage 08 abstractions.

Why does Tiny-Agent test `@traceable` with `tracing_context(enabled=False)` in CI?

---

## M. Coding exercises

### Exercise 1 — Latency evaluator

Implement an evaluator that scores:

```text
1.0 if latency <= 1000 ms
0.5 if latency <= 2000 ms
0.0 otherwise
```

Then explain why the raw latency should still be retained separately.

### Exercise 2 — Forbidden sequence

Extend `TrajectoryEvaluator` to reject the sequence:

```text
read_secret -> send_email
```

even if each Tool is individually allowed.

### Exercise 3 — Numeric argument tolerance

Implement argument comparison that treats:

```text
100
100.0
```

as equivalent while still rejecting strings.

### Exercise 4 — Trace metrics

From a list of `SpanRecord`, compute:

```text
tool_call_count
failed_span_count
total_tool_duration_ms
```

### Exercise 5 — Dataset slices

Add a helper that reports mean metrics grouped by:

```python
example.metadata["category"]
```

### Exercise 6 — Judge calibration

Given 100 human binary labels and 100 LLM-judge binary labels, compute precision, recall, F1, and disagreement examples.

### Exercise 7 — CI gate

Write a script that exits non-zero when `RegressionGateResult.passed` is false.

---

## N. Interview questions

1. How would you evaluate an Agent differently from a chatbot?
2. What is trajectory evaluation?
3. Why can exact trajectory matching be too strict?
4. How would you measure Tool-selection quality?
5. What is offline vs online evaluation?
6. When would you use LLM-as-judge?
7. How would you validate an LLM judge?
8. How would you prevent a prompt from injecting an evaluator?
9. How would you decide what telemetry to retain?
10. What is the difference between OpenTelemetry and LangSmith?
11. What is the relationship between tracing and evaluation?
12. Why are p95/p99 latency useful?
13. How would you detect a quality regression in CI?
14. Why is metric coverage important?
15. How do Stage 07 budgets and Stage 08 metrics complement each other?

---

## Completion checklist

You are ready for Stage 09 when you can explain without notes:

```text
trace != metric != evaluation != audit log
final answer quality != trajectory quality
Tool selection != Tool arguments
Offline eval != online eval
LLM judge != oracle
OpenTelemetry != LangSmith
observability != authorization
```

and can build a repeatable dataset -> target -> evaluator -> report -> regression-gate loop.

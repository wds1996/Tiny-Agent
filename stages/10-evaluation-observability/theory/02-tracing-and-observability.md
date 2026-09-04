# 02 — Tracing and Observability

Stage 09 made execution safer. Stage 10 needs to answer:

> What happened inside one Agent run?

Printing a few lines is not enough once execution contains nested model calls, retrieval, Tool calls, retries, interrupts, and remote services.

---

## 1. Logging, metrics, tracing, evaluation

These concepts overlap, but they answer different questions.

### Logging

Example:

```text
2026-09-02 14:03 tool=search status=ok
```

Good for discrete records and diagnostics.

### Metrics

Example:

```text
tool_calls_total = 12842
p95_latency = 2.4 s
error_rate = 0.7%
```

Good for aggregate system behavior.

### Tracing

Example:

```text
invoke_agent
├── model_call
├── retrieval
└── execute_tool search
    └── retry
```

Good for causal structure of one execution.

### Evaluation

Example:

```text
answer_correctness = 0.9
trajectory_policy_ok = 1.0
```

Good for judging behavior against explicit criteria.

A tracing UI with beautiful nested boxes does not automatically mean the Agent is good.

It only means you can inspect its boxes more beautifully.

---

## 2. Trace and span

A **trace** represents one end-to-end execution.

A **span** represents one timed operation inside the trace.

Example:

```text
Trace: user task #123

Span A: invoke_agent
Span B: model decision
Span C: retrieval
Span D: execute_tool
```

Each span usually needs:

```text
trace_id
span_id
parent_span_id
name
start/end time
status
attributes
```

Tiny-Agent's `SpanRecord` contains exactly that minimal model.

---

## 3. Parent-child structure is the key

Without parent relationships you may know:

```text
model call = 400 ms
tool call  = 900 ms
retrieval  = 150 ms
```

but not which model call triggered which Tool call.

With structure:

```text
invoke_agent
├── decide
│   └── model
├── retrieve
└── execute_tool search
    ├── attempt 1
    └── attempt 2
```

you can reason about the execution.

This is why tracing is more than timestamped logging.

---

## 4. Context propagation

A nested operation needs to know its current parent.

Tiny-Agent's `LocalTracer` uses Python `ContextVar`:

```python
with tracer.span("agent"):
    with tracer.span("tool"):
        ...
```

The child span automatically inherits the trace ID and records the current span as parent.

`ContextVar` is important because normal async task context propagation is safer than one global variable such as:

```python
CURRENT_SPAN = root
```

A global mutable variable in a concurrent server is a fast route to:

> "Congratulations, Alice's Tool call is now a child of Bob's Agent trace."

---

## 5. Span names vs attributes

Prefer stable operation categories in attributes:

```text
gen_ai.operation.name = execute_tool
tool.name             = search
```

and human-readable span names such as:

```text
execute_tool search
```

Do not put unbounded user content into span names:

```text
BAD:
span name = "search for user's entire 4,000-token question..."
```

Why?

- high cardinality;
- expensive indexes;
- sensitive content;
- unreadable dashboards.

Keep high-cardinality data controlled and deliberate.

---

## 6. Raw prompt capture is a privacy decision

A naive tracer does:

```python
span.set_attribute("prompt", full_prompt)
span.set_attribute("output", full_output)
```

This can silently copy:

- credentials;
- personal data;
- proprietary documents;
- internal prompts;
- memory contents;
- Tool results;
- customer data

into an observability backend.

That would undo the Stage 09 rule:

```text
unexpected internal details must not cross boundaries casually
```

So Tiny-Agent defaults to:

```python
TraceCapturePolicy(
    capture_inputs=False,
    capture_outputs=False,
)
```

You must opt in.

---

## 7. Redaction still matters after opt-in

Even with capture enabled:

```python
{
    "api_key": "sk-...",
    "query": "hello"
}
```

becomes roughly:

```python
{
    "api_key": "<redacted>",
    "query": "hello"
}
```

Tiny-Agent also truncates long strings.

This is an educational safety boundary, not enterprise DLP.

Real production systems may need:

- field-level allowlists;
- data classification;
- PII detectors;
- tokenization/pseudonymization;
- retention policies;
- regional storage controls;
- access controls over traces.

---

## 8. Unknown objects should not be `repr()`'d blindly

Suppose a provider SDK object has:

```python
def __repr__(self):
    return "Client(api_key='secret', endpoint='internal')"
```

A generic telemetry serializer that calls:

```python
repr(value)
```

may leak secrets.

Tiny-Agent therefore converts unknown objects only to:

```text
<ClassName>
```

unless application code explicitly extracts safe attributes.

Observability should make failures visible, not make secrets visible.

---

## 9. Observe policy; do not duplicate policy

`ObservedGuardedToolExecutor` wraps Stage 09:

```text
ObservedGuardedToolExecutor
        |
        v
GuardedToolExecutor
```

The observed layer records:

- Tool name;
- attempts;
- status;
- safe failure code;
- latency through span timing.

It does **not** decide:

- whether Tool arguments are valid;
- whether principal has permission;
- whether approval is valid;
- whether retry is safe;
- whether budget is exhausted.

That separation matters.

If telemetry becomes a second permission engine, disabling tracing might accidentally disable security.

Security controls must continue to work even when observability is turned off.

---

## 10. Failure telemetry should preserve classification, not secret text

Stage 09 introduced:

```text
ToolFailure[internal_error]: Tool execution failed.
```

Stage 10 records:

```text
error.type = internal_error
```

not:

```text
error.message = postgres://admin:password@prod...
```

The useful operational question is often:

```text
How many timeout failures?
How many permission denials?
Which Tools have high transient failure rate?
```

You do not need every raw exception string in every model-facing trace to answer those questions.

---

## 11. Traces are not necessarily audit logs

A security audit log usually needs strong guarantees about:

- who performed the action;
- what was authorized;
- exact resource identity;
- tamper resistance;
- retention;
- completeness;
- legal/compliance requirements.

Observability traces may be:

- sampled;
- dropped;
- redacted;
- stored for shorter periods;
- optimized for debugging.

Therefore:

```text
Trace != Audit Log
```

They may share data, but they do not have the same contract.

---

## 12. Sampling

At small scale you may trace 100% of runs.

At large scale that can become expensive.

Common approaches include:

```text
head sampling
    decide near trace start

tail sampling
    decide after seeing more of the trace

priority sampling
    keep failures/high-risk cases more often
```

Agent systems often benefit from retaining:

- errors;
- policy denials;
- high latency;
- high cost;
- unusual trajectories;
- sampled normal successes.

But sampling has a consequence:

> sampled telemetry is not a complete count unless metrics are collected separately with appropriate semantics.

---

## 13. High-cardinality attributes

Useful but dangerous attributes include:

```text
user_id
thread_id
document_id
Tool arguments
URL
prompt hash
```

They can explode index cardinality and cost.

A design question is not only:

> "Can I attach this attribute?"

but:

> "Do I need to query/group by this attribute in the telemetry backend?"

Store only what supports a concrete debugging/evaluation use case.

---

## 14. Local tracer first, OpenTelemetry second

Tiny-Agent first implements:

```text
SpanRecord
InMemorySpanSink
LocalTracer
```

so you understand:

- identity;
- hierarchy;
- timing;
- attributes;
- capture policy;
- sink/export boundary.

Then OpenTelemetry becomes understandable as a mature generalization rather than magical instrumentation plumbing.

The final mental model is:

```text
Application operation
      -> instrumentation
      -> span/log/metric API
      -> processor
      -> exporter
      -> backend
```

Stage 10 only needs enough of that architecture to make the boundary clear.

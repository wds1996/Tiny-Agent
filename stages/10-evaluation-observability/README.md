# Stage 10: Do Not Judge an Agent by Its Last Sentence — Evaluation and Observability

> Language: **English** | [简体中文](README.zh-CN.md)

Stage 09 put validation, permissions, budgets, retries, and deadlines into the Runtime. The natural next question is: after changing a Prompt, Tool, RAG pipeline, or Guardrail, how do we know the system actually improved?

Trying a few pleasant-looking prompts only shows that those demonstrations happened to look good. Agent quality also lives in its path: whether it omitted critical evidence, called an unnecessary Tool, spent too many steps, was denied by a guardrail, or kept answering when evidence was insufficient.

This chapter builds two complementary capabilities:

| Question | Capability | Output |
| --- | --- | --- |
| “What happened in this one Run?” | **Observability** | Traces, logs, metrics |
| “Did this change improve an important set of behaviors?” | **Evaluation** | Stable cases, scores, regression report |

Use a trace to explain one failure, then use evaluation to tell whether behavior regressed overall. Neither replaces the other: a trace is not a grade, and an evaluation report cannot automatically explain a failure.

---

## 1. From “the guardrail exists” to “we can prove its behavior”

In Stage 09, a Tool may not run for many different reasons: the model never proposed it, validation failed, permission was denied, the budget was exhausted, the deadline expired, or the external dependency actually failed. One `tool failed` log line erases all of those responsibility boundaries.

Stage 10 therefore starts by preserving the boundaries the system already has, rather than by choosing a monitoring product:

```text
agent.run
├── context.build
├── model.generate
├── policy.authorize
├── tool.lookup_order
├── retrieval.search_policy
└── final response
```

Each line is a **Span**: one small piece of work with a clear responsibility. All spans associated with the same `run_id` form a **Trace**.

Three common signals have different jobs:

| Signal | Question it answers | Agent example |
| --- | --- | --- |
| Log | “Which discrete event happened?” | `permission denied for issue_refund` |
| Metric | “What is the trend across many Runs?” | P95 latency, Tool success rate, average Tool calls |
| Trace | “Which path led this Run to a result or failure?” | Which evidence was retrieved, which Tools ran, where a call was denied |

For example, `P95 latency = 820 ms` means that 95% of Runs finished within 820 milliseconds; the slowest 5% took longer. It exposes a small set of very slow requests more clearly than an average alone.

For production terminology and tooling, read the [OpenTelemetry Observability Primer](https://opentelemetry.io/docs/concepts/observability-primer/). OpenTelemetry is an open standard for consistently recording and exporting this kind of observability data. This chapter implements a small tracer by hand so its data model and boundaries remain visible; it is not a replacement for a production SDK.

---

## 2. Trace a whole Run before printing more log lines

[`code/tracing.py`](code/tracing.py) records a Span’s name, start time, duration, attributes, status, and its `span_id` / `parent_span_id`. The final two fields make the Trace an actual tree rather than a few coincidentally adjacent log lines.

This is a complete minimal Trace using the same API as [`code/demo.py`](code/demo.py):

```python
from tracing import CapturePolicy, Trace, Tracer, format_trace

trace = Trace("run-001")
tracer = Tracer(trace, capture_policy=CapturePolicy(capture_content=False))

with tracer.span("agent.run", workflow="refund_support"):
    with tracer.span("context.build", question="Can ORDER-42 be refunded?") as span:
        span["selected_items"] = 3

    with tracer.span("tool.lookup_order", tool="lookup_order") as span:
        span["status_code"] = 200

print(format_trace(trace))
```

Its essential output is:

```text
run-001
└── agent.run [ok]
    ├── context.build [ok]
    └── tool.lookup_order [ok]
```

`agent.run` is the parent Span; `context.build` and `tool.lookup_order` are its children. A Span name states the responsibility. An **attribute** is a key-value note attached to that step: `selected_items=3` says three Context items were selected, while `status_code=200` says the request succeeded. Do not put an entire Prompt or Tool Result into attributes by default; the next section explains why.

Instrumentation is an observer and must not alter business behavior. When work inside `with tracer.span(...)` raises, the tracer records `status="error"` and the exception type, then re-raises the original exception:

```python
from tracing import Trace, Tracer

trace = Trace("failed-run")
try:
    with Tracer(trace).span("tool.lookup_order"):
        raise RuntimeError("connection lost")
except RuntimeError:
    pass

span = trace.spans[0]
assert span.status == "error"
assert span.attributes["error_type"] == "RuntimeError"
```

The snippet intentionally does not retain the raw `connection lost` message. Model-visible safe errors, controlled engineer diagnostics, and Trace attributes need distinct data boundaries, consistent with Stage 09.

Run the local example now:

```bash
python stages/10-evaluation-observability/code/demo.py
```

---

## 3. A Trace is a data system: design what it may retain

Traces are useful for debugging, which also makes them an easy place to collect Prompts, user details, retrieved documents, secrets, and Tool arguments. Think of a Trace as the maintenance record for one Run: it needs to say which step took time and whether it succeeded, but it need not photocopy every sentence a user supplied. Observability needs minimization, access control, and retention policy just like every other data system.

`CapturePolicy` is the filter before that maintenance record is written. Each Span’s attributes pass through it before the Trace stores them.

The chapter’s default `CapturePolicy` stores no raw strings. It stores their length and a 12-character SHA-256 digest instead:

```python
from tracing import CapturePolicy

policy = CapturePolicy(capture_content=False)
safe = policy.sanitize({"prompt": "private text", "selected_items": 3})

assert safe == {
    "prompt_sha256": "66c279b1e928",
    "prompt_chars": 12,
    "selected_items": 3,
}
```

`prompt_chars=12` is only the original length. `prompt_sha256` is the fixed fingerprint calculated from `private text`. You do not need the mathematics of SHA-256 here: the same text produces the same fingerprint, while changed text normally produces a different one. That lets us ask whether two Runs used the same content or whether a Context item changed, without retaining the original text by default.

A hash is not a universal privacy solution. A **low-entropy value** has only a few easy-to-enumerate candidates, such as `yes/no`, a country code, or a status with only a few options. Someone can hash every candidate and guess the original value. Hashing reduces default exposure; it does not replace data governance.

Only enable content capture for a controlled debugging need, and keep a hard length limit:

```python
from tracing import CapturePolicy

policy = CapturePolicy(capture_content=True, max_text_chars=4)
assert policy.sanitize({"prompt": "abcdef"})["prompt"] == "abcd"
```

Production systems must still define who can read a trace, how long it lives, which fields require **redaction** (replacing secrets with `[REDACTED]`), and how to **sample**. Sampling records only a subset of ordinary Runs, for example one out of every hundred. Errors or high-risk Runs may retain more structured information, but that does not mean raw-content capture should become less strict. The in-memory list in this chapter does not solve those operations problems; it makes “do not capture full text by default” a testable starting point.

---

## 4. Define correct behavior in an Eval Case before discussing scores

Evaluation is not asking the user’s question again. It writes a repeatable expectation for one important behavior. An `EvalCase` holds a stable ID, question, required answer fragments, expected Tool sequence, and whether the Agent should abstain. An `AgentRun` holds what the Agent actually produced: its answer, Tools, retrieved sources, and run measurements.

The `assert` statements below are Python assertions: the program raises an error when a condition is false. The teaching example uses them to make an expected result into a runnable check.

This complete refund example compares answer, trajectory, and abstention separately:

```python
from evaluation import AgentRun, EvalCase, score_case

case = EvalCase(
    id="refund-within-window",
    question="Can ORDER-42 be refunded to the original payment method?",
    expected_answer_contains=("30 days", "original payment method"),
    expected_tools=("lookup_order", "search_refund_policy"),
)
run = AgentRun(
    answer="Orders within 30 days may use the original payment method.",
    tools=("lookup_order", "search_refund_policy"),
    retrieved_ids=("refund-policy",),
    latency_ms=18,
)

score = score_case(case, run)
assert score.answer_ok
assert score.tool_trajectory_ok
assert score.abstention_ok
assert score.passed
```

In the teaching implementation, `expected_tools` is an **ordered, exact** tuple: extra calls, missing calls, or a different order set `tool_trajectory_ok=False`. That is useful when a refund flow has one known action path. If two different paths are both valid, create a Case for each or write an explicit custom evaluator. Do not quietly weaken the rule until every path passes.

`expected_answer_contains` is also a narrow, stable deterministic check, not a complete measure of natural-language quality. Its value is that failures remain reproducible and explainable when a rule can be stated precisely.

---

## 5. Report answers, trajectories, resources, and retrieval components together

For each Case, `score_case()` produces `answer_ok`, `tool_trajectory_ok`, and `abstention_ok`. A Case passes only when all three are true. An Agent that gets the final answer by luck after making irrelevant Tool calls therefore does not receive the same result as the intended trajectory.

[`code/evaluation.py`](code/evaluation.py) aggregates the cases into:

```python
EvalReport(
    scores=...,                       # three independent results per Case
    pass_rate=...,                    # passing Cases / all Cases
    unnecessary_tool_rate=...,        # unnecessary Tool calls / all Tool calls
    average_tool_calls=...,           # mean Tool calls per Case
    average_latency_ms=...,           # mean latency per Case
    average_estimated_cost_usd=...,   # mean estimated cost per Case
)
```

The numerator of `unnecessary_tool_rate` includes all Tool calls in cases such as a greeting that expected none, plus calls beyond the expected number in other cases. Its denominator is all observed Tool calls. It does not replace trajectory scoring: a wrong Tool with the same count still fails `tool_trajectory_ok`.

Do not guess after an end-to-end score falls. Earlier stages already contain independently measurable components:

| Component | Direct checks |
| --- | --- |
| Stage 02 Router | route accuracy |
| Stage 04 Retriever | Recall@K, MRR, whether a critical source was retrieved |
| Stage 07 Context | required-context retention, irrelevant content, omissions |
| Stage 09 Tool / Guardrail | arguments, permission-denial reason, retries, budget |
| Agent trajectory | Tool order, step count, unnecessary actions |
| Final answer | correctness, evidence boundary, abstention |

For example, Retriever `Recall@K` asks one exact question: did the first K results contain the labeled relevant documents?

```python
from evaluation import recall_at_k

score = recall_at_k(["a", "b", "c"], {"b", "x"}, k=2)
assert score == 0.5
```

If a critical document never enters Top-K, a fluent later answer cannot repair that retrieval failure.

`MRR` (Mean Reciprocal Rank) also measures retrieval ordering: a relevant document at rank 1 scores `1`, at rank 2 scores `1/2`, and lower ranks score less; the values are then averaged across queries.

Run the local regression checks here:

```bash
python stages/10-evaluation-observability/code/checks.py
```

---

## 6. Use deterministic evaluators first when the rule is deterministic

Evaluators need design too. Start with rules that can be decided exactly, then use human review or an LLM judge for genuinely open semantic questions.

| Evaluation question | First choice | Why |
| --- | --- | --- |
| Was the correct Tool called, were arguments valid, was a budget exceeded? | Deterministic rule | Exact answer, cheap and repeatable |
| Did relevant evidence enter Top-K? | Recall@K / MRR | Labeled sources permit direct calculation |
| Did the Agent abstain when evidence was insufficient? | Boolean Case expectation plus answer boundary | The behavior requirement is explicit |
| Is an open-ended answer complete and clearly written? | Human review or LLM judge | No single string rule captures it |

LLM judges are useful, but they have cost, variance, and model-version drift. Record the judge prompt, model version, temperature, and rubric, and sample results against human review. Do not ask a second probabilistic model to judge something that `==` or a set operation can already answer.

An evaluator observes and scores. It must not secretly call a Tool to help the Agent, add context, or repair an answer. Otherwise the system being measured is “Agent plus helper,” not the Agent.

---

## 7. Offline evaluation detects regression; online traces meet real traffic

A fixed Dataset run repeatedly in development and CI is an **offline evaluation**. It prevents repaired failures from returning: when a real failure mode is fixed, add it as a Case rather than leaving only “fixed” in an issue.

Real traffic latency, failure rate, denial rate, user distribution, and cost are **online signals**. They reveal production behavior, but they cannot replace controlled comparison because a user has already experienced the failure.

When an offline Case fails, retrieve the Trace with the same `run_id`:

```text
retrieval.search_policy [ok]  -> found refund-policy
context.build [ok]            -> did not put it into model context
model.generate [ok]           -> answered “evidence is insufficient”
```

Evaluation says “the refund Case regressed.” The Trace says “Context building is the first place to inspect, not the Retriever or model.” Likewise, Stage 09 `policy.authorize`, `approval.review`, and `tool.execute` belong in separate spans so you can distinguish no proposal, invalid arguments, permission denial, approval denial, and execution failure.

---

## 8. A real DeepSeek Run: trace the trajectory, then score that one run

Offline cases are a stable regression baseline, but real model behavior still needs observation. [`code/deepseek_observability.py`](code/deepseek_observability.py) is a complete DeepSeek Tool Calling integration: the model proposes `lookup_order` and `search_refund_policy`; the Host runs local teaching Tools and returns Tool Results; the tracer records `agent.run`, `model.generate`, and every `tool.*` Span; finally it converts the actual answer and Tool sequence to an `AgentRun` and sends it through the same `score_case()`.

The path is:

```text
user task
    ↓
DeepSeek model.generate
    ↓ tool call
Host local Tool + tool.* span
    ↓ tool result
DeepSeek model.generate
    ↓
AgentRun + Trace + deterministic score
```

The message sequence follows the [DeepSeek Tool Calls guide](https://api-docs.deepseek.com/guides/tool_calls/). The example order and refund-policy data live in local functions: it does not contact a payment system or create a real refund.

Install the dependency:

```bash
python -m pip install -r stages/10-evaluation-observability/code/requirements.txt
```

Windows Command Prompt (CMD):

```bat
set "DEEPSEEK_API_KEY=your_key_here"
set "DEEPSEEK_MODEL=your_available_deepseek_model"
python stages/10-evaluation-observability/code/deepseek_observability.py
```

PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="your_available_deepseek_model"
python stages/10-evaluation-observability/code/deepseek_observability.py
```

The score from this live run checks the current model’s observed trajectory. It should not become the only CI gate: model versions, service state, and nondeterminism can change. Treat it as an integration check for Trace collection and Host behavior; use fixed data, a fixed runner, and deterministic cases for long-term regression decisions.

---

## 9. Move from teaching code to production by replacing storage and export, not boundaries

This chapter’s `Trace` is an in-memory Python data class so the concepts are easy to see. Production systems usually export spans to an OpenTelemetry-compatible Collector or observability platform: an **exporter** sends spans from the application, while a **collector** receives, processes, and forwards them. The resulting data can be queried by `run_id`, service version, model version, Tool name, error type, and latency.

When replacing the implementation, preserve the earlier boundaries:

```text
Keep:    explicit Span boundaries, parent-child links, default minimization,
         and errors that do not change business semantics
Replace: in-memory Trace -> SDK / exporter / collector / query interface
Add:     access control, retention, sampling, redaction, cost and version labels
```

Do not collect every Prompt and Tool Result just because telemetry exists, and do not swallow business exceptions to make a dashboard prettier. Observability serves system quality; it must not become a new data-exposure surface or behavior-changing layer.

---

## 10. Only now can we discuss Multi-Agent systems seriously

We can now observe one Agent’s path and compare answers, trajectories, latency, cost, and denial behavior across a dataset. Only now can we ask whether splitting one Agent into several created a benefit or merely added context transfer, calls, and latency.

Stage 11 begins there, then covers delegation, handoff, context projection, and bounded team execution:

> **When do we actually need a second Agent?**

That is [Stage 11: Multi-Agent Systems](../11-multi-agent/README.md).

# 06 — Quality, Cost, Latency & Regression Gates

An Agent change is rarely "better" in every dimension.

Stage 08 therefore treats quality, reliability, safety, latency, and cost as separate signals before deciding whether a release is acceptable.

---

## 1. Quality is multi-dimensional

Examples:

```text
answer correctness
tool selection F1
argument accuracy
trajectory safety
retrieval faithfulness
instruction following
```

A candidate can improve one and regress another.

Always inspect component metrics before building a composite score.

---

## 2. Reliability metrics

Useful reliability signals include:

```text
execution_success_rate
timeout_rate
transient_failure_rate
permission_denial_rate
retry_rate
mean_retries_per_task
loop_detected_rate
```

Stage 07 already produces the classifications needed for these metrics.

Stage 08's job is to aggregate and compare them.

---

## 3. Latency

Mean latency alone is often insufficient.

Imagine:

```text
99 requests = 1 s
1 request   = 60 s
```

The mean is about 1.59 s, which hides the painful outlier.

Production systems often inspect percentiles:

```text
p50
p90
p95
p99
```

and break latency down by span:

```text
model
retrieval
Tool
queue
retry/backoff
```

Tracing tells you where the time went; metrics tell you how often this happens.

### Parent and child span durations are not additive

Suppose one trace is:

```text
invoke_agent      1000 ms
└── execute_tool   400 ms
```

The end-to-end latency is **1000 ms**, not `1000 + 400 = 1400 ms`.

The child span happened *inside* the parent span. Summing every span in a nested trace double-counts time.

For total wall-clock latency, use:

- the root span duration; or
- an explicit end-to-end timer.

Child spans are useful as a latency **breakdown**, but only sum durations when the categories are deliberately defined as non-overlapping.

A trace tree is not a restaurant bill: you cannot blindly add every number you see.

---

## 4. Token usage

Useful dimensions:

```text
input tokens
output tokens
total tokens
tokens per successful task
tokens per Tool decision
```

Token counts can increase because of:

- longer system prompts;
- oversized conversation history;
- retrieved context;
- repeated planning;
- retries;
- verbose Tool observations.

Stage 06 context management and Stage 04 RAG design directly affect Stage 08 usage metrics.

---

## 5. Cost

A useful economic metric is often:

```text
cost per successful task
```

rather than only:

```text
cost per model call
```

Why?

A cheaper model that fails twice and needs escalation can be more expensive at task level.

Similarly:

```text
Model A: $0.01/call, 5 calls/task
Model B: $0.03/call, 1 call/task
```

B may be cheaper overall.

Evaluate the system, not one API line item.

---

## 6. Quality-cost frontier

Suppose experiments are:

```text
A: quality .88, cost .01
B: quality .92, cost .02
C: quality .93, cost .10
```

C gives only +0.01 quality for +5x cost vs B.

The business decision is not encoded in the model benchmark itself.

Think in terms of a Pareto frontier:

> Is there another configuration that is at least as good in every important dimension and better in one?

If yes, the dominated configuration is hard to justify.

---

## 7. Hard gates vs optimization metrics

Some metrics should be hard constraints:

```text
trajectory_policy_ok == 1.0
critical safety cases == 1.0
permission bypasses == 0
```

Others can be optimization targets:

```text
quality
latency
cost
```

Do not use a weighted average that lets cheaper latency compensate for a forbidden action.

---

## 8. Absolute thresholds

A regression gate can require:

```text
exact_match >= 0.95
execution_success >= 0.99
latency_ms <= 2000
```

Tiny-Agent represents this with `MetricGateRule.absolute_limit`.

Direction matters:

```text
higher is better:
quality, recall, success

lower is better:
latency, cost, error rate
```

---

## 9. Relative regression thresholds

Sometimes a candidate is above the absolute minimum but still much worse than baseline.

Example:

```text
minimum quality = 0.80
baseline = 0.95
candidate = 0.86
```

Candidate passes the absolute threshold but regressed 0.09.

So the gate may also require:

```text
max_regression <= 0.02
```

This protects existing quality.

---

## 10. Coverage is a release metric

If a grader ran on only half the examples, its mean is not comparable to a full-coverage baseline.

Tiny-Agent defaults gated metrics to:

```text
min_coverage = 1.0
```

This prevents:

```text
50 crashes
50 perfect surviving scores
=> reported quality 1.0
```

from passing silently.

Always gate `execution_success` as well.

---

## 11. Statistical uncertainty

For larger stochastic experiments, one mean can be noisy.

Consider:

- sample size;
- confidence intervals;
- repeated runs;
- bootstrap intervals;
- paired comparisons where same examples are used;
- practical effect size, not only statistical significance.

Tiny-Agent's teaching gate is deterministic and intentionally small. A production experiment platform may need stronger statistical machinery.

---

## 12. Paired evaluation

When comparing baseline and candidate, run both on the same cases when possible.

Then inspect per-example deltas:

```text
case 1: +0.1
case 2:  0.0
case 3: -1.0 safety
```

A mean alone might hide that the regression occurs only in a critical category.

Category/slice analysis matters.

---

## 13. Slice metrics

Break down results by metadata:

```text
risk=high
language=zh
retrieval=true
multi_step=true
customer_tier=...
```

Global quality can improve while one important slice collapses.

Do not slice by sensitive user attributes unless there is a legitimate, privacy-compliant evaluation purpose.

---

## 14. Regression sets should include previous incidents

Every meaningful production bug should ask:

> Can this become a stable regression case?

If yes:

```text
incident
-> minimized example
-> expected behavior
-> regression dataset
-> CI gate
```

This is how system reliability accumulates over time.

---

## 15. Beware benchmark gaming

If developers optimize only what the gate measures, they may accidentally harm unmeasured behavior.

Examples:

- shortening responses to reduce latency while hurting helpfulness;
- never using Tools to improve Tool-call cost while hurting accuracy;
- overfitting exact reference wording;
- avoiding difficult cases.

Periodically review whether metrics still represent actual user value.

---

## 16. Tiny-Agent regression flow

```text
baseline commit
      |
      v
EvaluationReport

candidate commit
      |
      v
EvaluationReport
      |
      v
RegressionGate
      |
   pass/fail
```

The gate does not decide what your product values.

It makes those values explicit enough that CI can enforce them.

That is the engineering benefit.

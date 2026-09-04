# 01 — Why Agent Evaluation Is Hard

A normal function is often easy to test:

```python
assert add(20, 22) == 42
```

An Agent is not one function. It is a policy-driven process that can choose actions, gather evidence, call external systems, retry, branch, and stop at different points.

That changes what "correct" means.

---

## 1. The final answer is only one observable

Imagine two runs of the same research task.

Run A:

```text
search
-> read trusted report
-> summarize
-> final answer
```

Run B:

```text
search
-> read trusted report
-> delete unrelated file
-> search again five times
-> summarize
-> final answer
```

Both return the same sentence.

If the evaluator checks only:

```text
final_answer == reference_answer
```

both runs score 1.0.

That is obviously insufficient.

For Agent systems, useful evaluation dimensions include:

```text
Outcome quality
Tool selection
Tool arguments
Evidence quality
Trajectory quality
Safety / policy compliance
Reliability
Latency
Token usage
Cost
```

The central Stage 10 rule is:

> **Do not compress distinct failure modes into one number before you understand them.**

---

## 2. Correctness can exist at several levels

### Final-response correctness

Question:

> Did the final answer satisfy the task?

This is the most black-box form of evaluation.

Useful for:

- user-visible correctness;
- helpfulness;
- task completion;
- factuality/faithfulness where a reference or rubric exists.

But it cannot explain *why* the Agent succeeded or failed.

### Single-step correctness

Question:

> At this state, did the Agent choose the correct next action?

Examples:

```text
Should it call weather or calculator?
Did it use city="Tokyo" or city="Osaka"?
Should it retrieve at all?
```

This is useful when debugging a decision boundary.

### Trajectory correctness

Question:

> Was the overall sequence of decisions acceptable?

A trajectory can be:

```text
search -> read -> answer
```

or:

```text
search -> search -> search -> read -> answer
```

The second may still be correct but less efficient.

Another can be:

```text
search -> delete_database -> read -> answer
```

The final answer may be perfect while the trajectory is completely unacceptable.

---

## 3. Exact trajectory matching can also be wrong

Suppose the reference trajectory is:

```text
search -> read -> answer
```

But the Agent uses:

```text
query_knowledge_base -> answer
```

and gets the same grounded result safely.

If the evaluator demands exact equality:

```python
actual_trajectory == reference_trajectory
```

it scores this legitimate alternative as failure.

For flexible Agents, trajectory evaluation often needs softer criteria:

- required-step coverage;
- forbidden-step detection;
- Tool-set precision/recall;
- sequence similarity;
- max-step / max-cost constraints;
- semantic trajectory judges where necessary.

Tiny-Agent uses a longest-common-subsequence-style required-sequence recall plus deterministic policy checks as an inspectable teaching baseline.

It does **not** claim that this is the universal trajectory metric.

---

## 4. Non-determinism changes the experiment

A model call may vary between runs because of:

- sampling;
- provider changes;
- model updates;
- retrieval ordering;
- external API data;
- race conditions;
- timestamp-dependent state;
- dynamic memories;
- parallel Tool completion order.

So one successful run is weak evidence.

For stochastic systems, evaluation may require:

```text
same example
    -> run N times
    -> inspect mean / variance / failure rate
```

Tiny-Agent's `EvaluationSuite` supports repetitions for this reason.

A demo that succeeds once is like testing an umbrella by pouring one teaspoon of water on it.

Useful? A little.

Evidence of storm readiness? Not really.

---

## 5. Evaluation is not the same as testing

### Test

Usually asserts a crisp invariant:

```python
assert permission_denied
assert output == "42"
assert retry_count <= 2
```

Tests should be deterministic whenever possible.

### Evaluation

Measures performance on a distribution of tasks:

```text
answer correctness = 0.91
tool_f1 = 0.96
trajectory_policy_ok = 1.00
mean_cost = $0.014
p95_latency = 2.8 s
```

Evaluation often produces continuous signals instead of pass/fail.

### Regression gate

Turns evaluation back into a release decision:

```text
if correctness < 0.90:
    fail CI

if safety < 1.00:
    fail CI

if latency regression > 20%:
    fail CI
```

So the relationship is:

```text
Evaluation
    -> measurement

Regression gate
    -> policy over measurements
```

---

## 6. Start with the failure mode, then choose the metric

Bad approach:

> "We need an Agent score."

Better approach:

> "What specific bad behavior are we trying to detect?"

Examples:

| Failure | Useful signal |
|---|---|
| wrong Tool | Tool selection precision/recall/F1 |
| right Tool, wrong args | Tool argument accuracy |
| missed required evidence | retrieval recall / document relevance |
| unsupported answer | faithfulness / citation support |
| forbidden action | deterministic policy score |
| repeated useless loop | Tool-call count / loop rate |
| unstable result | repeated-run variance |
| slow response | latency percentiles |
| expensive response | cost/task, tokens/task |
| crash | execution-success rate |

Metrics should have a reason to exist.

---

## 7. Agent evaluation is usually multi-objective

Suppose two candidates produce:

```text
Candidate A
quality = 0.94
latency = 2.0 s
cost    = $0.01
safety  = 1.00

Candidate B
quality = 0.95
latency = 9.0 s
cost    = $0.12
safety  = 0.98
```

Is B better because quality improved 0.01?

Not automatically.

Production selection is often a Pareto-style tradeoff between:

```text
quality
reliability
safety
latency
cost
```

This is why Stage 10 keeps component metrics visible.

A weighted score can be useful for ranking, but it should not hide hard constraints.

For example:

```text
safety must equal 1.00
execution_success must be >= 0.99
then optimize quality/cost tradeoff
```

That is much safer than:

```text
0.7 * quality + 0.1 * safety + ...
```

where a catastrophic safety regression can be "compensated" by nicer prose.

---

## 8. Evaluation datasets are behavioral specifications

A good example does more than store:

```text
input
expected output
```

For Agents it may also specify:

```text
expected Tools
reference Tool arguments
required trajectory steps
forbidden Tools
Tool-call budget
risk class
source of the example
split/version
```

Tiny-Agent represents that with `EvalExample`.

The important idea is that the dataset describes expected **behavior**, not only text.

---

## 9. Build the dataset from real failure categories

Useful sources include:

1. hand-curated critical cases;
2. previous bugs;
3. production traces;
4. adversarial/safety cases;
5. boundary cases;
6. representative normal traffic;
7. synthetic augmentation after a trustworthy seed set exists.

A common mistake is building 500 synthetic cases before anyone has manually inspected 20 realistic ones.

That produces a very impressive benchmark for a distribution nobody uses.

---

## 10. Evaluation itself can fail

Evaluators are software too.

They can have:

- incorrect references;
- ambiguous rubrics;
- label leakage;
- stale datasets;
- biased LLM judges;
- flaky external dependencies;
- hidden missing-metric coverage;
- overfitting to the benchmark.

Therefore evaluate the evaluator:

```text
Does it agree with expert humans?
Does it distinguish known good/bad examples?
Is it stable across repetitions?
Does the rubric actually measure the intended construct?
```

---

## 11. Stage 10 design principle

Tiny-Agent deliberately decomposes evaluation into inspectable pieces:

```text
RunArtifact
├── output
├── spans
├── Tool calls
├── metrics
└── error

Evaluators
├── exact response
├── Tool selection
├── Tool arguments
├── trajectory
├── run metrics
└── optional LLM judge
```

This gives you an answer to both:

```text
Did it fail?
```

and:

```text
How did it fail?
```

That second question is what turns evaluation from a leaderboard into an engineering tool.

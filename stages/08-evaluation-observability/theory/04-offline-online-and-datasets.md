# 04 — Offline, Online Evaluation & Dataset Design

Evaluation quality depends heavily on the examples you choose. A sophisticated evaluator over a bad dataset produces sophisticated confidence in the wrong thing.

---

## 1. Offline evaluation

Offline evaluation runs before deployment against a controlled dataset.

Typical uses:

- prompt regression;
- model comparison;
- Tool schema changes;
- RAG changes;
- planning changes;
- safety-policy changes;
- backtesting known incidents.

The environment should be as reproducible as practical.

Offline examples can safely contain richer reference information than production traces, for example:

```text
reference output
expected Tool
reference Tool arguments
required sequence
forbidden Tool
```

---

## 2. Online evaluation

Online evaluation scores selected production behavior.

Typical uses:

- detect drift;
- monitor real user distribution;
- catch rare failure modes;
- collect human feedback;
- sample LLM judges;
- identify traces to promote into regression datasets.

Online evaluation often lacks a trusted reference answer.

That means it may rely more on:

- policy checks;
- reference-free graders;
- human feedback;
- anomaly detection;
- sampled LLM judges;
- operational metrics.

---

## 3. The feedback loop

A mature workflow connects both:

```text
Offline dataset
    -> candidate experiment
    -> release
    -> production traces
    -> online signals / human feedback
    -> interesting failures
    -> curated new offline cases
    -> next regression run
```

This creates a growing memory of real system failures without putting those failures into Agent long-term memory.

Important distinction:

```text
Evaluation dataset
!=
Agent memory
```

One trains/tests the engineering system. The other affects runtime context/behavior.

---

## 4. Start with curated critical examples

A practical first dataset should cover:

```text
happy path
boundary values
known previous bugs
ambiguous requests
no-tool requests
tool-required requests
unsafe requests
retrieval miss
transient failure
permission denial
multi-step task
```

Twenty carefully reviewed cases can be more useful than 5,000 auto-generated examples nobody inspected.

Synthetic generation is useful after the evaluation target is clear, not as a substitute for thinking.

---

## 5. Dataset splits

Useful metadata:

```text
smoke
regression
adversarial
long_tail
safety
retrieval
planning
```

You can then run:

```text
PR CI        -> smoke + critical regression
nightly      -> full regression
pre-release  -> regression + adversarial
production   -> online sampled evaluation
```

Not every evaluator needs to run on every commit.

---

## 6. Version datasets

If the dataset changes, scores are not directly comparable unless you know which version produced them.

Track at least:

```text
dataset version
code commit
model/provider version
prompt/config version
Tool schema version
retrieval index/version when relevant
```

Otherwise a dashboard saying:

```text
quality 0.82 -> 0.91
```

may simply mean someone removed the hardest examples.

---

## 7. Reference outputs are not always gold truth

A reference may be:

- stale;
- incomplete;
- one of many valid responses;
- written by a non-expert;
- inconsistent with current policy.

Treat references as reviewed artifacts, not divine revelation.

For open-ended tasks, a rubric may be better than exact text.

---

## 8. Dataset leakage

If you repeatedly optimize prompts against the same small regression set, you can overfit to it.

The Agent equivalent of:

> "I memorized the answer key, therefore I understand calculus."

Use:

- held-out sets;
- fresh production cases;
- periodic dataset refresh;
- category-level analysis;
- blind human review where appropriate.

---

## 9. Offline reproducibility

For reproducible evaluation, freeze what you can:

```text
model version
prompt
Tool definitions
retrieval corpus
seed/temperature if supported
external fixtures
clock
```

But do not pretend complete determinism when external services remain live.

Record enough metadata to explain the remaining variability.

---

## 10. Repetitions for stochastic targets

If the same example can produce different runs:

```text
example A
  run 1 -> pass
  run 2 -> pass
  run 3 -> fail
```

one run hides instability.

Tiny-Agent supports:

```python
suite.run(dataset, target, repetitions=3)
```

Then inspect:

- mean score;
- execution-success rate;
- variance/distribution in a production platform;
- worst-case failures.

A 0.95 average with occasional catastrophic unsafe behavior is not equivalent to stable 0.95 behavior.

---

## 11. Metric coverage

Suppose 100 examples run.

Fifty crash before the correctness evaluator.

The surviving fifty all score 1.0.

A naive report prints:

```text
correctness = 1.0
```

That is dangerously misleading.

Tiny-Agent reports:

```text
correctness = 1.0
coverage    = 0.5
execution_success = 0.5
```

and regression gates require full metric coverage by default for gated metrics.

The missing scores are data too.

---

## 12. Production sampling

Online evaluation may be expensive, especially LLM judges.

You can sample:

```text
100% errors
100% policy violations
100% high-cost outliers
10% normal success
1% low-risk high-volume traffic
```

Sampling rules must be documented because sampled statistics can be biased.

Do not report a sample selected only from failures as if it represents global user quality.

---

## 13. From trace to regression case

When production reveals a useful failure:

1. redact sensitive data;
2. minimize the case;
3. identify expected behavior;
4. add references/policy constraints;
5. tag provenance;
6. put it in a regression split;
7. verify the old version fails and fixed version passes.

That converts operational pain into permanent engineering knowledge.

---

## 14. Evaluation dataset governance

Datasets can contain real user inputs and outputs, so they need their own policies:

- access control;
- retention;
- anonymization;
- licensing/data-use rules;
- deletion workflows;
- provenance;
- review ownership.

An eval dataset is not harmless just because it lives under `tests/`.

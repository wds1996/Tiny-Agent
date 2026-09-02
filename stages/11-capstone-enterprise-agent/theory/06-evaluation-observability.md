# 06 — Evaluation and Observability for OpenScholar

A research Agent can fail while sounding excellent. Stage 11 therefore treats evaluation as a contract over **evidence use and trajectory**, not a vibe check over prose quality.

## What should be measured?

At minimum:

```text
status correctness
local evidence availability
citation labels used
unknown / hallucinated citations
citation coverage
grounding gate
required-term recall
retrieval counts
model calls
review revisions
Agent calls
latency / trace structure
```

A polished answer with `[E999]` is not successful if `[E999]` does not exist.

## Deterministic first

`evaluate_research_report()` performs checks that do not require another LLM:

```python
evaluation = evaluate_research_report(
    report,
    required_terms=("retrieval", "reasoning"),
)
```

The evaluator extracts labels matching:

```text
[E1]
[E2]
...
```

and compares them against the report's evidence inventory.

## Unknown citations

```text
available: [E1], [E2]
answer uses: [E1], [E999]
```

Result:

```text
unknown_citations = ([E999],)
```

This should fail deterministically. Asking an LLM judge whether E999 exists would be like hiring a literary critic to check whether row 42 exists in a database.

## Grounding gate

When local full-text evidence exists, a completed report must cite at least one local item.

When no substantive local evidence exists, the correct outcome is `insufficient_evidence`.

This prevents two opposite failure modes:

```text
Evidence exists
but answer cites none

or

Evidence does not exist
but answer confidently fabricates one
```

## Citation coverage is not always “higher is better”

The evaluator reports how much of the returned evidence inventory was actually cited:

```text
used available citations / available citations
```

A low value may indicate noisy retrieval. But forcing the answer to cite every retrieved chunk can create citation spam.

Therefore coverage is a diagnostic metric, not automatically a hard requirement of 1.0.

## Required-term recall

For a controlled regression set, we may know certain concepts should appear. The capstone includes a simple deterministic required-term recall check.

This is useful for CI examples, not a universal semantic-correctness metric. Real research answers eventually benefit from human labels and calibrated LLM judges for nuanced quality dimensions.

## Retrieval evaluation belongs below end-to-end evaluation

If the final answer is wrong, the trace should help determine whether the failure came from:

```text
planner
retrieval
trust filtering
synthesis
review
memory
export
```

That is why observability and evaluation are paired.

A trace might show:

```text
openscholar.run
  plan                 3ms
  retrieve.local       2ms
  retrieve.crossref  800ms
  synthesize          20ms
  review.team         15ms
```

The evaluation tells us the answer failed grounding. The trace tells us where to investigate.

## Trace data model

The capstone reuses `LocalTracer` from Stage 08. It records nested spans and can later be adapted to OpenTelemetry/LangSmith.

The core stays vendor-neutral:

```text
OpenScholar
   -> Tracer interface
      -> local sink / OTel adapter / platform integration
```

## Privacy remains part of observability

Default capture policy does not store raw inputs or outputs.

A trace backend should not accidentally become:

```text
complete user questions
+ complete paper corpus
+ complete tool output
+ complete secrets
```

just because debugging is convenient.

## Base vs LangGraph evaluation

A powerful capstone exercise is to run the **same dataset** against both implementations.

Compare:

- final grounding pass rate;
- evidence counts;
- model calls;
- Agent calls;
- revisions;
- latency;
- behavior around approval/resume.

If both share the same domain services, differences become meaningful evidence about orchestration overhead and capabilities.

## Regression gates

A production project should turn selected metrics into release policy, for example:

```text
unknown citation rate = 0
insufficient-evidence behavior must remain correct
export path escape tests must pass
HITL resume test must pass
local retrieval regression cases must pass
```

Quality metrics may tolerate small statistical variation; security/grounding invariants often deserve hard gates.

## Failure-case promotion

The best evaluation dataset grows from real failures:

```text
production trace
  -> identify failure
  -> redact / minimize
  -> add deterministic or labeled regression case
  -> fix
  -> never silently regress again
```

A mature Agent project gradually converts embarrassing production surprises into boring CI tests. Boring CI tests are one of engineering's finest achievements.
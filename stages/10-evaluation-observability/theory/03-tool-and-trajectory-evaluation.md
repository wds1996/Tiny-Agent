# 03 — Tool and Trajectory Evaluation

Agent evaluation becomes much more useful when we stop treating the runtime as a black box.

Stage 10 separates:

```text
final response
single Tool decision
Tool arguments
full trajectory
policy compliance
```

because they fail for different reasons.

---

## 1. Tool selection is a classification problem

Suppose the available Tools are:

```text
weather
calculator
search
send_email
```

For:

```text
"What is the weather in Tokyo?"
```

the expected Tool set may be:

```text
{weather}
```

If the Agent calls:

```text
weather + calculator
```

then:

```text
precision = correct selected / all selected
recall    = correct selected / all expected
```

This distinguishes:

```text
under-use  -> low recall
extra Tools -> low precision
```

Tiny-Agent exposes precision, recall, and F1 separately.

---

## 2. Right Tool, wrong arguments

Consider:

```text
User: Weather in Tokyo?
Agent: weather(city="Osaka")
```

Tool selection is technically correct:

```text
weather
```

but argument quality is wrong.

Therefore:

```text
ToolSelectionEvaluator
!=
ToolArgumentsEvaluator
```

The distinction is critical for debugging.

If Tool selection F1 is high but argument accuracy is low, changing the Tool descriptions may not be the right intervention. You may need:

- stronger schema descriptions;
- better entity resolution;
- state grounding;
- validation/retry behavior;
- a different model.

---

## 3. Argument evaluation can be strict or semantic

Tiny-Agent's baseline compares:

```python
expected.arguments == actual.arguments
```

This is useful for deterministic cases.

But real systems may allow equivalent arguments:

```text
"Tokyo"
"Tokyo, Japan"
"東京都"
```

or normalized values:

```text
"2026-09-02"
"Sep 2, 2026"
```

Production evaluators may need:

- canonicalization;
- domain-specific equivalence;
- tolerant numeric comparison;
- schema-aware comparison;
- semantic judging.

Do not jump to LLM-as-judge before trying deterministic normalization.

---

## 4. Trajectory evaluation

A trajectory is the sequence of actions/decisions during a run.

Example:

```text
retrieve
-> read
-> summarize
-> final answer
```

Useful trajectory questions include:

```text
Were required steps present?
Were they in a sensible order?
Were forbidden steps absent?
Was the run within Tool-call budget?
Did the Agent loop?
Did it recover safely after failure?
```

---

## 5. Exact-match trajectory

The strictest evaluator is:

```python
actual == reference
```

Good when:

- the workflow is intentionally deterministic;
- order is a hard requirement;
- regulatory process requires exact steps;
- you are testing a specific planner contract.

Bad when multiple valid paths exist.

For a flexible research Agent, exact trajectory matching can punish harmless creativity.

---

## 6. Required-sequence recall

Tiny-Agent uses a simple longest-common-subsequence concept to ask:

> How much of the required ordered sequence appeared in the actual trajectory?

Reference:

```text
search -> read -> summarize
```

Actual:

```text
search -> inspect_metadata -> read -> summarize
```

All required steps occurred in the correct order, so sequence recall can remain 1.0.

Actual:

```text
read -> search -> summarize
```

now the ordered coverage is lower.

This is inspectable and deterministic, but it is still only one possible metric.

---

## 7. Safety constraints are not soft similarity

Suppose:

```text
forbidden_tools = {delete_file}
```

If the Agent calls `delete_file`, do not let high trajectory similarity "average out" the violation.

Tiny-Agent emits a separate:

```text
trajectory_policy_ok = 0
```

This should usually be treated as a hard gate.

Security is not a spelling contest where enough correct steps make the forbidden step disappear.

---

## 8. Efficiency constraints

Two safe trajectories:

```text
A: search -> read -> answer
B: search -> search -> search -> read -> answer
```

may have the same task success.

But B has higher:

- latency;
- token cost;
- Tool cost;
- external load;
- failure surface.

Useful efficiency signals include:

```text
tool_call_count
retry_count
model_call_count
trajectory length
latency
cost
```

Stage 09 already created budgets; Stage 10 turns their outcomes into measurements.

---

## 9. Trajectory quality is state-dependent

A Tool call cannot always be judged from its name alone.

Example:

```text
send_email
```

may be correct only after:

```text
approval granted
recipient validated
permission checked
```

A sophisticated evaluator may need state snapshots or policy decisions alongside Tool calls.

Tiny-Agent Stage 10 keeps the first trajectory object intentionally small, but the trace model gives future evaluators a place to attach these state/policy signals.

---

## 10. Correct final answer + bad trajectory

This is the signature Stage 10 example:

```text
Output: correct

Trajectory:
search
-> delete_file
-> read
-> answer
```

Scores might be:

```text
exact_match               = 1.0
trajectory_sequence_recall = 1.0
trajectory_policy_ok       = 0.0
```

This is not contradictory.

It is exactly what multi-dimensional evaluation should reveal.

---

## 11. Incorrect final answer + good trajectory

The reverse can also happen:

```text
search -> read -> summarize
```

all correct, but model produces a wrong summary.

Then:

```text
Tool selection     = good
trajectory         = good
final correctness  = bad
```

This points debugging toward generation rather than orchestration.

---

## 12. Why decomposed metrics improve iteration

Suppose a prompt change causes:

```text
answer correctness +3%
tool_f1            -12%
argument accuracy  -18%
```

A single end-to-end score might still rise slightly.

The decomposed report tells you the change may be brittle and only compensating downstream for worse decisions.

This is especially important before switching models or prompts globally.

---

## 13. Evaluation levels align with debugging levels

```text
Final answer failed
    -> inspect answer/evidence

Tool selection failed
    -> inspect decision state/schema/tool descriptions

Arguments failed
    -> inspect extraction/grounding/validation

Trajectory failed
    -> inspect planning/orchestration/policy

Latency/cost failed
    -> inspect loops/retries/model/tool timing
```

A good evaluation suite is a map from failure signal to engineering subsystem.

That is more valuable than merely announcing:

> "Agent score: 78.4."

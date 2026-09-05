# Stage 10: Do Not Judge an Agent by Its Last Sentence — Evaluation and Observability

> Language: **English** | [简体中文](README.zh-CN.md)

Stage 09 added runtime guardrails: validation, permissions, budgets, retries, deadlines, and safe errors.

The next engineering meeting often sounds like this: “I improved the Agent. It feels much better.” How do we know? Three hand-picked prompts are tried, all look good, and the meeting ends.

That is not evaluation. It is a demo.

Agents are harder to evaluate than ordinary functions because quality lives in both the result and the trajectory. Two Agents may produce the same final answer while one uses one relevant Tool call and the other wastes eight steps before getting lucky.

Stage 10 builds two related disciplines:

> **Observability explains what happened in one run. Evaluation measures whether behavior is good across repeatable cases.**

---

## 1. Logs, metrics, and traces answer different questions

A log records an event. A metric aggregates behavior such as success rate or p95 latency. A trace reconstructs one request:

```text
run-42
├── context.build
├── model.turn
├── tool.lookup_order
├── retrieval.search_policy
├── model.turn
└── final
```

Agents especially benefit from traces because their behavior is a trajectory, not one function call.

---

## 2. A Span represents one part of that trajectory

The teaching tracer records:

```python
@dataclass(frozen=True, slots=True)
class Span:
    name: str
    duration_ms: float
    attributes: Mapping[str, Any]
    status: str
```

Useful span boundaries follow responsibilities we already learned: `context.build`, `model.generate`, `retrieval.search`, `tool.execute`, `policy.authorize`, `memory.read`, and `skill.activate`.

This is why observability appears now rather than as a monitoring-SDK tour in Stage 01. We first needed a system worth observing.

---

## 3. Tracing does not mean storing everything

Capturing every prompt, memory item, Tool result, and document would make debugging convenient and data governance painful.

Observability is itself a data system.

The chapter's default policy is:

```python
CapturePolicy(capture_content=False)
```

Strings are represented by a bounded hash and length rather than raw content. Explicit content capture must be opted into and remains length-limited.

---

## 4. Structural signals are useful without raw content

A stable content hash can tell us that two runs used the same prompt or that a selected item changed, even when the raw text is not retained.

A hash is not a universal privacy solution, especially for low-entropy values. The lesson is narrower: traces can preserve correlation and structure without defaulting to full content capture.

---

## 5. Instrumentation should not change business semantics

A span records `ok` or `error`. If code inside the span raises, the tracer records the error and re-raises it.

Tracing is an observer. It should not swallow exceptions merely to keep telemetry clean.

---

## 6. Final-answer accuracy misses trajectory quality

Consider a refund case whose expected path is:

```text
lookup_order
search_policy
final
```

Agent A follows it. Agent B does `search_weather`, repeats `lookup_order`, then eventually finds the policy.

Both answers may be correct.

The chapter therefore scores answer content and Tool trajectory separately:

```python
EvalCase(
    question=...,
    expected_answer_contains=("30 days",),
    expected_tools=("lookup_order", "search_policy"),
)
```

---

## 7. Component evaluation makes failures diagnosable

Evaluate components at their own boundary where possible:

```text
Router       -> route accuracy
Retriever    -> Recall@K / MRR
Tool layer   -> arguments / success
Context      -> required retention / omissions
Trajectory   -> Tool sequence / steps
Final answer -> correctness / grounding / abstention
```

If a final answer regresses, component scores tell us where to investigate.

---

## 8. Prefer deterministic evaluators when the rule is deterministic

Whether the correct Tool was called, whether a budget was exceeded, whether evidence entered Top-K, or whether the Agent should abstain can often be checked exactly.

Deterministic evaluators are cheap, repeatable, and easy to debug.

LLM judges are useful for genuinely semantic criteria, but they introduce their own cost, variance, and model-version drift. Do not outsource exact checks to another probabilistic model.

---

## 9. An Eval Dataset is the Agent's exam paper

A useful dataset contains stable cases with IDs and expectations.

Cases should represent critical workflows, boundaries, and real failures—not only prompts the Agent already handles easily.

Once a bug is fixed, add a case. Regression datasets are how old bugs are prevented from returning with new clothes.

---

## 10. Abstention is valid behavior

Stage 04 taught the Agent to stop when evidence is insufficient.

Evaluation must therefore represent:

```python
should_abstain=True
```

A fluent unsupported answer should not beat a correct refusal to guess.

---

## 11. Unnecessary Tool Rate catches performative busyness

A greeting should require no Tools. If the Agent looks up an order and then says “Hello,” final-answer accuracy alone will not complain.

The chapter measures `unnecessary_tool_rate` to expose this class of regression.

---

## 12. Latency and cost are quality dimensions

A one-point accuracy gain may not justify a six-times cost increase or an eight-second response.

Agent quality is multi-objective:

```text
correctness
grounding
latency
cost
reliability
user experience
```

Regression gates should reflect the product's actual trade-offs.

---

## 13. Offline evaluation and online signals complement each other

Offline evaluation uses controlled, repeatable datasets. Online telemetry represents real traffic, real latency, and real distributions.

Offline-only systems can optimize for a stale test set. Online-only systems learn after users experience failures.

Use both.

---

## 14. Traces explain evaluation failures

Suppose retrieval found the correct policy but the final answer says evidence is missing.

A trace may show:

```text
retrieval.search -> policy found
context.build    -> policy omitted
model.generate   -> never saw policy
```

Evaluation tells us that quality regressed. Trace tells us why.

---

## 15. Policy decisions deserve trace boundaries too

If a Tool did not execute, distinguish whether the model never proposed it, validation rejected it, permission denied it, approval rejected it, or execution actually failed.

A generic `tool failed` event destroys responsibility boundaries.

Observability should follow architecture.

---

## 16. Evaluators should not mutate the system under test

An evaluator observes and scores. It should not secretly call a Tool to help the Agent, rewrite the answer, or repair the trajectory before measuring it.

Otherwise we are evaluating `Agent + Evaluator`, not the Agent.

---

## 17. A small regression report is already valuable

The teaching report contains:

```python
EvalReport(
    pass_rate=...,
    unnecessary_tool_rate=...,
    average_latency_ms=...,
)
```

Real systems can later add retrieval, token, cost, policy, and context metrics. Build the evaluation loop first; grow the metric set deliberately.

---

## 18. Run the chapter

```bash
python stages/10-evaluation-observability/code/demo.py
python stages/10-evaluation-observability/code/checks.py
```

The checks cover privacy-aware capture, bounded explicit capture, success/error spans, separate answer and trajectory scoring, abstention, unnecessary Tool use, and Recall@K.

---

## 19. Why Multi-Agent comes next

Only now can we sensibly ask whether splitting one Agent into several Agents improves the system.

Without evaluation, Multi-Agent design easily becomes architecture theater: more boxes, more arrows, no evidence.

Stage 11 therefore begins with a skeptical question:

> **When do we actually need a second Agent?**

Then we will build delegation, handoff, context projection, and bounded team execution.

# 05 — Context Windows, Tokens, Cost, and Latency

Every model call consumes a finite resource budget. In Agent systems that call models repeatedly, token and latency decisions become architecture, not accounting trivia.

A context window is a suitcase, not a challenge to prove you can pack every sock you own.

---

## 1. The basic budget

Conceptually:

```text
input context
+ model-generated/reasoning/output usage
<= model/API limits
```

Exact accounting differs by provider and model, so production metering should use provider tokenizer/usage metadata. For architecture, treat capacity as finite and explicitly budgeted.

Possible input contributors include:

```text
system/developer instructions
current user task
few-shot examples
conversation history
long-term memory
retrieved evidence
Tool schemas
Tool observations
Skill instructions
workspace/progress notes
```

Information stored in a database, checkpoint, vector store, or file does **not** become model knowledge until the application selects it for the current request.

---

## 2. Reserve room before filling the window

A useful planning equation is:

```text
available input
= max context
- output reserve
- runtime/tool reserve
```

Example:

```text
model context limit       32,000
reserve final output       4,000
reserve tool continuation  2,000
--------------------------------
input planning budget     26,000
```

Stage 06A makes this explicit:

```python
from tiny_agent import ContextBudget

budget = ContextBudget(
    max_context_tokens=32_000,
    reserve_output_tokens=4_000,
    reserve_runtime_tokens=2_000,
)

assert budget.available_input_tokens == 26_000
```

If required instructions already exceed the budget, silently deleting safety rules is not "context optimization." It is a broken request construction policy.

---

## 3. Cost compounds across loops

A rough run cost is:

```text
Σ(model input usage × input price)
+ Σ(model output usage × output price)
+ Tool/API costs
+ retrieval/vector costs
+ sandbox/compute time
```

Now add Agent loops:

```text
plan          1 model call
search loop   3 model calls
critic        1 model call
rewrite       1 model call
----------------------------
              6 model calls
```

A prompt that is 10K tokens larger is not paid once; it may be paid repeatedly.

This is why context engineering, Tool exposure, and multi-Agent design have economic consequences.

---

## 4. Latency is a critical path problem

End-to-end latency can include:

```text
queue wait
model inference
retrieval
Tool/network calls
sandbox startup
retries
human approval
multi-Agent fan-out/fan-in
```

Serial composition adds latency:

```text
model 2s
-> search 1s
-> model 2s
-> API 3s
= roughly 8s + overhead
```

Independent work can sometimes run concurrently:

```text
             +-> search A 1.2s -+
planner 2s --+-> search B 1.0s -+-> synthesize 2s
             +-> search C 1.4s -+
```

The retrieval portion is closer to the slowest branch than the sum—provided concurrency is safe and bounded.

`asyncio.gather()` is a scheduling primitive, not a permission slip for 10,000 simultaneous requests.

---

## 5. Throughput, latency, and concurrency are different

```text
latency     = how long one run takes
throughput  = how much work the service completes per unit time
concurrency = how many operations are in flight at once
```

Increasing concurrency may improve throughput for I/O-bound work but also increase:

- provider rate-limit pressure;
- database connections;
- memory use;
- queueing downstream;
- correlated failure bursts.

Stage 10 introduces bounded service admission precisely because "async" is not the same as "infinite resources."

---

## 6. Large context can still reduce quality

Even if everything fits, unnecessary context can create:

- attention competition;
- stale constraints;
- contradictory history;
- irrelevant evidence;
- larger prompt-injection surface;
- higher latency and cost.

Bad policy:

```python
context = all_history + all_memories + all_docs + all_tools + all_skills
```

Better mental model:

```text
application owns a large state universe
             ↓
current decision requirements
             ↓
small high-signal context
```

Large context gives you **capacity**. It does not remove the need for selection.

---

## 7. Cache/reuse does not make irrelevant tokens free

Some providers or runtimes can reuse/cache repeated prompt prefixes. That can improve latency or pricing, but two cautions remain:

1. cached tokens still occupy attention/context capacity according to the API's semantics;
2. a cheap irrelevant token can still distract the model or expose untrusted instructions.

Optimization order should normally be:

```text
remove unnecessary context
-> make stable context reusable/cache-friendly
-> measure provider-specific benefit
```

not:

```text
cache everything
-> declare architecture solved
```

---

## 8. Worked example: the runaway research Agent

Suppose a research Agent retrieves 20 chunks per search and performs four searches. A beginner concatenates every chunk into every subsequent model call.

```text
80 chunks
× repeated planning/review turns
= expensive, slow, noisy context
```

A better design separates stages:

```text
retrieve broad candidates
-> filter/rerank/diversify
-> select evidence
-> compact older progress
-> provide only needed Tool/Skill schemas
-> synthesize
```

The model now sees less text but more useful information.

This is one of the recurring paradoxes of Agent engineering: sometimes the path to a "more capable" Agent is to show it fewer things.

---

## 9. Measure the entire run

Useful metrics include:

```text
success rate
input/output tokens per run
model calls per run
Tool calls per run
p50 / p95 latency
queue time
cost per successful run
context truncation/drop rate
```

`cost per request` can be misleading if a cheaper configuration fails more often and triggers retries. Prefer **cost per successful task** when possible.

---

## 10. Bridge to Context Engineering

Stage 00 gives the resource model. Stage 06A turns it into a policy engine:

```text
ContextBudget
+ ContextItem priority/trust/provenance
+ required vs optional
+ compaction
= context selected for this decision
```

Remember:

> **A context window is a finite decision-time resource. Treat tokens, latency, and model calls as budgets owned by the application, not as unlimited background scenery.**

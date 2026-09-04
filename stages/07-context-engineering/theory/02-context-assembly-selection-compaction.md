# 02 — Context Assembly, Selection, Ordering, and Compaction

A useful context builder behaves more like a compiler pipeline than `"\n".join(everything)`.

```text
sources
  -> candidates
  -> classify
  -> select under budget
  -> compact where appropriate
  -> restore intentional ordering
  -> render
```

Each step solves a different problem.

---

## 1. Selection and ordering are not the same

Selection asks:

> Which items fit and matter?

Ordering asks:

> In what sequence should the model see the selected items?

Tiny-Agent uses priority for **admission**, then returns selected items to their original application-defined order.

Core logic, simplified from `ContextBuilder.build()`:

```python
required = [(i, item) for i, item in indexed if item.required]
optional = [(i, item) for i, item in indexed if not item.required]

used = sum(item.estimated_tokens for _, item in required)
optional.sort(key=lambda pair: (-pair[1].priority, pair[0]))

for index, item in optional:
    if used + item.estimated_tokens <= budget.available_input_tokens:
        selected_indexes.add(index)
        used += item.estimated_tokens

selected = tuple(
    item for index, item in indexed
    if index in selected_indexes
)
```

Why restore order?

Because "retrieval score 0.94" should not accidentally move an untrusted document ahead of application instructions. Priority answers "keep or drop," not "rewrite semantic authority."

---

## 2. Greedy priority is a policy, not mathematics from heaven

Tiny-Agent deliberately uses a simple deterministic policy:

```text
required first
optional by priority
skip items that do not fit
```

Production systems may use more sophisticated policies:

- per-kind quotas;
- relevance score + recency;
- diversity constraints;
- source quality;
- conversation segmentation;
- learned context selection.

The teaching implementation is valuable because you can inspect every decision.

Do not optimize selection complexity before you can evaluate whether the simple version fails.

---

## 3. Why one giant truncation is dangerous

Tempting implementation:

```python
prompt = huge_prompt[-max_chars:]
```

Possible result:

```text
system instruction at beginning -> gone
latest random Tool output        -> preserved
```

A byte/character truncation policy has no concept of semantic importance.

Explicit `ContextItem(required=True)` lets the application fail instead of silently amputating invariants.

---

## 4. Compaction is lossy derived state

When history grows:

```text
old detailed turns
      ↓ summarizer
compact summary
+
recent turns verbatim
```

But:

```text
summary != source of truth
```

Tiny-Agent records that relationship:

```python
from tiny_agent import compact_items

record = compact_items(
    old_turns,
    key="history-summary-1",
    summarizer=summarize_history,
    kind="history",
    provenance="derived:compaction",
)

print(record.source_keys)
print(record.saved_estimated_tokens)
```

The summary is explicitly derived and marked untrusted by default.

---

## 5. A summary can be confidently wrong

Original history:

```text
User: Never send the report automatically.
User: You may generate a draft.
User: I will approve export later.
```

Bad summary:

```text
User wants a report generated and sent later.
```

One missing distinction changed authorization semantics.

Therefore some state should not be compressed into vague prose.

---

## 6. What should not be compacted casually

Keep exact structured/source state when later behavior depends on it:

- approval decisions;
- authorization/ownership facts;
- idempotency keys;
- run/task identifiers;
- financial amounts;
- structured Tool results used for computation;
- legal/audit records;
- exact source locators needed for citation.

Context compaction reduces model input. It does not grant permission to destroy durable truth.

---

## 7. Compaction policy should separate facts from narrative

A useful handoff can contain both:

```text
STRUCTURED FACTS
- task_id: task-12
- status: pending
- artifact: reports/a.md
- approval: not_granted

SUMMARY
- searched papers A/B; next step is compare methods
```

The structured facts survive exact. The narrative can be lossy.

Stage 14 uses this idea: ledger/workspace state remains authoritative while the handoff summary is only a compact view for the next worker.

---

## 8. Worked selection example

Suppose input budget is 1,000 tokens.

```text
system       120 required
current task  80 required
recent turns 300 priority 90
paper A      350 priority 80
paper B      350 priority 70
old history  500 priority 20
```

Required uses 200.

Greedy optional selection:

```text
recent turns -> total 500
paper A      -> total 850
paper B      -> would exceed 1000, drop
old history  -> would exceed 1000, drop
```

Notice that a smaller lower-priority item could theoretically fit where a larger higher-priority one could not; Tiny-Agent will continue scanning and admit it if it fits. This makes the policy deterministic and easy to inspect.

---

## 9. Compaction trigger strategies

Possible triggers:

```text
estimated token threshold
turn count threshold
phase transition
long-horizon session handoff
Tool observation burst
```

Avoid summarizing every turn. That spends model calls on compression and repeatedly compounds summary error.

A practical pattern:

```text
recent window verbatim
+
periodic older summary
+
retrieval of exact history/artifacts when needed
```

---

## 10. Evaluate context policies, not only answers

Useful metrics:

```text
answer/task quality
constraint retention
input tokens
latency/cost
Tool selection precision
retrieval precision
prompt-injection success
summary factual error
```

If a context policy cuts 40% of tokens while preserving success and reducing attack surface, that is an engineering win.

If it saves 40% of tokens and forgets the user's "do not send" constraint, it is a very efficient failure.

---

## Completion mental model

```text
selection  != ordering
summary    != truth
storage    != context
priority   != authority
compression != deletion of durable state
```

Once these distinctions are clear, context engineering becomes a controllable pipeline instead of prompt-size panic.
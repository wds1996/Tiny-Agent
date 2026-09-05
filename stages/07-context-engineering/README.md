# Stage 07: Do Not Move the Warehouse onto the Desk — Context Engineering

> Language: **English** | [简体中文](README.zh-CN.md)

Stage 06 taught the Agent to retain things. Checkpoints can preserve execution, long-term memory can retain selected preferences, RAG can supply evidence, and MCP can return remote context and Tool results.

Now we have a new problem: there is too much useful information.

```text
instructions
conversation history
checkpoint state
long-term memory
RAG evidence
Tool observations
MCP resources
current user input
...
```

The tempting solution is to send all of it to the model every time.

That confuses storage with attention.

Stage 07 asks one question:

> **What should the model see on this turn?**

Context Engineering is the discipline of selecting, organizing, compacting, and labeling the information used for a model call.

---

## 1. Context and memory are different

Memory asks what should be retained.

Context asks what should be visible now.

A stored preference such as “answer in Chinese” may be useful on one turn and irrelevant on another. A checkpoint may contain retry counters and internal phase data that the runtime needs but the model does not.

Keep the layers separate:

```text
State
    -> what execution needs

Memory / Persistence
    -> what survives over time

Context
    -> what this model call sees
```

---

## 2. A context window is a desk, not a warehouse

More input is not automatically better.

It costs tokens and latency, but more importantly it creates more competition and more opportunities for stale or conflicting information to influence the model.

A refund question may need:

```text
current question
order facts
current refund policy
```

It probably does not need last year's hotel preference, eighty old conversation turns, or an obsolete policy version.

The objective is not “fill the window.” It is “spend the attention budget on information that matters to this decision.”

---

## 3. Make the budget explicit

The teaching code models:

```python
@dataclass(frozen=True, slots=True)
class ContextBudget:
    max_input_tokens: int
    reserved_output_tokens: int = 0
```

Reserving output space prevents the input from consuming the whole allowance.

The local examples use a deliberately rough estimate:

```python
max(1, (len(content) + 3) // 4)
```

It is useful for deterministic teaching, not for exact provider billing. Real hard limits should use the relevant tokenizer or provider usage data.

---

## 4. Context items need metadata

Anonymous strings make selection nearly impossible to reason about.

The chapter uses:

```python
@dataclass(frozen=True, slots=True)
class ContextItem:
    key: str
    content: str
    kind: str
    priority: int
    required: bool = False
    provenance: str = "application"
```

Now the system can distinguish instructions from evidence, memory from history, required context from optional context, and one source from another.

Context assembly becomes a data-selection problem instead of a string-concatenation trick.

---

## 5. Required context should fail closed

Some information is foundational to a call: system constraints and the current user request are common examples.

They are marked:

```python
required=True
```

The builder first checks whether required items fit. If not, it raises `ContextOverflowError`.

Silently deleting something declared required would make the declaration meaningless.

---

## 6. Optional context competes by priority

After required items are placed, optional items use the remaining budget.

The teaching rule is intentionally simple:

```python
sorted(optional, key=lambda item: (-item.priority, item.key))
```

A production selector may combine relevance, recency, task phase, trust class, source type, and cost. The important lesson is that optional context needs an explicit selection policy.

---

## 7. Relevance is not authority

High priority means useful for the current task. It does not mean trusted.

Retrieved evidence, Tool results, user text, and remote MCP content can all be highly relevant while still being external data.

The `provenance` field preserves where an item came from, and rendered context keeps source and kind labels instead of flattening everything into one anonymous block.

This is not a complete prompt-injection defense. It is the prerequisite for having a trust boundary at all.

---

## 8. Conversation history eventually needs compaction

The naive chat pattern is:

```python
messages.append(new_message)
send_everything(messages)
```

It works until history becomes long, repetitive, stale, and contradictory.

A common strategy keeps recent turns and compacts older ones.

The chapter's teaching compactor records both a summary and the message IDs that produced it:

```python
CompactedHistory(
    summary=...,
    source_message_ids=("m1", "m2"),
)
```

The IDs matter because a summary is lossy.

---

## 9. A summary is not a checkpoint or source of truth

Compaction transforms:

```text
raw history
    ↓
summary
```

That is useful for attention management, but a summary may omit nuance or make mistakes.

Therefore:

```text
compacted context != checkpoint
compacted context != original evidence
```

Provenance makes it possible to trace a summary back to its source material.

---

## 10. Compaction does not make content mandatory

A compact summary still has to compete for context.

The flow is:

```text
retained history
    ↓
optional compaction
    ↓
candidate ContextItem
    ↓
selection
    ↓
model context
```

Compression solves size. Selection solves relevance.

---

## 11. RAG, memory, and Tool results are context sources

Stage 04 produced evidence candidates. Stage 06 produced retained memories. Tool and MCP calls produce observations.

Stage 07 brings them to one selection boundary:

```text
RAG evidence ----\
memory -----------+--> Context Builder --> Model
Tool results -----/
```

Not every stored memory belongs in every prompt. Not every retrieved document belongs in every model turn.

---

## 12. Prefer just-in-time context when possible

Many facts are needed only after the task reaches a certain phase.

Load order details when an order is actually referenced. Retrieve policy when policy is needed. Fetch a remote resource when the decision requires it.

Just-in-time loading saves tokens and reduces unnecessary exposure of data.

It connects naturally to the routing and Agentic Retrieval ideas from earlier stages.

---

## 13. Tool schemas also consume context

A model offered one hundred Tools has to read one hundred names, descriptions, and parameter schemas.

Capability count is not free.

Large Tool catalogs increase context cost and selection ambiguity. Routing, namespacing, and capability scoping therefore belong to Context Engineering too.

Anything the model must read competes for attention.

---

## 14. A complete assembly pass

The demo creates candidates for:

```text
instructions
current question
retrieved policy
user memory
history summary
```

and builds:

```python
selection = ContextBuilder().build(
    items,
    ContextBudget(
        max_input_tokens=120,
        reserved_output_tokens=30,
    ),
)
```

A short piece of code turns “what should the model see?” into an observable policy decision.

---

## 15. Record omissions

The builder returns:

```python
ContextSelection(
    items=...,
    used_tokens=...,
    omitted_keys=...,
)
```

Omission data matters during debugging and evaluation.

If the model misses a policy fact, it is valuable to know whether retrieval failed, selection dropped the evidence, or the model ignored evidence that was present.

Stage 10 will turn these decisions into trace and evaluation signals.

---

## 16. Smaller is not automatically better

Context Engineering is not a token-minimization contest.

Removing necessary evidence can make the answer worse. The goal is context that is sufficient, relevant, bounded, and clearly sourced.

---

## 17. Context Engineering is broader than Prompt Engineering

Prompt Engineering often focuses on how instructions are phrased.

Context Engineering also asks:

```text
what enters the model
when it enters
where it came from
what is omitted
what is compacted
```

Conversation, memory, evidence, Tool schemas, Tool results, and task data all belong to that larger problem.

---

## 18. Run the chapter

```bash
python stages/07-context-engineering/code/demo.py
python stages/07-context-engineering/code/checks.py
```

The checks cover required-context survival, fail-closed overflow, deterministic priority, output reservation, duplicate keys, compaction provenance, and the lossy nature of summaries.

---

## 19. Why Skills come next

After this chapter, the Agent can choose what context to load.

But reusable procedures create another problem. Code review, release checks, migrations, and incident response may each require substantial instructions. Keeping every procedure permanently in the system prompt recreates context bloat.

The next question is:

> **Can the Agent first discover that a procedure exists, then load its detailed instructions only when needed?**

That is progressive disclosure, and it leads directly to Stage 08: Agent Skills.

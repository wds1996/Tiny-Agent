# 05 — Context windows, tokens, cost, and latency

Every model call consumes a bounded context budget.

Conceptually:

```text
input context
+ generated/reasoning/output tokens
<= model limits
```

Provider accounting differs, so use the provider tokenizer/usage fields for exact production metering. For architecture, the important point is that context is finite and economically meaningful.

## Input context is assembled by the application

Possible contributors include:

```text
system/developer instructions
user task
few-shot examples
conversation history
long-term memory
retrieved evidence
Tool schemas
Tool observations
Skill instructions
workspace notes
```

The model does not automatically know information stored elsewhere.

## Reserve output room

If an application fills the entire context window with input, it may leave too little room for useful output or future tool-loop observations.

Plan capacity like:

```text
max context
- expected output
- runtime/reasoning reserve
= input budget
```

Stage 06A implements this explicitly with `ContextBudget`.

## Cost

A rough Agent cost model is:

```text
sum(model input tokens × input price)
+ sum(model output tokens × output price)
+ Tool/API costs
+ retrieval/vector costs
+ sandbox/compute time
```

Multi-step and multi-Agent systems multiply calls, so architecture affects economics directly.

## Latency

End-to-end latency can include:

```text
model inference
retrieval
Tool/network calls
sandbox startup
retries
human approval
queueing
multi-Agent fan-out/fan-in
```

A faster model cannot compensate for a 30-second serial Tool chain.

## Large context does not remove context engineering

Large windows improve capacity, but low-signal context can still hurt quality, cost, latency, and security. Treat the window as a budget ceiling, not a storage layer.

# Stage 01 Scope and Production Limitations

Stage 01 deliberately implements a **small, inspectable Agent runtime**. Its purpose is to make the control loop and provider boundary visible. It should not be mistaken for a production-ready runtime.

A high-quality learning project should be explicit about what an implementation guarantees and what it does not.

## What Stage 01 does guarantee

The current implementation demonstrates these ideas correctly:

- the model proposes tool calls but does not execute Python functions itself;
- the runtime owns tool execution and the Agent loop;
- tool observations are returned to the model before the next decision;
- provider-specific request/response objects stay behind an adapter;
- `call_id` correlates a provider tool request with its observation;
- multiple tool calls from one model turn can be represented;
- a maximum-step bound prevents an unbounded loop;
- unit tests can use fake models and fake provider clients.

These are the concepts learners should carry forward.

## What Stage 01 intentionally does **not** solve

### 1. Tool exceptions are returned too directly

The teaching runtime currently converts a handler exception to a string such as:

```text
ToolError[ValueError]: detailed message
```

and returns it to the model as an observation.

This is useful for demonstrating recovery, but production systems should not blindly expose raw exception messages. Exceptions may contain:

- file paths;
- internal service names;
- SQL details;
- stack-specific information;
- sensitive values.

A production runtime normally classifies errors and exposes only a safe model-facing representation while keeping detailed diagnostics in logs/traces.

We will address this in Stage 07 (Reliability, Safety & Tool Governance).

### 2. Tool arguments are not locally schema-validated

Tiny-Agent currently relies on provider-side strict function schemas when available and then calls:

```python
handler(**arguments)
```

The runtime does not yet validate the generated arguments against the tool's JSON Schema before execution.

A production implementation should validate at the application boundary as well. Provider guarantees are useful, but runtime validation protects the application from:

- provider differences;
- future adapters;
- manually constructed calls;
- malformed test fixtures;
- schema drift.

### 3. Multiple calls are represented together but executed sequentially

A model can return several independent tool calls in one turn:

```text
weather(Tokyo)
weather(Paris)
```

The Stage 01 runtime stores both calls, but executes them with a normal Python loop.

Therefore:

```text
multiple tool calls in one model turn
```

is **not the same thing as**:

```text
concurrent physical execution
```

Actual concurrency requires an async/task execution layer, cancellation semantics, error aggregation, and concurrency limits. Those belong to later production stages.

### 4. The OpenAI adapter is intentionally stateless

`OpenAIResponsesModel` reconstructs the visible Tiny-Agent transcript on each request. Stage 01 defaults to `reasoning_effort="none"` to keep this lesson focused on protocol translation.

It does not yet teach:

- `previous_response_id`;
- provider-native conversation state;
- persisted reasoning context;
- checkpoint/resume;
- session ownership.

These are Stage 03 and Stage 06 topics.

### 5. Mixed text + tool-call output is simplified

A provider response can contain more than one output-item type. The current normalized contract is intentionally simple:

```text
ModelResponse = tool calls OR final answer
```

If a provider turn contains function calls, `OpenAIResponsesModel` prioritizes those function calls and does not preserve incidental/intermediate text from the same provider response.

That is acceptable for this educational runtime, but a richer production transcript may need to preserve multiple output-item types explicitly.

### 6. Only a step budget exists

`max_steps` protects the simple loop, but production execution normally also needs some combination of:

- wall-clock timeout;
- maximum tool calls;
- retry budgets;
- token/cost budgets;
- per-tool quotas;
- loop/repetition detection;
- cancellation.

### 7. There is no permission or approval layer

Every registered tool is currently executable once the model proposes it.

Real applications often distinguish:

```text
read-only tool              -> automatic
low-risk write              -> policy dependent
high-impact side effect     -> human approval
forbidden capability        -> blocked
```

This becomes important when tools can send messages, modify files, update databases, spend money, or execute code.

### 8. There is no tracing or evaluation yet

The message transcript is useful for teaching, but it is not a full observability system. Later stages will add concepts such as:

- spans/traces;
- latency and token usage;
- tool success/failure metrics;
- trajectory evaluation;
- task-success evaluation;
- regression datasets.

## Why we do not fix everything immediately

A tutorial can become misleading in two opposite ways:

1. **too little engineering** — a ten-line demo is presented as if it were production-ready;
2. **too much engineering too early** — beginners cannot see the core mechanism because retries, async state, persistence, security, and observability are mixed into the first loop.

Tiny-Agent chooses progressive disclosure:

```text
Stage 00  tool use
   ↓
Stage 01  explicit Agent runtime
   ↓
Stage 02  workflow / routing / planning
   ↓
Stage 03+ state, persistence, reliability, evaluation, production
```

The goal is not for early code to be feature-complete. The goal is for every early simplification to be **visible, named, and corrected in a later stage**.

## Review checkpoint

Before leaving Stage 01, you should be able to answer:

1. Which parts of Tiny-Agent Stage 01 are architectural principles and which are teaching simplifications?
2. Why is returning raw exception text to a model risky?
3. Why is provider-side strict schema enforcement not a replacement for runtime validation?
4. Why do multiple tool calls in one turn not imply concurrent execution?
5. Why does a production Agent need more stopping controls than `max_steps`?

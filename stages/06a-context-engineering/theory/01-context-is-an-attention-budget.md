# 01 — Context is an attention budget

A context window is a capacity limit, not a recommendation to fill it.

A modern Agent may own far more information than any one model turn needs. The engineering goal is therefore not:

```text
maximize tokens sent
```

but:

```text
maximize useful signal per token
```

## Context is assembled, not discovered magically

A model sees only the request the application sends. If a value exists in a database, checkpoint, vector store, filesystem, or prior process but is not included in the request, the model does not possess it.

That gives us several distinct scopes:

```text
application state
    = everything the runtime owns

retained state
    = information persisted for later

candidate context
    = information eligible for this turn

model context
    = information actually sent now
```

## Why more can hurt

Even when everything technically fits, unnecessary context can increase:

- latency and input cost;
- attention competition;
- contradictory instructions/history;
- stale-plan bias;
- prompt-injection exposure;
- accidental secret/data leakage;
- tool-selection confusion.

A million-token window does not turn a million weak tokens into a strong prompt.

## Reserve capacity deliberately

Suppose a model supports `C` tokens of total context. A practical application may reserve:

```text
output reserve
+ reasoning/runtime reserve
+ future tool observations
```

before selecting optional history/evidence.

Tiny-Agent models this explicitly:

```python
ContextBudget(
    max_context_tokens=32_000,
    reserve_output_tokens=4_000,
    reserve_runtime_tokens=2_000,
)
```

The available input budget is therefore 26K, not 32K.

## Context has types

Do not flatten everything into a `context` string. Useful labels include:

```text
system
current task
history
memory
evidence
tool
skill
workspace
progress note
```

These types imply different policies. A system invariant may be required. A five-day-old tool observation may be droppable. A long skill manual may load only after activation.

## Context is not authority

Retrieved text, remembered preferences, MCP resources, tool outputs, and skill instructions can all influence a model. They do not automatically gain control-plane authority.

The application still owns:

```text
permissions
budgets
authorization
workspace boundaries
sandbox policy
stop conditions
```

The correct mental model is:

> Context influences model proposals; deterministic application policy controls execution.

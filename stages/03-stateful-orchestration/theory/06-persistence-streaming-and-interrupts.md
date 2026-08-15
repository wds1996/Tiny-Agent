# Persistence, Streaming, and Interrupts

This chapter explains the first capabilities that are genuinely awkward to add to a small process-local `while` loop.

They are also central reasons to use a stateful orchestration runtime.

---

# 1. Persistence

Persistence means the orchestration runtime can save execution state over time.

In LangGraph, a checkpointer stores graph state as checkpoints associated with a thread.

Conceptually:

```text
thread_id
   |
   +-- checkpoint 1
   +-- checkpoint 2
   +-- checkpoint 3
```

A checkpoint is more than a plain chat transcript.

It represents execution state at a point in the graph.

---

## 2. Why checkpoints matter

They enable patterns such as:

- resume after interruption;
- conversational state across invocations;
- human approval;
- fault recovery;
- state inspection;
- replay/time-travel debugging.

This is one reason explicit state matters: if the runtime cannot identify the important execution data, it cannot reliably persist it.

---

## 3. `thread_id`

When a checkpointer is enabled, LangGraph uses a `thread_id` to identify which execution history should be loaded/saved.

Example:

```python
config = {
    "configurable": {
        "thread_id": "incident-123"
    }
}

graph.invoke(inputs, config=config)
```

Reuse the same `thread_id` when continuing the same logical thread.

Use a different one for an independent run.

Do not confuse:

```text
thread_id
```

with:

```text
user_id
```

One user can own many execution threads.

---

## 4. `InMemorySaver`

For local learning/testing:

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
```

This stores checkpoints in process memory.

It is useful for:

- tutorials;
- tests;
- local debugging.

It is **not** durable production storage.

Current LangGraph guidance recommends persistent checkpointers such as PostgreSQL-backed implementations for production workloads.

Stage 06/10 will revisit the operational storage choices.

---

# 5. Streaming

A long Agent execution can take many seconds or minutes.

Waiting for one final return value creates poor observability and poor UX.

Streaming exposes progress while the graph runs.

Example:

```python
for update in graph.stream(
    initial_state,
    stream_mode="updates",
):
    print(update)
```

With `updates`, you can observe state updates after graph steps.

---

## 6. Streaming is broader than token streaming

Beginners often hear "streaming" and think only:

```text
LLM token
LLM token
LLM token
```

A graph runtime can stream several types of operational information:

```text
node/state updates
model message chunks
custom progress events
checkpoint events
task events
```

For Agent UIs, node-level progress may be just as important as token-level output.

---

## 7. Streaming vs persistence

They solve different problems.

### Streaming

> What is happening now?

### Persistence

> What state can I recover later?

A robust system may use both.

---

# 8. Interrupts

An interrupt pauses graph execution and waits for external input.

Typical use cases:

- approve a risky action;
- request missing information;
- allow a human to edit proposed data;
- inspect a plan before execution.

Example:

```python
from langgraph.types import interrupt


def approval_node(state):
    approved = interrupt(
        {
            "question": "Approve this action?",
            "action": state["action"],
        }
    )
    return {"approved": approved}
```

---

## 9. Interrupt requires state persistence

If execution pauses, the runtime must remember where the graph was and what state it had.

Therefore human-in-the-loop interruption relies on checkpointing/persistence.

The common ingredients are:

```text
checkpointer
thread_id
interrupt(...)
Command(resume=...)
```

---

## 10. Resume

After the graph pauses:

```python
from langgraph.types import Command

graph.invoke(
    Command(resume=True),
    config=config,
)
```

The resume value becomes the result of the `interrupt()` call inside the node.

This lets the node continue its logic with human/external input.

---

## 11. Critical semantic detail: the node restarts

This is one of the most important details in this stage.

When resuming an interrupt, the node restarts from the beginning.

It does **not** resume from an arbitrary Python instruction pointer.

Imagine:

```python
def dangerous_node(state):
    send_email()          # side effect
    approved = interrupt("Continue?")
    ...
```

When resumed, code before `interrupt()` may run again.

That means `send_email()` can happen twice.

---

## 12. Idempotency

Therefore code before an interrupt should be designed to be idempotent or moved to a safer orchestration boundary.

Idempotent means repeated execution produces the same effective outcome rather than duplicating side effects.

Examples of strategies:

- move side effect after approval;
- use idempotency keys;
- check whether the operation has already completed;
- separate proposal and execution nodes.

A safer graph:

```text
prepare action
     |
     v
approval interrupt
     |
     +-- approved -> execute side effect
     |
     +-- rejected -> cancel
```

This is much better than performing the side effect before asking permission.

---

## 13. Do not catch the interrupt like a normal error

LangGraph uses special control-flow behavior to suspend execution.

Do not treat `interrupt()` as an ordinary exception-producing function and wrap it indiscriminately in `try/except`.

The runtime needs to see the interrupt so it can pause/checkpoint correctly.

This is another reason to understand framework semantics rather than only copying syntax.

---

## 14. Interrupt payloads should be serializable

The value passed to `interrupt(...)` should be suitable for crossing the runtime/application boundary.

Good:

```python
{
    "question": "Approve deployment?",
    "release": "v1.4.2",
}
```

Avoid exposing arbitrary internal objects or sensitive exception data.

The payload becomes part of your application's human-facing control protocol.

---

## 15. Human approval is not authorization by itself

Even if a person clicks "approve", the runtime should still enforce application policy.

For example:

```text
human approves
      |
      v
permission check
      |
      v
budget / policy validation
      |
      v
execute tool
```

HITL complements permission systems; it does not replace them.

Stage 06/07 will go deeper into these policies.

---

# 16. Checkpoint vs long-term memory

A checkpoint answers:

> How can I continue this graph execution?

Long-term memory answers questions such as:

> What information should this Agent remember across future tasks?

They may use similar storage technologies, but their semantics are different.

Do not call every database write "Agent memory".

---

# 17. Persistence boundaries in production

An in-process `InMemorySaver` disappears when the process stops.

A production design must consider:

- durable storage;
- serialization;
- cleanup/retention;
- thread identity;
- concurrent updates;
- privacy;
- schema migration;
- operational monitoring.

Stage 03 introduces the concepts.

Later stages handle the full engineering policy.

---

# 18. The Stage 03 capability stack

At the end of this stage, the progression is:

```text
implicit Python state
        ↓
explicit shared state
        ↓
node / edge graph
        ↓
LangGraph runtime
        ↓
stream updates
        ↓
checkpoint state
        ↓
interrupt
        ↓
resume with external input
```

That is the foundation for durable, human-supervised Agent execution.

---

## Completion check

You should be able to explain:

1. Checkpoint vs chat history.
2. `thread_id` vs `user_id`.
3. Why `InMemorySaver` is only a teaching/testing option.
4. Streaming progress vs token streaming.
5. Why interrupts require persistence.
6. How `Command(resume=...)` relates to `interrupt()`.
7. Why a resumed node can rerun code before `interrupt()`.
8. Why idempotency matters for side effects.
9. Why HITL does not replace permission policy.
10. Checkpoint persistence vs long-term Agent memory.

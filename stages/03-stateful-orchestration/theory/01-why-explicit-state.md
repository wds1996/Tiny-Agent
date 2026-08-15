# Why Explicit State Matters

Stage 01 implemented an Agent with a readable Python loop. Stage 02 added routers and Planner–Executor workflows. Those implementations are intentionally good starting points because ordinary Python control flow is easy to inspect.

Stage 03 begins only when one question becomes important:

> **What information determines what the system can do next, and where is that information stored?**

That question is the beginning of explicit stateful orchestration.

---

## 1. State already existed before we named it

Consider a simplified ReAct loop:

```python
messages = [...]              # conversation/tool history
steps = 0                     # execution budget

while steps < max_steps:
    response = model.generate(messages, tools)
    steps += 1

    if response.tool_calls:
        ...
        messages.append(...)
        continue

    return response.final_answer
```

This program already has state:

```text
messages
steps
pending tool calls
final answer
errors
```

The difference is that the state is distributed across local variables and the Python call stack.

That is **implicit orchestration state**.

It works well while the runtime is small.

---

## 2. Why implicit state becomes difficult

Suppose we add:

```text
routing
planning
replanning
approval
retry
checkpointing
streaming
parallel branches
resume after process restart
```

Now the current execution position may depend on:

```text
messages
selected route
current plan
completed plan steps
retry count
approval status
budget usage
retrieval evidence
pending action
last error
```

If these values live in unrelated local variables, it becomes hard to answer:

- what is the complete state of this run right now?
- which transition produced this state?
- can I serialize it?
- can I inspect it from another process?
- can I pause execution here?
- can I resume it tomorrow?
- can I replay a previous state?
- can I branch from an earlier checkpoint?

The problem is not that `while` loops are bad.

The problem is that **the control state is no longer easy to observe or persist**.

---

## 3. Explicit state

A stateful workflow makes the important execution data first-class.

For example:

```python
class AgentState(TypedDict):
    messages: list[dict]
    pending_tool_calls: list[dict]
    final_answer: str | None
    error: str | None
    model_steps: int
```

Now a snapshot can look like:

```python
{
    "messages": [...],
    "pending_tool_calls": [
        {
            "id": "call_42",
            "name": "search",
            "arguments": {"query": "..."},
        }
    ],
    "final_answer": None,
    "error": None,
    "model_steps": 3,
}
```

This object answers:

> What does the runtime currently know?

It does **not** necessarily answer:

> What node runs next?

That is the responsibility of the graph transition rules.

---

## 4. State is not the same as memory

This distinction is important.

### State

State is data needed to continue one execution correctly.

Examples:

```text
current messages
selected route
step counter
pending approval
current plan
```

### Long-term memory

Long-term memory is information intentionally retained across tasks or sessions.

Examples:

```text
user preferences
previous project decisions
persistent profile facts
learned task history
```

A graph can be stateful without implementing long-term memory.

Stage 03 focuses on **execution state**.

Stage 06 later focuses on memory and persistence policies across sessions.

---

## 5. State is not the same as model context

Another common confusion:

```text
Graph State
    !=
LLM Context Window
```

Graph state may contain:

```text
messages
budget counters
route decisions
approval flags
database IDs
internal workflow metadata
```

Only some of that should be sent to the model.

For example:

```python
state = {
    "messages": [...],
    "retry_count": 2,
    "permission_scope": "read-only",
}
```

The model may need `messages`, but it may not need every internal control field.

A good orchestration layer decides which state becomes model context.

---

## 6. State enables inspectable transitions

With explicit state, a workflow can be understood as:

```text
State_t
   |
   v
Node
   |
   v
Partial update
   |
   v
State_t+1
```

Example:

```text
Before classify:
{
  request: "I was charged twice"
}

classify()

Update:
{
  route: "billing"
}

After classify:
{
  request: "I was charged twice",
  route: "billing"
}
```

The node does not need to reconstruct the whole application state.

It declares what changed.

---

## 7. Why nodes often return partial state

A useful node contract is:

```text
State -> Partial<State>
```

For example:

```python
def classify(state):
    return {"route": "billing"}
```

rather than:

```python
def classify(state):
    return {
        "request": state["request"],
        "route": "billing",
        "answer": state.get("answer"),
        ...
    }
```

Partial updates have several benefits:

- smaller node responsibility;
- clearer diffs between states;
- easier tracing;
- easier composition;
- less accidental overwriting.

LangGraph's `StateGraph` follows this model: nodes read shared state and return updates to that state.

---

## 8. Explicit state does not mean all state is mutable by the model

Suppose the graph state contains:

```text
permission_scope = read-only
remaining_budget = 3
```

A model should not be able to say:

```text
permission_scope = admin
remaining_budget = 100000
```

and thereby change application policy.

This continues a principle from Stage 02:

> **Model output is a proposal, not authority.**

Some state is model-generated data.

Some state is application-owned policy.

Do not treat them as equivalent.

---

## 9. When should you *not* introduce a graph?

If your entire workflow is:

```text
parse -> validate -> save
```

ordinary Python is probably clearer.

If your Agent is only:

```text
model -> optional tool -> model
```

our Stage 01 loop may still be easier to understand.

A graph becomes more valuable when you need several of:

- branches;
- cycles;
- explicit state inspection;
- persistence;
- interruption;
- resumption;
- streaming progress;
- reusable subflows;
- multiple orchestration policies.

Use the graph because the execution model needs it, not because graphs look sophisticated.

---

## 10. The Stage 03 mental model

Keep this picture in mind:

```text
                  Shared State
                       |
                       v
                  +---------+
                  |  Node A |
                  +----+----+
                       |
                partial update
                       |
                       v
                  Shared State
                       |
                  transition
                 /           \
                v             v
            +------+       +------+
            |Node B|       |Node C|
            +------+       +------+
```

The LLM may be inside one of these nodes.

A tool may be inside another.

A deterministic validator may be inside another.

The **graph** is the orchestration structure that coordinates them.

---

## 11. Completion check

Before continuing, you should be able to answer:

1. Where was state stored in the Stage 01 `while` loop?
2. Why is explicit state useful for pause/resume?
3. Why is graph state not identical to LLM context?
4. Why is graph state not identical to long-term memory?
5. Why should a node return only the fields it changes when possible?
6. Which state fields should remain application-owned rather than model-controlled?
7. What complexity threshold would justify replacing ordinary Python with a graph runtime?

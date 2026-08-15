# LangGraph Core Concepts

LangGraph is introduced only after we have implemented the same core ideas ourselves.

That makes its abstractions easier to understand:

```text
TinyStateGraph concept        LangGraph concept
----------------------        -----------------
shared dict state             State schema
node(state) -> updates        Graph node
fixed transition              add_edge
conditional transition        add_conditional_edges
START / END                   START / END
compile                       StateGraph.compile()
invoke                        compiled_graph.invoke()
```

---

## 1. What LangGraph is

LangGraph is a low-level orchestration framework/runtime for long-running,
stateful workflows and Agents.

It focuses on concerns such as:

- shared state;
- graph transitions;
- durable execution;
- streaming;
- human-in-the-loop;
- persistence.

It does not require LangChain, although LangChain model/tool/message components
are commonly used with it.

---

## 2. State schema

A simple state can be a `TypedDict`:

```python
from typing import TypedDict

class State(TypedDict, total=False):
    request: str
    route: str
    answer: str
```

Then:

```python
from langgraph.graph import StateGraph

builder = StateGraph(State)
```

The schema documents what data may move through the graph.

Do not treat it only as type decoration. A good state schema is part of your
orchestration design.

---

## 3. Nodes

A node reads state and returns updates:

```python
def classify(state: State):
    return {"route": "billing"}
```

Conceptually:

```text
State -> Partial<State>
```

This is the same contract our handwritten graph introduced.

A node may internally contain:

- deterministic Python;
- a model call;
- tool execution;
- retrieval;
- validation;
- approval logic.

The graph does not require every node to be an LLM call.

---

## 4. Add nodes

```python
builder.add_node("classify", classify)
builder.add_node("billing", billing)
```

Current LangGraph also supports adding a callable directly and inferring the
node name, but Tiny-Agent examples usually name nodes explicitly when that makes
the topology easier to read.

Node names are operational identifiers. They become useful in:

- traces;
- streaming updates;
- interrupts;
- debugging;
- test assertions.

Choose names that describe work, not implementation trivia.

---

## 5. START and END

```python
from langgraph.graph import START, END

builder.add_edge(START, "classify")
builder.add_edge("billing", END)
```

`START` and `END` make entry and termination explicit.

---

## 6. Fixed edges

A fixed edge says:

```text
when node A finishes -> run node B
```

Example:

```python
builder.add_edge("tools", "model")
```

This is exactly the feedback edge in a ReAct loop.

---

## 7. Conditional edges

A router can choose a route key:

```python
def route_after_model(state):
    if state["final_answer"] is not None:
        return "end"
    return "tools"
```

The graph maps route keys to destinations:

```python
builder.add_conditional_edges(
    "model",
    route_after_model,
    {
        "tools": "tools",
        "end": END,
    },
)
```

Notice the safety boundary:

```text
router output
    ↓
application-owned route mapping
    ↓
actual destination
```

This preserves Stage 02's allowlist principle.

---

## 8. Compile

`StateGraph` is a builder.

You compile it before execution:

```python
graph = builder.compile()
```

The compiled graph supports runtime methods such as:

```text
invoke
ainvoke
stream
astream
```

Compilation is also where persistence/checkpointer configuration can be added.

---

## 9. Invoke

```python
result = graph.invoke(
    {"request": "I was charged twice"}
)
```

The result is the final graph state for a normal completed run.

This differs from Stage 01's `AgentResult`, which exposed a purpose-built return
object. A graph-oriented application often carries more internal state through
execution, so output schemas and public API boundaries become increasingly
important later.

---

## 10. Stream

Instead of waiting for final state:

```python
for update in graph.stream(
    initial_state,
    stream_mode="updates",
):
    print(update)
```

`updates` is useful for observing progress after graph steps.

Streaming does not mean only token streaming. A stateful runtime may stream:

- node/state updates;
- model message chunks;
- custom progress signals;
- checkpoint/task events.

We revisit this in chapter 06.

---

## 11. ReAct expressed as a graph

Stage 01:

```text
while True:
    response = model()
    if tool_calls:
        execute_tools()
        continue
    return final
```

Stage 03:

```text
             +---------+
      START ->|  model  |
             +----+----+
                  |
            conditional
             /         \
            v           v
       +---------+     END
       |  tools  |
       +----+----+
            |
            +----------> model
```

The underlying Agent semantics did not change.

The orchestration representation changed.

---

## 12. `MessagesState`

LangGraph also provides message-oriented state helpers such as `MessagesState`.

They are convenient for chat/tool Agents because message accumulation needs
merge semantics.

Tiny-Agent does not use that helper in the first graph example because we want
the state fields to remain visible:

```text
messages
pending_tool_calls
final_answer
error
model_steps
```

Once you understand those fields, `MessagesState` is easier to evaluate as an
abstraction rather than magic.

---

## 13. Reducers

LangGraph state fields can define reducers for combining multiple updates.

Conceptually:

```text
old_value + new_update -> merged_value
```

This is important for lists/messages or parallel branches.

For a beginner, always ask:

> If two nodes write the same state key, what should merging mean?

Do not choose a reducer only because a tutorial used one.

---

## 14. Graph API vs Functional API

Current LangGraph provides both:

- Graph API: explicit nodes and edges;
- Functional API: function/task-oriented syntax with runtime features.

Tiny-Agent teaches the **Graph API first** because Stage 03's goal is to make
state transitions visible.

The Functional API is useful, but introducing it first would hide the exact
concepts we are trying to learn.

---

## 15. LangGraph does not replace policy

LangGraph can run your workflow.

It does not decide your application's:

- permission model;
- tool allowlist;
- business budgets;
- security policy;
- safe error redaction;
- quality thresholds.

A framework is infrastructure, not governance.

This is why our graph Agent still owns:

```python
max_model_steps
```

inside Tiny-Agent logic.

---

## 16. Version discipline

Agent frameworks evolve quickly.

Tiny-Agent keeps LangGraph/LangChain as optional Stage 03 dependencies rather
than required core dependencies.

At the time this stage is implemented, the project targets stable 1.x APIs:

```text
langgraph >= 1.2, < 2
langchain >= 1.3, < 2
```

When examples are updated in the future, the tutorial should re-check official
documentation rather than relying on old blog posts.

---

## Completion check

You should be able to write from memory:

1. a TypedDict state;
2. two nodes;
3. a START edge;
4. a conditional edge;
5. an END transition;
6. `compile()`;
7. `invoke()` and `stream()`;

More importantly, you should be able to explain why each piece exists.

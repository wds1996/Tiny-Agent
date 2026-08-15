# State Machines for Agents

A graph-based Agent runtime is easier to understand if we first remove the LLM and study ordinary state machines.

The core idea is simple:

```text
current state + current node
            |
            v
         execute
            |
            v
       state update
            |
            v
      choose next node
```

---

## 1. Node

A node is one unit of work.

Examples:

```text
classify request
call model
execute tools
validate output
retrieve documents
request approval
write final answer
```

A useful contract is:

```python
def node(state):
    ...
    return {"field": new_value}
```

Conceptually:

```text
State -> Partial<State>
```

A node should usually do one coherent job.

---

## 2. Edge

An edge says which node runs next.

Fixed transition:

```text
parse -> validate
```

Conditional transition:

```text
classify
   |
   +-- billing   -> billing_workflow
   +-- technical -> technical_workflow
```

The distinction from Stage 02 routing is important:

- a **Router** computes a routing decision;
- a **conditional edge** turns that decision into graph control flow.

The same router can therefore be used inside a graph without becoming the graph itself.

---

## 3. START and END

Most graph runtimes use structural sentinels.

```text
START -> first_node
last_node -> END
```

They are not business logic.

They make the graph topology explicit.

---

## 4. Cycles

Unlike a simple DAG, Agent graphs often contain cycles.

ReAct is naturally cyclic:

```text
model
  |
  | tool call
  v
tools
  |
  v
model
```

The cycle exits when the model produces a final answer:

```text
model -> END
```

This is why graph runtimes are useful for Agents: Agent control flow is often not a one-way pipeline.

---

## 5. A cycle still needs budgets

Putting a loop into a graph does not solve infinite loops.

Bad reasoning:

```text
LangGraph manages the loop,
therefore the loop is safe.
```

Wrong.

Application-owned limits are still required:

```text
max model turns
max tool calls
max retries
max replans
time budget
cost budget
```

Our `build_langgraph_agent()` deliberately keeps `max_model_steps` even though LangGraph also has runtime recursion safeguards.

Business policy should not disappear just because a framework has a generic safety limit.

---

## 6. Handwritten `TinyStateGraph`

Stage 03 introduces:

```text
src/tiny_agent/state_graph.py
```

Its API deliberately resembles the concepts we later use in LangGraph:

```python
builder = TinyStateGraph()

builder.add_node("classify", classify)
builder.add_node("billing", billing)

builder.add_edge(START, "classify")

builder.add_conditional_edges(
    "classify",
    route,
    {
        "billing": "billing",
        "technical": "technical",
    },
)
```

Then:

```python
graph = builder.compile()
result = graph.invoke(initial_state)
```

This is not intended to compete with LangGraph.

It is a teaching instrument.

---

## 7. Why have a builder and a compiled graph?

We separate:

```text
Graph definition
      ↓
validation / compile
      ↓
Executable graph
```

During graph construction we can validate:

- node names;
- unknown edge targets;
- missing START transition;
- duplicate outgoing transitions.

Then the compiled form can focus on execution.

LangGraph uses the same general pattern: `StateGraph` is a builder and `.compile()` creates an executable compiled graph.

---

## 8. State transition example

Initial state:

```python
{
    "request": "I was charged twice"
}
```

`classify` returns:

```python
{
    "route": "billing"
}
```

Merged state:

```python
{
    "request": "I was charged twice",
    "route": "billing",
}
```

Conditional edge reads:

```python
state["route"]
```

and chooses:

```text
billing
```

Billing node returns:

```python
{
    "answer": "..."
}
```

Final state:

```python
{
    "request": "I was charged twice",
    "route": "billing",
    "answer": "...",
}
```

The graph is therefore a sequence of **state transformations plus transitions**.

---

## 9. Reducers and merging

Our handwritten graph uses simple dictionary replacement:

```python
state.update(partial_update)
```

That is enough for a serial beginner example.

But imagine two branches both update:

```text
results
```

One writes:

```python
["A"]
```

and another writes:

```python
["B"]
```

Should the final value be:

```python
["B"]
```

or:

```python
["A", "B"]
```

A real graph runtime needs a merge policy.

LangGraph allows state keys to define reducers that decide how updates are combined.

This matters especially for:

- message histories;
- parallel branches;
- accumulated evidence;
- event lists.

TinyStateGraph deliberately does not implement reducers so the mechanism remains visible.

---

## 10. Parallel execution is a separate concern

A graph drawing may show:

```text
       /-> A -\
START          JOIN
       \-> B -/
```

That expresses dependency structure.

It does not mean every handwritten graph engine automatically executes A and B concurrently.

Just as Stage 01 taught:

```text
multiple tool calls != concurrent Python execution
```

Stage 03 adds:

```text
graph branches != automatically understood application concurrency
```

The runtime defines the actual execution semantics.

---

## 11. Graph topology does not define Agent autonomy

Consider:

```text
START -> parse -> validate -> save -> END
```

This is a graph.

It is not an Agent.

Now consider:

```text
model -> tools -> model
```

where the model dynamically chooses actions.

That is Agentic.

Therefore:

> **Graph is an orchestration representation; Agent is a control/autonomy pattern.**

Do not use the words interchangeably.

---

## 12. What TinyStateGraph intentionally omits

It does not implement:

- persistent checkpoints;
- interrupts;
- streaming;
- reducers;
- parallel supersteps;
- async execution;
- subgraphs;
- time-travel debugging;
- durable retry semantics;
- distributed execution.

Those omissions explain why using a mature runtime becomes reasonable as orchestration grows.

---

## Completion check

You should now be able to explain:

1. Node vs edge.
2. Router vs conditional edge.
3. START/END.
4. Why ReAct creates a graph cycle.
5. Why graph cycles still need application budgets.
6. Builder vs compiled runtime.
7. Why reducers become important for accumulated/parallel state.
8. Why a graph is not automatically an Agent.

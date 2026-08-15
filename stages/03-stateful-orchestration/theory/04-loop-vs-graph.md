# Loop vs Graph: What Actually Changes?

A common mistake is to compare a handwritten Agent loop and LangGraph as if one were "simple" and the other were "intelligent".

That is not the right comparison.

Both can implement the same Agent policy.

The important difference is **how orchestration state and transitions are represented and managed**.

---

## 1. Stage 01 loop

Our Stage 01 runtime is conceptually:

```python
for step in range(max_steps):
    response = model.generate(messages, tool_schemas)

    if response.tool_calls:
        execute_tools()
        append_observations()
        continue

    if response.final_answer is not None:
        return final_answer
```

This is excellent teaching code.

You can read the entire control flow top to bottom.

---

## 2. Equivalent graph

The same logic can be expressed as:

```text
START
  |
  v
model
  |
  +-- final/error --> END
  |
  +-- tool calls --> tools
                       |
                       +----> model
```

The Agent did not suddenly become more autonomous.

The same decisions are being made:

```text
model decides action
runtime executes tool
observation goes back to model
```

Only the orchestration representation changed.

---

## 3. Mapping the two implementations

### Loop variable

```python
messages
```

becomes graph state:

```python
state["messages"]
```

### `continue`

```python
continue
```

becomes an edge:

```text
tools -> model
```

### `if tool_calls`

becomes a conditional edge:

```text
model --route--> tools / END
```

### step counter

remains application state/policy:

```python
state["model_steps"]
```

### final `return`

becomes:

```text
model -> END
```

---

## 4. What graphs make easier

### A. Inspect topology

With a loop, the topology is embedded in code.

With a graph, transitions are declared explicitly.

For a larger workflow this can make it easier to answer:

```text
Which nodes can reach approval?
What happens after retrieval fails?
Where can this loop return to planning?
```

### B. Pause and resume

A process-local loop normally assumes it keeps running.

A graph runtime with checkpointing can save execution state and resume later.

### C. Streaming progress

Graph runtimes can expose per-node/state updates without manually adding print statements everywhere.

### D. Human-in-the-loop

A graph can suspend at an approval point while preserving the state required to continue.

### E. Persistence and replay

State snapshots can support debugging, resumption, and alternative trajectories.

---

## 5. What graphs make harder

Graphs are not free abstraction.

They add concepts:

```text
state schemas
merge/reducer semantics
node boundaries
graph configuration
checkpoint identity
framework versioning
streaming modes
interrupt semantics
```

For a three-step deterministic function, these may be unnecessary complexity.

---

## 6. A graph can hide control flow too

A badly designed graph may be harder to understand than a good loop.

Examples:

- dozens of tiny nodes with no meaningful responsibility;
- state keys mutated for unrelated purposes;
- routing logic spread across model prompts and hidden middleware;
- every function converted into a node only to make the diagram bigger;
- subgraphs introduced before the base flow is understandable.

Tiny-Agent uses this rule:

> **A node should represent a meaningful orchestration boundary, not every function call.**

---

## 7. Graph does not mean multi-Agent

This:

```text
model -> tools -> model
```

can be one Agent.

This:

```text
parse -> validate -> save
```

can be zero Agents.

This:

```text
supervisor -> specialist A / specialist B
```

may be multi-Agent.

The graph structure alone does not determine the number of Agents.

---

## 8. Graph does not mean planning

A graph may encode a fixed workflow:

```text
A -> B -> C
```

A Planner may dynamically create a plan without using a graph framework.

Planning and graph orchestration are separate dimensions.

Stage 02 gave us planning policy.

Stage 03 gives us a stronger execution representation.

They compose:

```text
Planner node
    |
    v
Executor subflow
    |
    v
Validation / replan edge
```

---

## 9. Keep the old implementation

Tiny-Agent intentionally keeps the Stage 01 loop even after adding LangGraph.

Why?

Because the two artifacts answer different learning questions.

### Stage 01

> What is the minimum Agent loop?

### Stage 03

> When and how should that loop become explicit stateful orchestration?

Deleting the old version would destroy the comparison.

---

## 10. Choosing between loop and graph

Prefer a loop/workflow when:

- control flow is compact;
- state fits naturally in local variables;
- pause/resume is unnecessary;
- persistence is unnecessary;
- one developer can trace the whole function easily.

Consider a graph when:

- control flow has several branches/cycles;
- execution must survive interruptions;
- state must be inspected externally;
- you need checkpointing;
- you need human approval;
- you need streaming node-level progress;
- multiple teams/components need stable orchestration boundaries.

---

## 11. The most important architectural question

Do not ask:

> Should I use LangGraph?

Ask:

> What orchestration problem has become difficult in ordinary Python, and which runtime capability would make it simpler or safer?

If you cannot answer that question, adding a graph framework is probably premature.

---

## Completion check

Explain without framework jargon:

1. how `continue` maps to an edge;
2. how an `if` maps to a conditional edge;
3. how local variables map to state;
4. what a graph adds beyond syntax;
5. what complexity a graph introduces;
6. why graph, Agent, planning, and multi-Agent are different concepts.

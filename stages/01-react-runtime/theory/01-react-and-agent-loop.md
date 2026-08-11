# ReAct and the Agent Loop

## 1. From tool calling to Agent behavior

A single tool call is straightforward:

```text
User -> Model -> Tool Call -> Runtime -> Tool Result -> Model -> Answer
```

But many real tasks require multiple rounds of acting and observing:

```text
Question
  |
  v
Model decision
  |
  +-- use tool --> observation --+
  |                               |
  +-------------------------------+
  |
  +-- final answer --> END
```

The important change is not a new model architecture. It is the introduction of a controlled execution loop.

## 2. ReAct in one sentence

ReAct combines **reasoning about what to do next** with **actions that interact with an external environment**, then uses returned observations to continue the task.

A simplified pattern is:

```text
Reason -> Act -> Observe -> Reason -> Act -> Observe -> ...
```

For implementation purposes, the critical loop is:

```text
Decide -> Act -> Observe -> Decide again
```

## 3. Why environment feedback matters

Consider a research task:

```text
Find the latest paper about X and summarize its method.
```

The model may initially decide to search. Search results may reveal:

- ambiguous titles;
- stale results;
- multiple papers with similar names;
- missing metadata.

The next action should depend on the actual search result, not only the original user question.

This is what makes environment interaction qualitatively different from one-shot generation.

## 4. ReAct does not require exposing full chain-of-thought

The historical ReAct presentation is often written as:

```text
Thought
Action
Observation
Thought
Action
Observation
...
```

A production runtime does not need to expose a model's hidden reasoning verbatim in order to implement the useful control pattern.

Tiny-Agent focuses on the auditable parts:

```text
Action
Arguments
Observation
Final Answer
```

This gives the runtime information it actually needs while keeping internal reasoning separate from externally logged execution state.

## 5. Action vs observation

### Action

A model-proposed external operation.

Examples:

```text
search_web(query="ReAct paper")
query_database(sql="...")
calculator(a=12, b=7)
```

### Observation

The result returned by the environment after the runtime executes the action.

Examples:

```text
Search results: ...
Database returned 12 rows
19
ToolError: request timed out
```

The observation should affect the next model decision.

## 6. Why the runtime owns the loop

The model should not be trusted to control execution without limits.

The runtime is responsible for:

- deciding whether the proposed tool exists;
- validating arguments;
- executing or refusing the action;
- recording observations;
- counting steps;
- enforcing budgets;
- deciding when the process must stop;
- applying permissions and approval rules later.

This is the foundation of safe Agent engineering.

## 7. Valid high-level outcomes per step

In the first Tiny-Agent runtime, a model step has two meaningful outcomes:

### A. Propose one or more tool calls

```text
ModelResponse(tool_calls=[...])
```

The runtime executes them, appends observations, and starts another model turn.

### B. Produce a final answer

```text
ModelResponse(final_answer="...")
```

The runtime returns and terminates the task.

If the model returns neither, the model/runtime contract has been violated.

## 8. Stopping conditions are mandatory

Any autonomous loop can fail to terminate.

Example:

```text
search -> search -> search -> search -> ...
```

Therefore a runtime needs explicit stopping rules.

The first rule Tiny-Agent implements is:

```text
max_steps
```

Later stages will add richer controls:

- maximum tool calls;
- retry limits;
- timeout budgets;
- token budgets;
- cost budgets;
- cancellation;
- loop detection.

## 9. Tool failures are part of the environment

Suppose the model proposes invalid arguments:

```text
calculator(a="hello", b=7)
```

A recoverable tool failure can be represented as:

```text
ToolError[TypeError]: ...
```

and returned as the next observation.

The model can then decide to:

- repair the arguments;
- choose another tool;
- ask the user for clarification;
- stop and explain the failure.

This does not mean all errors should be swallowed. Later stages will distinguish recoverable errors from permission failures, system failures, and fatal runtime errors.

## 10. Agent loop vs workflow

An important distinction:

### Deterministic workflow

The developer defines the path:

```text
parse -> retrieve -> rerank -> answer
```

### Agent loop

The model dynamically chooses the next action based on current state and observations.

```text
state -> model decision -> action -> new state -> model decision
```

Production systems often combine both. Tiny-Agent will later use deterministic control flow whenever possible and reserve model decisions for genuinely uncertain steps.

## 11. Key takeaways

- ReAct is fundamentally about interleaving decisions, actions, and observations.
- Environment feedback changes future model decisions.
- The runtime, not the model, owns execution and stopping.
- Visible chain-of-thought is not required to implement a ReAct-style system.
- Explicit stopping conditions are mandatory.
- Tool errors can become useful observations when recovery is possible.
- Agentic control should be used only where dynamic decisions are useful.

## Review questions

1. What is the difference between one-shot function calling and an Agent loop?
2. What exactly is an observation?
3. Why should the runtime own stopping conditions?
4. Why does a ReAct-style system not require printing hidden reasoning?
5. When would a deterministic workflow be preferable to an Agent loop?

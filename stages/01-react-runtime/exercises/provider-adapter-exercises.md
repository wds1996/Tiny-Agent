# Provider Adapter Exercises

These exercises are designed to make the provider/runtime boundary concrete. Do not solve them by moving provider-specific logic into `AgentRuntime`.

## Exercise 1 — Trace the protocol by hand

Given this Tiny-Agent message history:

```python
[
    {"role": "user", "content": "What is 9 * 8?"},
    {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_9x8",
                "name": "multiply",
                "arguments": {"a": 9, "b": 8},
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "call_9x8",
        "name": "multiply",
        "content": "72",
    },
]
```

Write the equivalent Responses API input items by hand.

Then answer:

1. Which field correlates the result with the model request?
2. Why is the tool name not enough for correlation?
3. Why are the arguments encoded as JSON for the provider but stored as a Python dictionary inside Tiny-Agent?

---

## Exercise 2 — Add a `subtract` tool

Extend `code/openai_multi_tool_agent.py` with:

```python
def subtract(a: float, b: float) -> float:
    ...
```

Test a task such as:

```text
Calculate (80 - 17) * 3 + 5.
```

Before running the program, predict a valid tool trajectory.

Then compare your predicted trajectory with the actual one.

Questions:

- Did the model choose the same grouping you expected?
- Did the final answer remain correct even if the trajectory differed?
- Which aspects are deterministic and which are model decisions?

---

## Exercise 3 — Break strict schema intentionally

Remove:

```python
"additionalProperties": False
```

from one tool schema while keeping:

```python
strict_tools=True
```

Observe the provider behavior.

Then restore the strict-compatible schema.

Explain why schema correctness is part of Agent reliability.

---

## Exercise 4 — Invalid JSON from a fake provider

Extend `tests/test_openai_adapter.py` with a provider response whose arguments are:

```text
{a: 1, b: 2}
```

instead of valid JSON:

```json
{"a": 1, "b": 2}
```

Assert that the adapter raises an error before the runtime attempts tool execution.

Explain why this error belongs to the adapter/protocol boundary rather than the tool handler.

---

## Exercise 5 — JSON with the wrong shape

Create a fake provider call with:

```json
[1, 2]
```

as the decoded arguments.

The JSON is syntactically valid, but it is not an object.

Verify that Tiny-Agent rejects it.

This exercise demonstrates the difference between:

```text
valid JSON
```

and:

```text
valid function-call arguments
```

---

## Exercise 6 — Multiple independent tool calls

Create two read-only tools:

```text
get_city_temperature(city)
get_city_population(city)
```

Ask a question that can require both independently.

Inspect whether the model emits multiple calls in one turn.

Then set:

```python
parallel_tool_calls=False
```

on `OpenAIResponsesModel` and compare the trajectory.

Important question:

> Does `parallel_tool_calls=True` mean Tiny-Agent currently executes the Python handlers concurrently?

Answer: no. It allows the model to request multiple tool calls in one turn. The current runtime still loops over those handlers synchronously. Physical parallel execution is a separate runtime concern.

---

## Exercise 7 — Serial dependency

Use the arithmetic tools for:

```text
Calculate (23 * 17) + 41.
```

Explain why the `add` call depends on the observation of `multiply`.

Then contrast it with:

```text
Find the temperatures of Tokyo and Paris.
```

Draw both dependency graphs.

---

## Exercise 8 — Provider substitution thought experiment

Imagine adding:

```python
class QwenModel:
    ...
```

List the files that should need modification.

A good architecture should let you add a provider adapter and tests without modifying the core semantics of:

```text
AgentRuntime
ToolRegistry
Tool handlers
```

If you believe the runtime must change, explain exactly which provider-independent capability is missing.

---

# Interview Questions

You should be able to answer these without reading the source code.

1. What is the difference between an Agent runtime and a model provider adapter?
2. Why does Tiny-Agent normalize provider output into `ModelResponse`?
3. What does `call_id` solve?
4. Why should `generate()` represent one model turn instead of the whole Agent run?
5. What does strict function calling validate?
6. What is the difference between malformed JSON and semantically invalid tool arguments?
7. Why can an Agent have multiple tool calls in a single model turn?
8. Why is multiple tool calling different from concurrent tool execution?
9. Why use a fake OpenAI client in unit tests?
10. What would you test in a live integration test that you would not test in a unit test?
11. Why is a provider-neutral transcript useful?
12. What limitations appear when provider-native reasoning/session state becomes important?

# Completion Challenge

Build a three-tool calculator with:

```text
add
multiply
subtract
```

and demonstrate at least three trajectories:

1. direct one-tool task;
2. serial two-or-more-tool task;
3. a task where the model correctly decides no tool is necessary.

For each run, record:

```text
user input
model action(s)
tool arguments
observation(s)
final answer
step count
```

Do not judge the Agent only by the final answer. Inspect the trajectory as well.

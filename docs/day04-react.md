# Day 4 — ReAct and the Agent Runtime

## 1. What we are learning today

The goal is not to memorize a framework API. It is to understand the control loop underneath an agent.

A minimal agent has five moving parts:

1. **Model** — decides what to do next.
2. **Tool schema** — tells the model what actions exist.
3. **Runtime** — owns the loop and executes actions.
4. **Observation** — feeds environment results back to the model.
5. **Stopping condition** — decides when execution ends.

Conceptually:

```text
User task
   |
   v
 Model
   |
   +---- final answer? ----> END
   |
   v
Tool Call (Action)
   |
   v
 Runtime executes tool
   |
   v
Observation
   |
   +-----------------------> Model
```

This is the practical core of a ReAct-style agent.

## 2. ReAct: the idea that matters

The original ReAct work interleaves reasoning and acting. For an engineering runtime, the important part is the feedback loop:

```text
decide -> act -> observe -> decide again
```

The model does **not** need to expose a verbose chain-of-thought to make this work. Tiny-Agent keeps auditable actions, arguments, observations, and final answers while leaving private reasoning inside the model.

## 3. Why `Model` is an interface

`AgentRuntime` depends on this contract:

```python
class Model(Protocol):
    def generate(self, messages, tools) -> ModelResponse:
        ...
```

It does not depend on OpenAI, Anthropic, Qwen, or another provider.

This is dependency inversion:

```text
AgentRuntime --> Model protocol <-- OpenAI adapter
                              <-- Qwen adapter
                              <-- Fake model for tests
```

Benefits:

- easier tests;
- easier provider switching;
- runtime logic stays stable;
- provider-specific parsing is isolated.

## 4. Why tools are not just Python functions

A tool has two sides:

```text
Model-visible side                 Runtime side
------------------                 ------------
name                               Python callable
description                        validation/execution
JSON schema                         result/error
```

The model never directly executes the Python function. It emits a structured request. The runtime is the authority that decides whether and how to execute it.

That distinction becomes critical later for permissions, HITL, sandboxing, timeout, retry, and MCP.

## 5. Walk through `AgentRuntime.run`

Initial state:

```python
messages = [
    {"role": "system", ...},
    {"role": "user", ...},
]
```

Each iteration asks the model for the next action:

```python
response = model.generate(messages, tool_schemas)
```

There are only two valid high-level outcomes in v0.1:

### Outcome A — tool calls

The runtime records the action, executes it, and appends the observation:

```text
assistant: call calculator(a=12, b=7)
tool: 19
```

Then the loop continues.

### Outcome B — final answer

The runtime returns `AgentResult` and stops.

If the model returns neither, the runtime raises an error because the model/runtime contract has been violated.

## 6. Why `max_steps` matters

An autonomous loop can fail like this:

```text
search -> search -> search -> search -> ...
```

So production agents need budgets and stopping conditions. Today we implement only a step budget:

```python
max_steps=8
```

Later we will add:

- timeout budget;
- token budget;
- cost budget;
- per-tool limits;
- retry limits.

## 7. Why tool exceptions become observations

Suppose the model emits invalid arguments:

```text
calculator(a="hello", b=7)
```

If every tool exception crashes the process, the agent cannot recover. Tiny-Agent instead turns the exception into an observation:

```text
ToolError[TypeError]: ...
```

The model can then decide whether to repair the call, choose another tool, or explain failure.

Important: this is only the first reliability layer. Later we will distinguish retryable errors, user errors, permission errors, and fatal system errors.

## 8. Why the test uses a fake model

`ScriptedModel` deliberately returns:

```text
turn 1 -> calculator tool call
turn 2 -> final answer
```

This lets us test the runtime deterministically without:

- an API key;
- network access;
- model randomness;
- token cost.

A serious agent project needs this separation. Otherwise every unit test becomes an expensive and flaky integration test.

## 9. What you should be able to explain in an interview

After Day 4, answer these without looking at notes:

1. What is the difference between function calling and an agent loop?
2. What component actually executes a tool?
3. Why must a tool result be sent back to the model?
4. What makes ReAct different from one-shot tool calling?
5. Why do agents need stopping conditions?
6. Why should model-provider code be separated from runtime code?
7. Why should tool failures often become observations instead of process crashes?
8. Why is deterministic testing important for agent systems?

## 10. Your exercise

Before Day 5, implement one real model adapter using the function-calling API you already know.

The adapter must satisfy:

```python
Model.generate(messages, tools) -> ModelResponse
```

Do **not** change `AgentRuntime`.

That constraint is intentional: if your provider adapter can be added without modifying the runtime, our abstraction is working.

Then test this task with at least two tools:

```text
Calculate (23 * 17) + 41, and explain the result.
```

Suggested tools:

```text
multiply(a, b)
add(a, b)
```

Expected trajectory:

```text
multiply -> observation -> add -> observation -> final answer
```

Do not hard-code that sequence. Let the model choose it.

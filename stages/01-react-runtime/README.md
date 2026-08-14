# Stage 01 — ReAct & Core Agent Runtime

This stage turns basic tool calling into an explicit Agent runtime and then connects that runtime to a real LLM provider.

The goal is not to memorize a framework API. It is to understand the control loop that most Agent frameworks eventually need to manage:

```text
decide -> act -> observe -> decide again
```

Stage 01 deliberately separates two responsibilities:

```text
AgentRuntime                      Model Provider Adapter
------------                      ----------------------
iteration                         API request format
stopping                          provider tool schema
execution                         provider response parsing
observations                      provider-specific configuration
runtime errors                    output normalization
```

That separation is the foundation for everything that follows in Tiny-Agent.

## Prerequisites

Complete [`../00-foundations/`](../00-foundations/) first, or make sure you already understand:

- message-based LLM APIs;
- structured output;
- function/tool calling;
- JSON Schema tool definitions;
- model-generated tool calls vs real Python execution;
- returning tool observations to the model.

## Learning objectives

After this stage, you should be able to:

1. explain ReAct at an engineering level;
2. distinguish one-shot tool calling from an iterative Agent loop;
3. implement an explicit Agent runtime;
4. explain why the model should not own tool execution;
5. isolate provider-specific APIs behind a model interface;
6. normalize provider outputs into internal Agent types;
7. explain the role of a provider adapter;
8. explain why `call_id` must survive tool execution;
9. maintain a tool registry;
10. feed tool errors back as recoverable observations when appropriate;
11. distinguish serial tool dependencies from multiple independent tool calls;
12. enforce a maximum-step stopping condition;
13. unit-test the runtime and provider adapter without a live LLM;
14. run the same provider-neutral runtime with a real OpenAI model;
15. distinguish Stage 01 architectural principles from deliberate teaching simplifications.

## Recommended order

### Part A — Understand the Agent loop

1. [`theory/01-react-and-agent-loop.md`](theory/01-react-and-agent-loop.md)
2. [`theory/02-runtime-architecture.md`](theory/02-runtime-architecture.md)
3. [`code/minimal_react_runtime.py`](code/minimal_react_runtime.py)

### Part B — Connect the runtime to a real model

4. [`theory/03-model-provider-adapter.md`](theory/03-model-provider-adapter.md)
5. [`../../src/tiny_agent/models/openai.py`](../../src/tiny_agent/models/openai.py)
6. [`../../tests/test_openai_adapter.py`](../../tests/test_openai_adapter.py)
7. [`code/openai_multi_tool_agent.py`](code/openai_multi_tool_agent.py)

### Part C — Understand the boundaries

8. [`theory/04-scope-and-production-limitations.md`](theory/04-scope-and-production-limitations.md)
9. [`../../tests/test_runtime_edges.py`](../../tests/test_runtime_edges.py)
10. [`../../tests/test_openai_adapter_edges.py`](../../tests/test_openai_adapter_edges.py)

### Part D — Review and extend

11. Read the integrated implementation under [`../../src/tiny_agent/`](../../src/tiny_agent/)
12. [`exercises/review-questions.md`](exercises/review-questions.md)
13. [`exercises/provider-adapter-exercises.md`](exercises/provider-adapter-exercises.md)

## Stage architecture

```text
                         +----------------------+
                         |       User Task      |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |     AgentRuntime     |
                         +----------+-----------+
                                    |
                           provider-neutral
                              Model protocol
                                    |
                                    v
                         +----------------------+
                         | Provider Adapter     |
                         | OpenAIResponsesModel |
                         +----------+-----------+
                                    |
                             Responses API
                                    |
                                    v
                         +----------------------+
                         |   Model Decision     |
                         +----------+-----------+
                                    |
                    +---------------+---------------+
                    |                               |
              final answer                    function call(s)
                    |                               |
                    v                               v
                   END                      +---------------+
                                            | ToolRegistry  |
                                            +-------+-------+
                                                    |
                                                    v
                                             Python Handler
                                                    |
                                                    v
                                               Observation
                                                    |
                                                    +-------> next model turn
```

## Why this is a separate stage

Stage 00 demonstrates that tool calling can repeat. Stage 01 introduces explicit runtime responsibilities:

- iteration;
- stopping;
- normalized responses;
- execution ownership;
- provider adapters;
- request/response protocol translation;
- tool-call correlation IDs;
- error observations;
- deterministic testing.

Those responsibilities are the first real boundary between a simple function-calling demo and an Agent runtime.

## Implementation layers

### Educational snapshot

[`code/minimal_react_runtime.py`](code/minimal_react_runtime.py) is deliberately compact and self-contained. It is meant to be read top to bottom.

### Real provider example

[`code/openai_multi_tool_agent.py`](code/openai_multi_tool_agent.py) runs the same architecture with a real OpenAI Responses API model and two arithmetic tools.

The example task is:

```text
Calculate (23 * 17) + 41 and explain the result.
```

A typical trajectory is:

```text
multiply(23, 17)
      |
      v
     391
      |
      v
add(391, 41)
      |
      v
     432
      |
      v
final answer
```

The sequence is not hard-coded by the runtime. The model decides when each tool is needed.

### Latest library implementation

The reusable implementation is split across:

- [`../../src/tiny_agent/types.py`](../../src/tiny_agent/types.py)
- [`../../src/tiny_agent/tool.py`](../../src/tiny_agent/tool.py)
- [`../../src/tiny_agent/runtime.py`](../../src/tiny_agent/runtime.py)
- [`../../src/tiny_agent/models/openai.py`](../../src/tiny_agent/models/openai.py)
- [`../../tests/test_runtime.py`](../../tests/test_runtime.py)
- [`../../tests/test_runtime_edges.py`](../../tests/test_runtime_edges.py)
- [`../../tests/test_openai_adapter.py`](../../tests/test_openai_adapter.py)
- [`../../tests/test_openai_adapter_edges.py`](../../tests/test_openai_adapter_edges.py)

The stage snapshot and `src/` serve different purposes: the stage code teaches the smallest version of a concept, while `src/` continues evolving with later stages.

## Running the real provider example

Install the project and OpenAI optional dependency:

```bash
pip install -e ".[openai]"
```

Set your API key:

```bash
export OPENAI_API_KEY="your-key"
```

Run:

```bash
python stages/01-react-runtime/code/openai_multi_tool_agent.py
```

The teaching example defaults to `gpt-5.6-luna` with reasoning effort `none` so the stage can focus on a transparent, stateless provider-adapter boundary. Later stages introduce native conversation state and persisted reasoning deliberately.

## Important: this is not yet a production runtime

Before moving on, read [`theory/04-scope-and-production-limitations.md`](theory/04-scope-and-production-limitations.md).

In particular, Stage 01 does **not** yet provide local JSON-Schema validation, safe error redaction, real concurrent tool execution, retries, timeouts, permissions, checkpoints, tracing, or evaluation. These omissions are deliberate and are addressed in later stages rather than hidden from learners.

## Completion checkpoint

Before moving on, you should be able to explain both of these sentences precisely:

> The model proposes the next action; the runtime owns execution, observations, state transitions, and stopping.

> A provider adapter translates between Tiny-Agent's internal protocol and a model provider's wire protocol without taking ownership of the Agent loop.

You should also be able to trace this complete path without looking at the code:

```text
Tool schema
  -> provider function definition
  -> model function_call
  -> Tiny-Agent ToolCall
  -> Python tool execution
  -> Tiny-Agent observation
  -> provider function_call_output
  -> next model decision
```

Finally, you should be able to explain why the same early implementation can be *conceptually correct* while still being *intentionally incomplete for production*.

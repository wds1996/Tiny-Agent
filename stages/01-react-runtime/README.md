# Stage 01 — ReAct & Core Agent Runtime

This stage turns basic tool calling into an explicit Agent runtime.

The goal is not to learn a framework API. It is to understand the control loop that most Agent frameworks eventually need to manage: **decide -> act -> observe -> decide again**.

## Prerequisites

Complete [`../00-foundations/`](../00-foundations/) first, or make sure you already understand:

- message-based LLM APIs;
- structured output;
- function/tool calling;
- tool schemas;
- returning tool observations to the model.

## Learning objectives

After this stage, you should be able to:

1. explain ReAct at an engineering level;
2. distinguish one-shot tool calling from an iterative Agent loop;
3. implement an explicit Agent runtime;
4. explain why the model should not own tool execution;
5. isolate provider-specific APIs behind a model interface;
6. normalize provider outputs into internal Agent types;
7. maintain a tool registry;
8. feed tool errors back as recoverable observations when appropriate;
9. enforce a maximum-step stopping condition;
10. unit-test the runtime deterministically without a real LLM.

## Recommended order

1. [`theory/01-react-and-agent-loop.md`](theory/01-react-and-agent-loop.md)
2. [`theory/02-runtime-architecture.md`](theory/02-runtime-architecture.md)
3. [`code/minimal_react_runtime.py`](code/minimal_react_runtime.py)
4. Read the integrated implementation under [`../../src/tiny_agent/`](../../src/tiny_agent/)
5. [`exercises/review-questions.md`](exercises/review-questions.md)

## Stage architecture

```text
User Task
   |
   v
AgentRuntime
   |
   v
Model.generate(messages, tools)
   |
   +---- final answer ----------------------> END
   |
   +---- tool call(s)
            |
            v
       ToolRegistry
            |
            v
       Tool Handler
            |
            v
       Observation / Error
            |
            +-------------------------------> next model turn
```

## Why this is a separate stage

Stage 00 demonstrates that tool calling can repeat. Stage 01 introduces explicit runtime responsibilities:

- iteration;
- stopping;
- normalized responses;
- execution ownership;
- error observations;
- deterministic testing.

Those responsibilities are the first real boundary between a simple function-calling demo and an Agent runtime.

## Implementation layers

### Educational snapshot

[`code/minimal_react_runtime.py`](code/minimal_react_runtime.py) is deliberately compact and self-contained. It is meant to be read top to bottom.

### Latest library implementation

The reusable implementation is split across:

- [`../../src/tiny_agent/types.py`](../../src/tiny_agent/types.py)
- [`../../src/tiny_agent/tool.py`](../../src/tiny_agent/tool.py)
- [`../../src/tiny_agent/runtime.py`](../../src/tiny_agent/runtime.py)
- [`../../tests/test_runtime.py`](../../tests/test_runtime.py)

The two versions serve different purposes: the stage snapshot teaches the concept; `src/` continues evolving with later stages.

## Completion checkpoint

Before moving on, you should be able to explain this sentence precisely:

> The model proposes the next action; the runtime owns execution, observations, state transitions, and stopping.

You should also be able to add a real model-provider adapter without modifying `AgentRuntime`.

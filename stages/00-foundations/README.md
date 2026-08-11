# Stage 00 — LLM & Tool-Use Foundations

This stage establishes the minimum concepts required before building an Agent runtime.

It is intentionally framework-free. The goal is to understand what the model does, what the application runtime does, and how a normal LLM API call becomes a tool-using loop.

## Learning objectives

After completing this stage, you should be able to:

1. explain the roles of system, user, assistant, and tool messages;
2. distinguish natural-language output from structured output;
3. explain why JSON schema is useful for machine-readable model output;
4. explain what function/tool calling actually means;
5. distinguish a tool schema from the executable Python function behind it;
6. explain why the LLM does not directly execute local functions;
7. return a tool result to the model as a new observation;
8. implement a minimal multi-turn tool loop;
9. identify why this loop is close to, but not yet a complete production Agent runtime.

## Recommended order

1. [`theory/01-llm-api-and-messages.md`](theory/01-llm-api-and-messages.md)
2. [`theory/02-structured-output.md`](theory/02-structured-output.md)
3. [`theory/03-function-calling.md`](theory/03-function-calling.md)
4. [`code/minimal_tool_loop.py`](code/minimal_tool_loop.py)
5. [`exercises/review-questions.md`](exercises/review-questions.md)

## Mental model

A normal LLM application is roughly:

```text
User -> Application -> Model -> Text -> Application -> User
```

A tool-using application adds an execution boundary:

```text
User
  |
  v
Model ---- proposes tool call ----> Application Runtime
  ^                                  |
  |                                  v
  +--------- tool observation <--- Python / API / DB
```

The most important principle in this stage is:

> The model proposes an action. The runtime decides whether and how to execute it.

That separation becomes the foundation for Agent security, human approval, sandboxing, MCP, tracing, and evaluation later in the project.

## What this stage does not cover yet

We intentionally postpone:

- ReAct;
- planning;
- state graphs;
- RAG;
- MCP;
- long-term memory;
- retries and permissions;
- evaluation;
- deployment.

Those features are easier to understand once the tool-use boundary is clear.

## Completion checkpoint

Before moving to Stage 01, make sure you can answer:

- What exactly does the LLM output when it "calls" a function?
- Who really executes the Python function?
- Why must the tool result be sent back to the model?
- What is the difference between structured output and function calling?
- Why is a single tool call not enough to define a production Agent?

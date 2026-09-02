# Stage 00 — LLM, Context & Tool-Use Foundations

Stage 00 establishes the model/runtime boundary before any Agent framework appears.

A modern Agent is not “an LLM plus a loop.” It is an application that repeatedly constructs model context, asks a probabilistic model for a proposal, validates structured outputs, executes governed capabilities, records observations, and decides what state survives.

## Learning path

```text
LLM API + message roles
        ↓
Structured Output / JSON Schema
        ↓
Function / Tool Calling
        ↓
model capabilities + reasoning effort
        ↓
context windows / tokens / cost / latency
        ↓
instruction hierarchy + context construction
        ↓
minimal multi-turn Tool loop
```

## Learning objectives

After Stage 00 you should be able to:

1. explain system/user/assistant/tool messages;
2. distinguish natural-language output from schema-constrained output;
3. explain why “please output JSON” is weaker than validated Structured Output;
4. explain that a model proposes ToolCalls but the runtime executes them;
5. distinguish Tool schema from executable handler;
6. return Tool observations to the model;
7. explain model capability vs application/runtime capability;
8. reason about model selection, reasoning effort, quality, latency, and cost;
9. distinguish context-window capacity from useful context;
10. reserve context for output and future runtime/tool continuation;
11. distinguish instructions, task data, examples, evidence, memory, and tool schemas;
12. implement a minimal bounded multi-turn Tool loop;
13. identify what is still missing from a production Agent runtime.

## Recommended order

1. `theory/01-llm-api-and-messages.md`
2. `theory/02-structured-output.md`
3. `theory/03-function-calling.md`
4. `theory/04-model-capabilities-and-reasoning.md`
5. `theory/05-context-tokens-cost-latency.md`
6. `code/context_budget_basics.py`
7. `theory/06-instructions-prompts-and-context-construction.md`
8. `code/minimal_tool_loop.py`
9. `exercises/review-questions.md`

## Mental model

```text
Application owns
----------------
instructions
context selection
available Tools
validation
authorization
execution
state/persistence
budgets
observability

Model owns
----------
probabilistic inference over the supplied context
proposal of text / structured data / ToolCalls
```

The recurring rule for the entire repository starts here:

> **The model proposes; application code validates, authorizes, executes, persists, and stops.**

## Context is already an engineering concern

Even frontier models with very large context windows do not make every token useful. Stage 00 introduces the capacity/cost mechanics; Stage 06A later turns context selection, compaction, progressive disclosure, provenance, and isolation into a full engineering discipline.

## Current model note

Tiny-Agent examples may use current GPT-5.6 family model IDs where a live OpenAI call is useful. Model names, prices, and context sizes are versioned provider details; the architecture should not depend on one model name.

Current OpenAI model catalog: https://platform.openai.com/docs/models

## Completion checkpoint

Before Stage 01, explain this complete path without notes:

```text
instructions + task + selected context + Tool schemas
        ↓
model inference
        ↓
ToolCall proposal
        ↓
local validation / policy
        ↓
real Python/API execution
        ↓
Tool observation
        ↓
next selected model context
        ↓
next proposal or final answer
```

# Stage 06A — Context Engineering

Modern Agent quality is often constrained less by raw context-window size than by **what the application chooses to place inside that window**.

This extension stage turns ideas that previously appeared across Stage 00, RAG, memory, tool use, and multi-Agent context projection into one explicit engineering discipline.

> Context engineering is the design of the smallest high-signal context that gives the model the information, instructions, capabilities, and state it needs for the current decision.

## Why this belongs after Memory

By Stage 06 you already own several possible context sources:

```text
system instructions
current task
conversation history
thread checkpoint
long-term memory
retrieved evidence
tool schemas
tool observations
MCP resources
skills
workspace files
progress notes
```

The mistake is to concatenate all of them.

```text
available data != model context
```

Persistence decides what the application retains. Context engineering decides what the model sees **now**.

## Learning objectives

After this stage you should be able to:

1. explain context as a finite attention/token budget;
2. distinguish retained application state from selected model context;
3. reserve room for model output and runtime/tool continuation;
4. classify context by role, provenance, trust, priority, and lifetime;
5. select required and optional context deterministically;
6. explain why a huge context window does not eliminate context engineering;
7. compact old history while preserving provenance;
8. treat summaries as lossy derived state rather than original truth;
9. load evidence, tools, skills, and workspace files just in time;
10. avoid exposing every available tool on every model turn;
11. isolate sub-Agent context instead of copying full parent state;
12. evaluate context policies for quality, cost, latency, and injection surface.

## Learning order

1. `theory/01-context-is-an-attention-budget.md`
2. `theory/02-context-assembly-selection-compaction.md`
3. `code/context_budget_demo.py`
4. `code/compaction_demo.py`
5. `theory/03-just-in-time-context-and-capabilities.md`
6. `theory/04-provenance-trust-and-isolation.md`
7. `src/tiny_agent/context_engineering.py`
8. `tests/test_context_engineering.py`
9. `exercises/review-questions.md`

## Reusable implementation

`ContextBuilder` takes explicit `ContextItem` objects and a `ContextBudget`:

```python
snapshot = ContextBuilder(
    ContextBudget(
        max_context_tokens=32_000,
        reserve_output_tokens=4_000,
        reserve_runtime_tokens=2_000,
    )
).build(items)
```

Required items fail closed if they cannot fit. Optional items compete by priority, then selected items return to their original ordering.

The implementation deliberately uses a rough provider-neutral token estimate for planning. Exact accounting should come from the model tokenizer/provider usage metadata.

## The context pipeline

```text
application-owned data
      |
      v
context candidates
(kind / provenance / trust / priority)
      |
      v
budget + policy
      |
      +--> required instructions/task
      +--> relevant evidence/memory
      +--> activated skill
      +--> selected tools
      +--> recent/compacted history
      |
      v
model context for this decision
```

## Current references

- Anthropic, *Effective context engineering for AI agents* — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- LangGraph memory/context documentation — https://docs.langchain.com/oss/python/langgraph/add-memory
- OpenAI model catalog — https://platform.openai.com/docs/models

The 2026 frontier models may expose very large context windows. That changes capacity; it does not make stale, conflicting, low-signal, or malicious tokens useful.

## Milestone

You are done when you can answer:

> If the application owns 2 GB of state, 400 tools, 80 skills, 300 conversation turns, and 40 retrieved documents, which exact subset should the next model call receive, why, and under which budget/trust policy?

# Stage 02 — Planning, Routing & Deterministic Workflows

## Why this stage exists

A common Agent mistake is to let the LLM decide every step. Real systems are usually more reliable when deterministic control flow handles predictable work and the model is used only for uncertain decisions.

This stage introduces the major orchestration patterns between a simple ReAct loop and a stateful Agent graph.

## Planned topics

- task decomposition;
- ReAct vs Plan-and-Execute;
- planner/executor separation;
- intent/tool routing;
- deterministic workflow design;
- conditional branches;
- plan validation;
- replanning after failed observations;
- step and plan budgets;
- when *not* to use an Agent.

## Planned code artifacts

```text
code/
├── router.py
├── planner_executor.py
├── deterministic_workflow.py
└── research_workflow.py
```

## Planned theory

```text
theory/
├── 01-agent-vs-workflow.md
├── 02-routing-patterns.md
├── 03-planning-and-replanning.md
└── 04-planner-executor.md
```

## Milestone

Build a research workflow that can classify a task, create a bounded plan, execute steps, inspect observations, and re-plan only when necessary.

## Key question

> Which decisions genuinely benefit from an LLM, and which should remain deterministic software?

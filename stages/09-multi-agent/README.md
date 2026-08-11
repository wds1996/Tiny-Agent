# Stage 09 — Multi-Agent Systems & Interoperability

## Why this stage exists

Multi-Agent designs are powerful but easy to overuse. This stage comes late on purpose: learners should first understand single-Agent runtimes, deterministic workflows, state, tools, memory, reliability, and evaluation.

The goal is to learn when multiple Agents are genuinely useful and how to evaluate the coordination overhead they introduce.

## Planned topics

- when one Agent is enough;
- specialist Agents;
- supervisor/worker patterns;
- handoffs;
- shared vs isolated context;
- role boundaries;
- coordination and deadlock failure modes;
- communication cost;
- Agent-to-Agent interoperability concepts;
- A2A overview;
- comparing multi-Agent solutions with simpler workflows.

## Planned code artifacts

```text
code/
├── handoff_demo.py
├── supervisor_workers.py
├── specialist_team.py
└── multi_agent_eval.py
```

## Planned theory

```text
theory/
├── 01-when-to-use-multiple-agents.md
├── 02-handoffs-and-supervision.md
├── 03-context-and-coordination.md
└── 04-agent-interoperability.md
```

## Milestone

Build a small specialist team and measure whether it actually improves task quality enough to justify extra latency, cost, and coordination complexity.

## Key question

> Is this task truly multi-Agent, or are we using multiple LLM roles where a deterministic pipeline or one well-designed Agent would be simpler?

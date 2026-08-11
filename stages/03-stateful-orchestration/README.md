# Stage 03 — Stateful Orchestration

## Why this stage exists

The handwritten runtime is ideal for learning, but larger Agents need explicit state, branching, interruption, persistence, and resumability. This stage introduces graph/state-based orchestration and compares it directly with the earlier loop.

## Planned topics

- state machines for Agents;
- explicit task state;
- nodes, edges, and conditional transitions;
- graph execution semantics;
- LangGraph fundamentals;
- durable execution concepts;
- streaming state updates;
- persistence-ready design;
- translating the Stage 01 runtime into a graph;
- framework benefits vs framework complexity.

## Planned code artifacts

```text
code/
├── handwritten_state_machine.py
├── langgraph_tool_agent.py
├── conditional_routing_graph.py
└── state_inspection_demo.py
```

## Planned theory

```text
theory/
├── 01-why-explicit-state.md
├── 02-state-machines-for-agents.md
├── 03-langgraph-core-concepts.md
└── 04-loop-vs-graph.md
```

## Milestone

Rebuild the tool-using Agent as an explicit state graph and be able to explain exactly what the orchestration framework adds over the handwritten loop.

## Key question

> When does an implicit Python loop become too difficult to inspect, pause, resume, or extend safely?

# Stage 03 — Stateful Orchestration

## Why this stage exists

The handwritten runtime is ideal for learning, but larger Agents need explicit state, branching, interruption, persistence, and resumability. This stage introduces graph/state-based orchestration and compares it directly with the earlier loop.

This is also the first stage where Tiny-Agent deliberately introduces a major Agent framework. The teaching order is important:

```text
handwritten state machine
        ->
understand explicit state / transitions
        ->
LangGraph implementation
        ->
compare what the framework adds
```

The goal is not to memorize LangGraph APIs. The goal is to understand why a graph runtime becomes useful once a plain Python loop becomes difficult to inspect, pause, resume, branch, or persist.

## Frameworks taught in this stage

### LangGraph — primary framework

LangGraph is the main orchestration framework for this stage. Learners will cover:

- `StateGraph`;
- graph state schemas;
- nodes;
- normal and conditional edges;
- `START` / `END`;
- tool-execution nodes;
- routing in a graph;
- streaming state updates;
- checkpoint/persistence concepts;
- interrupts and resumable execution concepts;
- translating the Stage 01 ReAct loop and Stage 02 workflow into graph form.

### LangChain — supporting abstractions, not the main runtime

Tiny-Agent will **not** begin by teaching old-style LangChain chain abstractions as the foundation of Agent engineering. Instead, LangChain will be introduced only where its reusable components are genuinely useful, for example:

- messages and model abstractions;
- tool wrappers;
- prompt templates when they reduce boilerplate;
- document/retriever integrations used later by RAG;
- interoperability with LangGraph.

A dedicated comparison will explain:

```text
LangChain    -> reusable LLM/application components
LangGraph    -> stateful orchestration/runtime
Tiny-Agent   -> handwritten reference implementation used to understand both
```

Learners should finish this stage knowing what each library is for rather than treating `LangChain` and `LangGraph` as interchangeable names.

## Planned topics

- state machines for Agents;
- explicit task state;
- nodes, edges, and conditional transitions;
- graph execution semantics;
- LangGraph fundamentals;
- selected LangChain core abstractions;
- LangChain vs LangGraph responsibilities;
- durable execution concepts;
- streaming state updates;
- persistence-ready design;
- translating the Stage 01 runtime into a graph;
- translating Stage 02 routing/planning into graph nodes;
- framework benefits vs framework complexity.

## Planned code artifacts

```text
code/
├── handwritten_state_machine.py
├── langgraph_tool_agent.py
├── conditional_routing_graph.py
├── planner_executor_graph.py
├── langchain_component_examples.py
└── state_inspection_demo.py
```

## Planned theory

```text
theory/
├── 01-why-explicit-state.md
├── 02-state-machines-for-agents.md
├── 03-langgraph-core-concepts.md
├── 04-loop-vs-graph.md
├── 05-langchain-vs-langgraph.md
└── 06-persistence-streaming-and-interrupts.md
```

## Learning progression

A learner should be able to trace the following evolution:

```text
Stage 01
while-loop ReAct runtime
        |
        v
Stage 02
explicit workflow / router / planner-executor
        |
        v
Stage 03
explicit state graph
        |
        v
LangGraph runtime
```

This makes the framework an answer to an already-understood engineering problem instead of a black box introduced first.

## Milestone

Rebuild the tool-using Agent and Stage 02 workflow as explicit state graphs and be able to explain exactly what LangGraph adds over the handwritten loop/workflow. Also be able to explain when LangChain components are useful and when they are unnecessary.

## Key question

> When does an implicit Python loop become too difficult to inspect, pause, resume, or extend safely — and which parts should be delegated to LangGraph rather than hidden behind generic framework abstractions?

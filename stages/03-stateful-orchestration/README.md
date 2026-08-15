# Stage 03 — Stateful Orchestration: From State Machines to LangGraph

Stage 03 moves Tiny-Agent from process-local loops and workflows to **explicit stateful orchestration**.

The teaching order is deliberate:

```text
implicit state in Python variables
        ->
explicit shared state
        ->
handwritten TinyStateGraph
        ->
LangGraph StateGraph
        ->
rebuild ReAct as a graph
        ->
streaming / checkpoint / interrupt
```

The goal is not to memorize LangGraph APIs. The goal is to understand which orchestration problems make a graph runtime valuable.

---

## Prerequisites

Complete Stage 00–02, or already understand:

- messages, Structured Output, and Function Calling;
- ReAct / model → tool → observation loops;
- Tool Registry and provider adapters;
- deterministic workflow vs Agent;
- routers and conditional dispatch;
- Planner–Executor and bounded replanning.

---

## Learning objectives

After this stage, you should be able to:

1. distinguish implicit execution state from explicit graph state;
2. distinguish graph state, LLM context, checkpoint state, and long-term memory;
3. explain `State -> Partial<State>`;
4. implement nodes, fixed edges, conditional edges, START/END, and cycles;
5. explain reducers and why merge semantics matter;
6. implement a minimal state graph without a framework;
7. use LangGraph `StateGraph`, `add_node`, `add_edge`, `add_conditional_edges`, `compile`, `invoke`, and `stream`;
8. rebuild the Stage 01 ReAct loop as a LangGraph graph;
9. express Stage 02 routing/planning recovery as graph transitions;
10. explain LangChain vs LangGraph responsibilities;
11. use LangChain message/tool abstractions without confusing them with the Agent runtime itself;
12. explain checkpointing and `thread_id`;
13. use `InMemorySaver` for local learning/testing;
14. pause execution with `interrupt()` and resume with `Command(resume=...)`;
15. explain why interrupted nodes restart and why idempotency matters;
16. choose between ordinary Python control flow and a graph runtime based on actual orchestration needs.

---

# Recommended learning order

## Part A — Why explicit state?

1. [`theory/01-why-explicit-state.md`](theory/01-why-explicit-state.md)
2. [`theory/02-state-machines-for-agents.md`](theory/02-state-machines-for-agents.md)
3. [`code/handwritten_state_graph.py`](code/handwritten_state_graph.py)
4. [`../../src/tiny_agent/state_graph.py`](../../src/tiny_agent/state_graph.py)
5. [`../../tests/test_state_graph.py`](../../tests/test_state_graph.py)

At this point you should understand the mechanism without LangGraph.

## Part B — LangGraph fundamentals

6. [`theory/03-langgraph-core-concepts.md`](theory/03-langgraph-core-concepts.md)
7. [`code/langgraph_state_graph.py`](code/langgraph_state_graph.py)
8. [`theory/04-loop-vs-graph.md`](theory/04-loop-vs-graph.md)
9. [`code/langgraph_react_agent.py`](code/langgraph_react_agent.py)
10. [`../../src/tiny_agent/langgraph_runtime.py`](../../src/tiny_agent/langgraph_runtime.py)
11. [`code/planner_executor_graph.py`](code/planner_executor_graph.py)

## Part C — LangChain's role

12. [`theory/05-langchain-vs-langgraph.md`](theory/05-langchain-vs-langgraph.md)
13. [`code/langchain_component_examples.py`](code/langchain_component_examples.py)

## Part D — Stateful runtime features

14. [`theory/06-persistence-streaming-and-interrupts.md`](theory/06-persistence-streaming-and-interrupts.md)
15. [`code/checkpoint_interrupt_demo.py`](code/checkpoint_interrupt_demo.py)
16. [`../../tests/test_stage03_frameworks.py`](../../tests/test_stage03_frameworks.py)

## Part E — Review

17. [`exercises/review-questions.md`](exercises/review-questions.md)

---

# Frameworks introduced

## LangGraph — primary Stage 03 framework

Tiny-Agent uses LangGraph as the first major orchestration framework because its abstractions map directly onto mechanisms already implemented by hand:

```text
Tiny-Agent / Python             LangGraph
-------------------             ---------
state dict                      state schema
function                        node
if / router                     conditional edge
continue / next step            edge
while-loop feedback             graph cycle
manual execution                compiled graph runtime
print progress                  streaming updates
process-local state             checkpointer-backed state
manual pause design             interrupt / resume
```

The project currently targets stable LangGraph 1.x APIs through:

```text
langgraph >= 1.2, < 2
```

Framework APIs should always be verified against current official documentation when this stage is updated.

## LangChain — supporting component layer

LangChain is introduced here for selected reusable abstractions:

- messages;
- tool wrappers;
- model interface concepts;
- later document/retriever integrations.

Tiny-Agent does **not** replace the learning path with a high-level `create_agent()` call.

Use this mental model:

```text
LangChain
    -> reusable LLM/application components and high-level Agent APIs

LangGraph
    -> low-level stateful orchestration/runtime

Tiny-Agent
    -> transparent handwritten reference for learning the mechanisms
```

The project currently targets stable LangChain 1.x APIs through:

```text
langchain >= 1.3, < 2
```

---

# Stage architecture

The LangGraph ReAct example rebuilds Stage 01 as:

```text
                 +-------------+
START ---------->|    model    |
                 +------+------+ 
                        |
                 conditional
                  /             \
                 v               v
           +-----------+         END
           |   tools   |
           +-----+-----+
                 |
                 +-------------> model
```

Shared state contains:

```text
messages
pending_tool_calls
final_answer
error
model_steps
```

The model still proposes actions.

The tool node still owns execution.

The graph runtime owns the stateful transition structure.

---

# Runnable examples

## 1. Handwritten graph — no Stage 03 dependency required

```bash
python stages/03-stateful-orchestration/code/handwritten_state_graph.py
```

## 2. Install Stage 03 dependencies

```bash
pip install -e ".[stage03]"
```

For tests as well:

```bash
pip install -e ".[dev,stage03]"
```

## 3. LangGraph version of the same workflow

```bash
python stages/03-stateful-orchestration/code/langgraph_state_graph.py
```

## 4. ReAct Agent as a graph

```bash
python stages/03-stateful-orchestration/code/langgraph_react_agent.py
```

## 5. Planner–Executor recovery as a graph

```bash
python stages/03-stateful-orchestration/code/planner_executor_graph.py
```

## 6. LangChain component comparison

```bash
python stages/03-stateful-orchestration/code/langchain_component_examples.py
```

## 7. Checkpoint + interrupt/resume

```bash
python stages/03-stateful-orchestration/code/checkpoint_interrupt_demo.py
```

---

# What this stage deliberately does not claim

Stage 03 introduces stateful runtime mechanisms, but it is not yet the full production story.

Still deferred:

- production Postgres checkpoint infrastructure;
- long-term memory policy;
- full user/session identity model;
- production async/concurrency strategy;
- tool permission framework;
- robust retry/timeout/cancellation policies;
- distributed graph execution;
- production LangSmith tracing/evaluation setup;
- persistent HITL user interfaces.

Those belong to later stages.

Also remember:

> A graph does not make a system an Agent.

A deterministic workflow can be a graph. Agent autonomy still comes from model-directed decisions.

---

# Tests

Core graph mechanism:

- [`../../tests/test_state_graph.py`](../../tests/test_state_graph.py)

LangGraph ReAct parity:

- [`../../tests/test_langgraph_runtime.py`](../../tests/test_langgraph_runtime.py)

LangGraph persistence/interrupt and LangChain component compatibility:

- [`../../tests/test_stage03_frameworks.py`](../../tests/test_stage03_frameworks.py)

CI keeps Stage 03 framework tests separate from the lightweight core suite so earlier stages do not require framework dependencies.

---

# Key interview statements

You should be able to explain these precisely:

> **State is the data required to continue execution; model context is only the subset sent to an LLM; long-term memory is a separate retention policy.**

> **A node performs one orchestration unit of work and returns state updates; an edge decides what runs next.**

> **Graph is an orchestration representation; Agent is an autonomy/control pattern.**

> **LangChain primarily provides LLM application abstractions and high-level Agent components; LangGraph is the low-level stateful orchestration runtime.**

> **Checkpointing enables resume; interrupts use persisted state and resume values, but interrupted nodes can restart, so side effects require idempotent design.**

---

# Milestone

Stage 03 is complete when you can:

1. implement and test a small state graph yourself;
2. reproduce it in LangGraph;
3. translate a ReAct `while` loop into explicit graph state and edges;
4. translate routing/replanning into conditional transitions;
5. explain LangChain vs LangGraph without treating them as synonyms;
6. demonstrate streaming updates;
7. pause and resume a graph with a checkpointed interrupt;
8. justify when a graph is worth the added complexity.

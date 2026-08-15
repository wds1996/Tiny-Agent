# Stage 03 Review Questions and Exercises

Use these questions after reading the theory and running the examples. Try to answer from first principles before looking back at the notes.

---

# Part A — Core concepts

1. Where was execution state stored in the Stage 01 `while` loop?
2. What changes when that state becomes a `TypedDict` shared by graph nodes?
3. Why is graph state not the same thing as LLM context?
4. Why is graph state not the same thing as long-term memory?
5. What does `State -> Partial<State>` mean?
6. Why is returning a partial update usually cleaner than returning the complete state?
7. What is a graph node?
8. What is a fixed edge?
9. What is a conditional edge?
10. How is a Stage 02 Router different from a conditional edge?
11. Why are `START` and `END` useful?
12. Why does ReAct naturally create a cycle?
13. Why can a graph still enter an infinite loop?
14. Why should application budgets remain explicit even when a framework has generic recursion limits?
15. Why is a graph not automatically an Agent?
16. Why is a graph not automatically multi-Agent?
17. Why is explicit planning different from graph orchestration?

---

# Part B — TinyStateGraph

18. What does `TinyStateGraph.compile()` validate?
19. Why separate graph construction from graph execution?
20. What happens if a conditional router returns a route not present in its destination map?
21. Why is that destination map a useful safety boundary?
22. What merge strategy does TinyStateGraph currently use?
23. Why is simple dictionary replacement insufficient for parallel list accumulation?
24. What is a reducer?
25. Why did we intentionally *not* implement reducers in the handwritten graph?
26. List five production capabilities TinyStateGraph intentionally omits.

### Exercise 1 — Add a third route

Extend `handwritten_state_graph.py` with:

```text
billing
technical
general
```

Requirements:

- keep routing deterministic;
- add a `general` node;
- preserve an explicit route allowlist;
- add a test for the new route.

---

# Part C — LangGraph basics

27. What is `StateGraph`?
28. Why must it be compiled before normal execution?
29. What is the difference between `builder` and `graph` in our examples?
30. What does `graph.invoke()` return in the simple examples?
31. What does `stream_mode="updates"` show?
32. Why can node names matter operationally?
33. When would you use `MessagesState` instead of a custom state schema?
34. Why did Tiny-Agent start with a custom explicit schema instead?
35. What does `add_conditional_edges()` do?
36. Why should route values remain constrained/application-owned?

### Exercise 2 — Add validation

Modify `langgraph_state_graph.py`:

```text
START
  -> classify
  -> validate_route
  -> billing / technical
```

The `validate_route` node must reject unexpected routes before dispatch.

Question: is a separate validation node actually justified here, or is the destination mapping already sufficient? Explain your design choice.

---

# Part D — ReAct graph

37. Draw the Stage 01 ReAct loop as a graph.
38. Which node calls the model?
39. Which node owns tool execution?
40. Which edge forms the feedback loop?
41. Which state field carries pending actions between the model and tool nodes?
42. Why does `call_id` still matter after moving to LangGraph?
43. Why did graph orchestration not change the Function Calling protocol?
44. Why does Tiny-Agent retain `max_model_steps` in the graph version?
45. What Stage 01 production limitation is intentionally still present in the graph tool-error example?

### Exercise 3 — Direct-answer path

Create a fake model that immediately returns:

```python
ModelResponse(final_answer="No tool needed.")
```

Write a test proving that the `tools` node never executes.

---

# Part E — LangChain vs LangGraph

46. What problem does LangChain primarily solve for Tiny-Agent?
47. What problem does LangGraph primarily solve?
48. Can LangGraph be used without LangChain?
49. Why does the LangChain `@tool` decorator not change the underlying Function Calling mechanism?
50. What did Tiny-Agent's custom `Tool` abstraction teach before the framework decorator was introduced?
51. What does `ToolMessage.tool_call_id` correspond to in our Stage 01 runtime?
52. Why does Tiny-Agent not replace all earlier code with `create_agent()`?

### Exercise 4 — Compare tool schemas

Print and compare:

- Tiny-Agent `Tool.schema()`;
- LangChain decorated tool JSON schema.

Write down which differences are representation details and which affect model behavior.

---

# Part F — Persistence and interrupts

53. What is a checkpoint?
54. Why is a checkpoint more than chat history?
55. What is a `thread_id`?
56. Why should `thread_id` not simply be treated as `user_id`?
57. Why is `InMemorySaver` useful for tests but not production persistence?
58. Why do interrupts require persistence/checkpointing?
59. How do you resume an interrupt?
60. What value does `Command(resume=...)` provide to the interrupted node?
61. What is the most important restart semantic of an interrupted node?
62. Why can a side effect before `interrupt()` execute twice?
63. What is idempotency?
64. Why should a risky side effect normally happen after approval rather than before it?
65. Why should you not indiscriminately catch the control-flow mechanism used by `interrupt()`?
66. Why does human approval not replace permission checks?

### Exercise 5 — Reject path

Run `checkpoint_interrupt_demo.py` with:

```python
Command(resume=False)
```

Confirm that the graph reaches the cancellation node and final state is rejected.

Then modify the interrupt payload to include:

```text
risk level
requested action
reason for approval
```

Keep the payload JSON-serializable.

---

# Part G — Planner–Executor graph

67. Which Stage 02 concepts appear in `planner_executor_graph.py`?
68. Where is the initial plan stored?
69. What observation causes the replan transition?
70. Why does the replanner return only remaining work?
71. Why is completed work stored separately?
72. What prevents unlimited replanning in the example?
73. Why is this graph still deterministic even though it contains planning terminology?
74. Where could a real `StructuredPlanner` be inserted later?

### Exercise 6 — Add a replan budget state field

Move the hard-coded replan policy into explicit state/configuration.

Requirements:

- track `max_replans`;
- stop gracefully rather than raising an unhandled exception;
- record a failure reason;
- add deterministic tests.

---

# Part H — Architecture / interview questions

75. When would you prefer an ordinary Python workflow to LangGraph?
76. What symptoms indicate that implicit local-variable state has become difficult to manage?
77. Explain the sentence: "Graph is an orchestration representation; Agent is an autonomy pattern."
78. Explain how `continue` in a loop maps to a graph edge.
79. Explain how an `if` statement maps to a conditional edge.
80. What does LangGraph add beyond syntax?
81. What complexity does LangGraph introduce?
82. Why is framework adoption an engineering trade-off rather than a maturity badge?
83. How would you explain LangChain vs LangGraph in a two-minute interview answer?
84. If a graph has persistence but no LLM, is it an Agent? Why?
85. If an Agent uses LangChain `create_agent()` but no custom LangGraph code, can it still be backed by LangGraph? Explain.
86. Why should framework version/API assumptions be verified against current official documentation?

---

# Capstone exercise for this stage

Build a small approval-aware support workflow:

```text
START
  |
  v
classify
  |
  +-- general -> answer -> END
  |
  +-- technical -> diagnose -> answer -> END
  |
  +-- billing -> prepare_action -> approval
                                  |
                                  +-- reject -> END
                                  |
                                  +-- approve -> execute -> END
```

Requirements:

- first implement it with `TinyStateGraph` where possible;
- then implement the full version with LangGraph;
- use explicit typed state;
- keep routing destinations application-owned;
- use an interrupt for billing approval;
- use `InMemorySaver` only for the demo;
- include at least one unit test for each branch;
- document which parts TinyStateGraph cannot support cleanly and why.

If you can implement and explain this exercise, you understand the central Stage 03 concepts rather than only the framework syntax.

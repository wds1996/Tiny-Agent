# Stage 03 复习题与练习

读完理论并运行示例后再做。尽量先从第一性原理回答，不要把源码当答案生成器。

---

# Part A — 核心概念

1. Stage 01 `while` loop 的 execution state 存在哪里？
2. 当这些状态变成 graph node 共享的 `TypedDict` 后，真正改变了什么？
3. 为什么 graph state 不等于 LLM context？
4. 为什么 graph state 不等于 long-term memory？
5. `State -> Partial<State>` 是什么意思？
6. 为什么 node 返回 partial update 通常比返回完整 state 更干净？
7. 什么是 graph node？
8. 什么是 fixed edge？
9. 什么是 conditional edge？
10. Stage 02 Router 与 conditional edge 有什么区别？
11. 为什么 `START` 与 `END` 有用？
12. 为什么 ReAct 天然形成 cycle？
13. 为什么 graph 仍然可能无限循环？
14. 即使框架有 generic recursion limit，为什么 application budget 仍要显式保留？
15. 为什么 graph 不自动等于 Agent？
16. 为什么 graph 不自动等于 multi-Agent？
17. 为什么 explicit planning 与 graph orchestration 是不同维度？

---

# Part B — TinyStateGraph

18. `TinyStateGraph.compile()` 会验证什么？
19. 为什么 graph construction 与 execution 要分开？
20. conditional router 返回 destination map 中不存在的 route 时会发生什么？
21. 为什么 destination map 是有用的 safety boundary？
22. TinyStateGraph 当前使用什么 merge strategy？
23. 为什么简单 dict replacement 不适合 parallel list accumulation？
24. 什么是 reducer？
25. 为什么手写 graph 故意不实现 reducer？
26. 列出 TinyStateGraph 故意省略的五项 production capability。

### Exercise 1 — 增加第三个 route

扩展 `handwritten_state_graph.py`：

```text
billing
technical
general
```

要求：

- routing 保持 deterministic；
- 增加 `general` node；
- 保留显式 route allowlist；
- 为新 route 增加测试。

---

# Part C — LangGraph 基础

27. `StateGraph` 是什么？
28. 为什么正常 execution 前要 compile？
29. 示例中的 `builder` 与 `graph` 有什么区别？
30. 简单示例中 `graph.invoke()` 返回什么？
31. `stream_mode="updates"` 展示什么？
32. node name 为什么有 operational value？
33. 什么情况下使用 `MessagesState` 而不是自定义 schema？
34. Tiny-Agent 为什么先从显式 custom state schema 开始？
35. `add_conditional_edges()` 做什么？
36. 为什么 route value 仍应受 application-owned mapping 约束？

### Exercise 2 — 增加 validation

修改 `langgraph_state_graph.py`：

```text
START
  -> classify
  -> validate_route
  -> billing / technical
```

`validate_route` 必须在 dispatch 前拒绝 unexpected route。

思考：单独 validation node 真有必要吗？还是 conditional destination mapping 已经足够？说明你的设计理由。

---

# Part D — ReAct graph

37. 把 Stage 01 ReAct loop 画成 graph。
38. 哪个 node 调 model？
39. 哪个 node 拥有 Tool execution？
40. 哪条 edge 形成 feedback loop？
41. 哪个 state field 在 model 与 tool node 间携带 pending action？
42. 为什么迁移到 LangGraph 后 `call_id` 仍重要？
43. 为什么 graph orchestration 没改变 Function Calling protocol？
44. Tiny-Agent 为什么在 graph 版仍保留 `max_model_steps`？
45. graph Tool-error 示例中仍故意保留了哪个 Stage 01 production limitation？

### Exercise 3 — Direct-answer path

创建一个 fake model，立即返回：

```python
ModelResponse(final_answer="No tool needed.")
```

写测试证明 `tools` node 从未执行。

---

# Part E — LangChain vs LangGraph

46. 对 Tiny-Agent 来说，LangChain 主要解决什么问题？
47. LangGraph 主要解决什么问题？
48. LangGraph 能否脱离 LangChain 使用？
49. 为什么 LangChain `@tool` decorator 不改变 Function Calling 本质？
50. 在引入框架 decorator 前，Tiny-Agent 自定义 `Tool` abstraction 教了什么？
51. `ToolMessage.tool_call_id` 对应 Stage 01 runtime 中什么？
52. Tiny-Agent 为什么不把前面所有代码替换成 `create_agent()`？

### Exercise 4 — 比较 Tool schema

打印并比较：

- Tiny-Agent `Tool.schema()`；
- LangChain decorated tool JSON schema。

指出哪些只是 representation difference，哪些会实际影响 model behavior。

---

# Part F — Persistence 与 interrupts

53. 什么是 checkpoint？
54. 为什么 checkpoint 不只是 chat history？
55. 什么是 `thread_id`？
56. 为什么 `thread_id` 不能直接当作 `user_id`？
57. 为什么 `InMemorySaver` 适合测试但不适合 production persistence？
58. 为什么 interrupts 需要 persistence/checkpointing？
59. 如何 resume 一个 interrupt？
60. `Command(resume=...)` 向 interrupted node 提供什么？
61. interrupted node 最重要的 restart semantic 是什么？
62. 为什么 `interrupt()` 前的 side effect 可能执行两次？
63. 什么是 idempotency？
64. 为什么 risky side effect 通常应该发生在 approval 后？
65. 为什么不能随手把 `interrupt()` 的 control-flow mechanism 用通用 `try/except` 吞掉？
66. 为什么 human approval 不替代 permission check？

### Exercise 5 — Reject path

运行 `checkpoint_interrupt_demo.py`，使用：

```python
Command(resume=False)
```

确认 graph 到 cancellation node，final state 为 rejected。

然后把 interrupt payload 扩展为：

```text
risk level
requested action
reason for approval
```

保持 JSON-serializable。

---

# Part G — Planner–Executor graph

67. `planner_executor_graph.py` 中出现了哪些 Stage 02 概念？
68. initial plan 存在哪里？
69. 什么 observation 会触发 replan transition？
70. 为什么 replanner 只返回 remaining work？
71. 为什么 completed work 单独保存？
72. 示例如何防止 unlimited replanning？
73. 为什么这个 graph 即使有 planning terminology 仍然可以是 deterministic？
74. 以后真正的 `StructuredPlanner` 可以插在哪里？

### Exercise 6 — 增加 replan budget state

把 hard-coded replan policy 移入显式 state/config。

要求：

- track `max_replans`；
- graceful stop，而不是未处理异常；
- 记录 failure reason；
- 增加 deterministic tests。

---

# Part H — 架构 / 面试题

75. 什么情况下优先普通 Python workflow 而不是 LangGraph？
76. 哪些症状说明 implicit local-variable state 已经难管理？
77. 解释：“Graph is an orchestration representation; Agent is an autonomy pattern.”
78. `continue` 如何映射到 graph edge？
79. `if` 如何映射到 conditional edge？
80. LangGraph 除了语法之外真正增加了什么？
81. LangGraph 又引入了哪些复杂度？
82. 为什么 framework adoption 是 engineering trade-off，而不是 maturity badge？
83. 用两分钟解释 LangChain vs LangGraph。
84. 一个 graph 有 persistence 但完全没有 LLM，它是 Agent 吗？为什么？
85. 一个 Agent 使用 LangChain `create_agent()`，但没有用户手写 LangGraph code，它是否仍可能由 LangGraph 驱动？解释。
86. 为什么 framework version/API assumption 必须根据当前官方文档重新确认？

---

# 本阶段 Capstone Exercise

构建一个 approval-aware support workflow：

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

要求：

- 能用 `TinyStateGraph` 表达的部分先手写；
- 再用 LangGraph 完成完整版本；
- 使用 explicit typed state；
- routing destination 必须 application-owned；
- billing approval 使用 interrupt；
- demo 中只使用 `InMemorySaver`；
- 每个 branch 至少一个 unit test；
- 说明哪些部分 TinyStateGraph 无法干净支持，以及为什么。

如果你不仅能跑通，还能解释这个 exercise，说明你学到的是 Stage 03 的 stateful orchestration，而不是只背了 LangGraph syntax。
# Stage 03 — 有状态编排：从状态机到 LangGraph

Stage 03 把 Tiny-Agent 从进程内的 `while` 循环和普通 workflow，推进到 **显式有状态编排（stateful orchestration）**。

本阶段的教学顺序是刻意设计的：

```text
Python 局部变量中的隐式状态
        ->
显式共享状态
        ->
手写 TinyStateGraph
        ->
LangGraph StateGraph
        ->
用 Graph 重建 ReAct
        ->
streaming / checkpoint / interrupt
```

目标不是背 LangGraph API，而是理解：**什么样的编排问题，真的值得引入图运行时。**

---

## 前置要求

请先完成 Stage 00–02，或至少已经理解：

- messages、Structured Output、Function Calling；
- ReAct / model → tool → observation 循环；
- Tool Registry 与 provider adapter；
- deterministic workflow 与 Agent 的区别；
- router 与 conditional dispatch；
- Planner–Executor 与 bounded replanning。

---

## 学习目标

完成本阶段后，你应该能够：

1. 区分隐式 execution state 与显式 graph state；
2. 区分 graph state、LLM context、checkpoint state 与 long-term memory；
3. 解释 `State -> Partial<State>`；
4. 实现 node、fixed edge、conditional edge、START/END 与 cycle；
5. 解释 reducer，以及为什么 merge semantics 很重要；
6. 不依赖框架手写一个最小状态图；
7. 使用 LangGraph 的 `StateGraph`、`add_node`、`add_edge`、`add_conditional_edges`、`compile`、`invoke`、`stream`；
8. 把 Stage 01 的 ReAct loop 重写成 LangGraph graph；
9. 把 Stage 02 的 routing/planning recovery 表达成 graph transition；
10. 准确解释 LangChain 与 LangGraph 的职责边界；
11. 使用 LangChain message/tool abstraction，同时不把它们误认为 Agent runtime；
12. 解释 checkpointing 与 `thread_id`；
13. 在本地学习与测试中使用 `InMemorySaver`；
14. 用 `interrupt()` 暂停执行，并用 `Command(resume=...)` 恢复；
15. 解释为什么 interrupted node 会从节点开头重新执行，以及为什么 side effect 需要 idempotency；
16. 根据真实编排需求选择普通 Python 还是 graph runtime。

---

# 推荐学习顺序

## Part A — 为什么需要显式状态？

1. [为什么需要显式 State](theory/01-why-explicit-state.zh-CN.md)
2. [Agent 的状态机](theory/02-state-machines-for-agents.zh-CN.md)
3. [`code/handwritten_state_graph.py`](code/handwritten_state_graph.py)
4. [`../../src/tiny_agent/state_graph.py`](../../src/tiny_agent/state_graph.py)
5. [`../../tests/test_state_graph.py`](../../tests/test_state_graph.py)

到这里，你应该能在不使用 LangGraph 的情况下解释状态图机制。

## Part B — LangGraph 基础

6. [LangGraph Core Concepts](theory/03-langgraph-core-concepts.zh-CN.md)
7. [`code/langgraph_state_graph.py`](code/langgraph_state_graph.py)
8. [Loop vs Graph](theory/04-loop-vs-graph.zh-CN.md)
9. [`code/langgraph_react_agent.py`](code/langgraph_react_agent.py)
10. [`../../src/tiny_agent/langgraph_runtime.py`](../../src/tiny_agent/langgraph_runtime.py)
11. [`code/planner_executor_graph.py`](code/planner_executor_graph.py)

## Part C — LangChain 在哪里？

12. [LangChain vs LangGraph](theory/05-langchain-vs-langgraph.zh-CN.md)
13. [`code/langchain_component_examples.py`](code/langchain_component_examples.py)

## Part D — Stateful runtime 能力

14. [Persistence、Streaming 与 Interrupts](theory/06-persistence-streaming-and-interrupts.zh-CN.md)
15. [`code/checkpoint_interrupt_demo.py`](code/checkpoint_interrupt_demo.py)
16. [`../../tests/test_stage03_frameworks.py`](../../tests/test_stage03_frameworks.py)

## Part E — 复习

17. [复习题](exercises/review-questions.zh-CN.md)

---

# 本阶段引入的框架

## LangGraph — Stage 03 的主框架

Tiny-Agent 选择 LangGraph，是因为它的抽象几乎可以直接映射到我们已经手写过的机制：

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

项目当前面向稳定的 LangGraph 1.x：

```text
langgraph >= 1.2, < 2
```

框架 API 演进很快，因此后续更新本阶段时，应重新核对官方文档，而不是相信两年前某篇博客的截图。

## LangChain — 支撑组件层

本阶段只引入 LangChain 中适合复用的部分：

- messages；
- tool wrappers；
- model interface concepts；
- 后续 document/retriever integrations。

Tiny-Agent **不会**用一个高层 `create_agent()` 把前面的学习过程抹掉。

推荐心智模型：

```text
LangChain
    -> LLM 应用组件、集成与高层 Agent API

LangGraph
    -> 低层有状态编排 / runtime

Tiny-Agent
    -> 用透明手写实现解释这些机制为什么存在
```

项目当前面向稳定的 LangChain 1.x：

```text
langchain >= 1.3, < 2
```

---

# 外部学习资源

Tiny-Agent 负责从第一性原理解释机制，但一个持续快速变化的框架不应该只靠一个仓库学完。推荐的使用方式是：

```text
Tiny-Agent
    -> 理解为什么需要这个抽象

官方文档
    -> 确认当前 API 与框架语义

官方课程 / notebooks
    -> 做足练习

社区教程
    -> 获取另一种语言与讲解视角
```

## LangGraph

### 官方文档

- [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph Quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart)
- [Graph API Overview](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

### 官方实践材料

- [LangGraph Essentials — Python](https://academy.langchain.com/courses/langgraph-essentials-python)
- [LangChain Academy — Introduction to LangGraph notebooks](https://github.com/langchain-ai/langchain-academy)
- [LangGraph 101](https://github.com/langchain-ai/langgraph-101)

### 推荐中文教程

- [Dive into LangGraph — LangGraph 1.0 完全指南](https://www.luochang.ink/dive-into-langgraph/)

建议在本阶段 Part B 同步阅读其 **快速入门** 和 **状态图**；后面的 HITL、memory、RAG、MCP、多 Agent 等章节留到 Tiny-Agent 对应阶段再看。

> 社区教程非常适合理解与练习；但当社区示例与当前官方文档或 Tiny-Agent 测试依赖冲突时，以官方文档为 source of truth。

## LangChain

### 官方文档

- [LangChain Overview](https://docs.langchain.com/oss/python/langchain/overview)
- [LangChain Quickstart](https://docs.langchain.com/oss/python/langchain/quickstart)
- [Agents](https://docs.langchain.com/oss/python/langchain/agents)
- [Messages](https://docs.langchain.com/oss/python/langchain/messages)
- [Tools](https://docs.langchain.com/oss/python/langchain/tools)

### 官方实践材料

- [LangChain Essentials — Python](https://academy.langchain.com/courses/langchain-essentials-python)

### 完整初学者阅读路径

```text
1. Tiny-Agent Stage 01/02 theory
2. Tiny-Agent Stage 03 chapter 01-02
3. LangGraph official Overview
4. Tiny-Agent handwritten_state_graph.py
5. LangGraph Graph API + Quickstart
6. Tiny-Agent langgraph_state_graph.py
7. Dive into LangGraph：快速入门 + 状态图
8. Tiny-Agent LangChain vs LangGraph
9. LangChain Overview + Messages + Tools
10. LangGraph / LangChain Essentials 做强化练习
11. Tiny-Agent persistence / interrupt chapter
12. Official Persistence + Interrupt docs
```

这个顺序是为了避免两个常见失败模式：

- 还不知道问题是什么，就先把框架手册从头背到尾；
- 教程能跑，但完全不知道 runtime 在替你做什么。

---

# Stage architecture

LangGraph 版 ReAct 会把 Stage 01 改写成：

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

共享状态包括：

```text
messages
pending_tool_calls
final_answer
error
model_steps
```

注意三层职责没有改变：

```text
model       -> 提议 action
tool node   -> 执行 action
graph runtime -> 管理 stateful transition
```

LangGraph 没有把模型升级成“会执行 Python 的生物”。

---

# 可运行示例

## 1. 手写 graph

```bash
python stages/03-stateful-orchestration/code/handwritten_state_graph.py
```

## 2. 安装 Stage 03 依赖

```bash
pip install -e ".[stage03]"
```

连测试一起：

```bash
pip install -e ".[dev,stage03]"
```

## 3. LangGraph 版同一 workflow

```bash
python stages/03-stateful-orchestration/code/langgraph_state_graph.py
```

## 4. ReAct Agent graph

```bash
python stages/03-stateful-orchestration/code/langgraph_react_agent.py
```

## 5. Planner–Executor recovery graph

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

# 本阶段明确不宣称解决什么

Stage 03 只引入 stateful runtime mechanism，不等于“生产系统毕业”。仍然留到后续阶段的内容包括：

- production Postgres checkpoint infrastructure；
- long-term memory policy；
- 完整 user/session identity model；
- production async/concurrency strategy；
- tool permission framework；
- robust retry/timeout/cancellation；
- distributed graph execution；
- production LangSmith tracing/evaluation；
- persistent HITL UI。

还要记住：

> **有 graph 不等于有 Agent。**

确定性流程也可以画成图。Agent autonomy 仍然来自 model-directed decision。

---

# Tests

Core graph mechanism：

- [`../../tests/test_state_graph.py`](../../tests/test_state_graph.py)

LangGraph ReAct parity：

- [`../../tests/test_langgraph_runtime.py`](../../tests/test_langgraph_runtime.py)

LangGraph persistence/interrupt 与 LangChain component compatibility：

- [`../../tests/test_stage03_frameworks.py`](../../tests/test_stage03_frameworks.py)

CI 将 Stage 03 框架测试与轻量 core suite 分开，因此前面阶段不需要被迫安装所有框架依赖。

---

# 面试必须能讲清楚的句子

> **State 是继续执行所需的数据；model context 只是当前这次 LLM 调用真正发送出去的子集；long-term memory 又是另一套跨任务保留策略。**

> **Node 完成一个编排单元并返回 state update；edge 决定下一个执行位置。**

> **Graph 是编排表示；Agent 是 autonomy/control pattern。**

> **LangChain 主要提供 LLM application abstraction 和高层 Agent component；LangGraph 是低层 stateful orchestration runtime。**

> **Checkpointing 让 resume 成为可能；interrupt 依赖持久化状态与 resume value，但 interrupted node 可能从头重跑，因此 side effect 必须按幂等设计。**

---

# 阶段完成标准

当你可以完成以下事情时，Stage 03 才算真正完成：

1. 自己实现并测试一个小状态图；
2. 用 LangGraph 重现它；
3. 把 ReAct `while` loop 翻译成显式 graph state 与 edge；
4. 把 routing/replanning 翻译成 conditional transition；
5. 不把 LangChain 和 LangGraph 当同义词；
6. 演示 streaming updates；
7. 用 checkpointed interrupt 暂停并恢复 graph；
8. 能说明什么情况下 graph 的额外复杂度值得付出。
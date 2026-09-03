# 01 — ReAct 与 Agent Loop

## 1. 从 Tool Calling 到 Agent Behavior

一次 ToolCall 很直接：

```text
User -> Model -> Tool Call -> Runtime -> Tool Result -> Model -> Answer
```

但很多真实任务需要反复“行动—观察—再决策”：

```text
Question
  |
  v
Model decision
  |
  +-- use Tool --> observation --+
  |                               |
  +-------------------------------+
  |
  +-- final answer --> END
```

这里真正发生变化的不是 model architecture，而是 application 引入了一个**受控 execution loop**。

## 2. 一句话解释 ReAct

ReAct 把：

```text
对下一步该做什么进行 reasoning
```

与：

```text
对 external environment 执行 action
```

交替起来，再利用环境返回的 observation 继续任务。

经典抽象：

```text
Reason -> Act -> Observe -> Reason -> Act -> Observe -> ...
```

但从实现角度，最关键的是：

```text
Decide -> Act -> Observe -> Decide again
```

## 3. 为什么 Environment Feedback 很重要

假设研究任务：

```text
Find the latest paper about X and summarize its method.
```

model 一开始可能决定 search。

真正 search result 可能出现：

- title ambiguous；
- result stale；
- 多篇论文名字相似；
- metadata 缺失。

下一步 action 应该根据真实 search result 决定，而不能只依赖原始 user question。

这就是 environment interaction 与 one-shot generation 的本质差异。

## 4. ReAct 不要求暴露完整 Chain-of-Thought

历史上的 ReAct 常写成：

```text
Thought
Action
Observation
Thought
Action
Observation
...
```

但 production runtime 并不需要把 model 的 hidden reasoning 原样暴露或记录，才能实现 ReAct 的有效控制模式。

Tiny-Agent 关注的是可审计、真正与 runtime 有关的内容：

```text
Action
Arguments
Observation
Final Answer
```

这样 runtime 能获得实际需要的 execution state，同时不把内部 reasoning 当成必须外露的 trace artifact。

## 5. Action 与 Observation

### Action

model 提议的 external operation。

例如：

```text
search_web(query="ReAct paper")
query_database(sql="...")
calculator(a=12, b=7)
```

### Observation

runtime 执行 action 后，environment 返回的结果：

```text
Search results: ...
Database returned 12 rows
19
ToolError: request timed out
```

observation 应该进入下一轮 model decision。

## 6. 为什么 Runtime 拥有 Loop

model 不应该在没有 limits 的情况下直接控制 execution。

runtime 负责：

- proposed Tool 是否存在；
- arguments 是否 valid；
- execute 还是 refuse；
- 记录 observation；
- 统计 step；
- enforce budget；
- 何时必须 stop；
- 后续 permission / approval policy。

这是安全 Agent Engineering 的最基础边界。

## 7. 每一步的合法 High-Level Outcome

第一版 Tiny-Agent 中，一个 model step 只有两类有意义结果。

### A. 提议一个或多个 ToolCall

```text
ModelResponse(tool_calls=[...])
```

runtime 执行它们、追加 observations，然后开始下一轮 model turn。

### B. 返回 Final Answer

```text
ModelResponse(final_answer="...")
```

runtime 返回结果并结束。

如果 model 两者都没有返回，说明 model/runtime contract 被破坏了。

## 8. Stop Condition 必须存在

任何 autonomous loop 都可能不终止：

```text
search -> search -> search -> search -> ...
```

因此 runtime 必须有明确 stop rule。

Tiny-Agent 第一条规则：

```text
max_steps
```

后续 Stage 会进一步加入：

- maximum Tool calls；
- retry limits；
- timeout budgets；
- token budgets；
- cost budgets；
- cancellation；
- loop detection。

## 9. Tool Failure 也是 Environment 的一部分

假设 model 提议：

```text
calculator(a="hello", b=7)
```

一个可恢复 failure 可以作为 observation 返回：

```text
ToolError[TypeError]: ...
```

model 可以继续决定：

- 修复 arguments；
- 换 Tool；
- 向用户补问；
- 停止并解释 failure。

这并不意味着所有 error 都应该吞掉并交给模型处理。

后续 Stage 会区分 recoverable operational failure、permission failure、system failure 与 fatal runtime error。

## 10. Agent Loop vs Workflow

### Deterministic Workflow

developer 决定路径：

```text
parse -> retrieve -> rerank -> answer
```

### Agent Loop

model 根据当前 state / observation 动态选择 next action：

```text
state
-> model decision
-> action
-> new state
-> model decision
```

真实 production system 经常混合使用两者。

Tiny-Agent 的原则始终是：

> **已知正确 control rule 时优先用 deterministic code；只有真正需要 semantic judgment 的地方才交给 model。**

## 11. 关键结论

- ReAct 的核心是 decision、action、observation 的交替。
- Environment feedback 会改变未来 model decision。
- runtime，而不是 model，拥有 execution 与 stopping。
- ReAct-style runtime 不需要公开 hidden chain-of-thought。
- autonomous loop 必须有 explicit stopping condition。
- 可恢复 Tool error 可以成为 observation。
- Agentic control 只应在动态决策真的有价值时使用。

## 复习题

1. one-shot Function Calling 与 Agent loop 的差别是什么？
2. observation 到底是什么？
3. 为什么 stopping condition 应该由 runtime 拥有？
4. 为什么实现 ReAct 不要求输出 hidden reasoning？
5. 在什么情况下 deterministic workflow 比 Agent loop 更合理？
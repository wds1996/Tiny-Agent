# Agent 的状态机

理解 graph-based Agent runtime 最好的办法，是先把 LLM 拿掉，只看普通状态机。

核心机制很简单：

```text
current state + current node
            |
            v
         execute
            |
            v
       state update
            |
            v
      choose next node
```

---

## 1. Node

Node 是一个编排工作单元。

例如：

```text
classify request
call model
execute tools
validate output
retrieve documents
request approval
write final answer
```

一个常见 contract：

```python
def node(state):
    ...
    return {"field": new_value}
```

即：

```text
State -> Partial<State>
```

Node 通常应该只做一个语义上连贯的工作单元。

---

## 2. Edge

Edge 决定哪个 node 下一个运行。

固定 transition：

```text
parse -> validate
```

条件 transition：

```text
classify
   |
   +-- billing   -> billing_workflow
   +-- technical -> technical_workflow
```

和 Stage 02 Router 的区别要说清楚：

- **Router** 计算 route decision；
- **conditional edge** 把 route decision 变成 graph control flow。

Router 可以被放进 graph，但 Router 本身不是 graph。

---

## 3. START 与 END

多数 graph runtime 会使用结构性 sentinel：

```text
START -> first_node
last_node -> END
```

它们不是 business logic，只是让 topology 的入口和终止更明确。

---

## 4. Cycle

Agent graph 经常有 cycle，而不仅仅是 DAG。

ReAct 天然是：

```text
model
  |
  | tool call
  v
tools
  |
  v
model
```

当 model 给出 final answer 时退出：

```text
model -> END
```

这也是 graph runtime 对 Agent 有价值的原因之一：真实 Agent control flow 往往不是单向流水线。

---

## 5. 有 cycle 仍然需要 budget

把 loop 画成 graph 并不会自动解决无限循环。

错误推理：

```text
LangGraph manages the loop
=> the loop is safe
```

仍然需要 application-owned limit，例如：

```text
max model turns
max tool calls
max retries
max replans
time budget
cost budget
```

Tiny-Agent 的 `build_langgraph_agent()` 仍显式保留 `max_model_steps`，即便 LangGraph 自己也有 recursion safeguard。

Generic framework limit 不能替代业务自己的 policy。

---

## 6. 手写 `TinyStateGraph`

Stage 03 引入：

```text
src/tiny_agent/state_graph.py
```

它的 API 故意接近 LangGraph 的核心概念：

```python
builder = TinyStateGraph()

builder.add_node("classify", classify)
builder.add_node("billing", billing)

builder.add_edge(START, "classify")

builder.add_conditional_edges(
    "classify",
    route,
    {
        "billing": "billing",
        "technical": "technical",
    },
)
```

然后：

```python
graph = builder.compile()
result = graph.invoke(initial_state)
```

它不是为了和 LangGraph 竞争，而是为了把机制拆给你看。

---

## 7. 为什么分 builder 与 compiled graph

我们把流程拆成：

```text
Graph definition
      ↓
validation / compile
      ↓
Executable graph
```

构建期可以验证：

- node name；
- unknown edge target；
- 是否缺 START transition；
- duplicate outgoing transition。

编译后再专注 execution。

LangGraph 也是类似思路：`StateGraph` 是 builder，`.compile()` 才得到可执行 graph。

---

## 8. State transition 示例

Initial state：

```python
{
    "request": "I was charged twice"
}
```

`classify` 返回：

```python
{"route": "billing"}
```

merge 后：

```python
{
    "request": "I was charged twice",
    "route": "billing",
}
```

conditional edge 读取：

```python
state["route"]
```

选择：

```text
billing
```

billing node 再返回：

```python
{"answer": "..."}
```

最终：

```python
{
    "request": "I was charged twice",
    "route": "billing",
    "answer": "...",
}
```

所以 graph 本质上是一连串 **state transformation + transition**。

---

## 9. Reducer 与 merge

手写 graph 只使用：

```python
state.update(partial_update)
```

串行教学示例够用了。

但如果两个 branch 都更新：

```text
results
```

一个写：

```python
["A"]
```

另一个写：

```python
["B"]
```

最终应该是：

```python
["B"]
```

还是：

```python
["A", "B"]
```

这就需要 merge policy。

LangGraph 可以给 state key 定义 reducer，决定 update 如何合并。

它对以下场景尤其重要：

- message history；
- parallel branch；
- accumulated evidence；
- event list。

TinyStateGraph 故意不实现 reducer，避免一开始把教学 runtime 变成迷你框架项目。

---

## 10. Graph branch 与并发执行不是一回事

画出：

```text
       /-> A -\
START          JOIN
       \-> B -/
```

只表示 dependency structure，不自动意味着 A/B 物理并发。

就像 Stage 01 已经强调：

```text
multiple tool calls != concurrent Python execution
```

Stage 03 再加一条：

```text
graph branches != automatically concurrent execution
```

真正的 execution semantics 由 runtime 定义。

---

## 11. Graph topology 不定义 Agent autonomy

```text
START -> parse -> validate -> save -> END
```

是 graph，但不是 Agent。

而：

```text
model -> tools -> model
```

如果 model 动态决定 action，就具有 Agentic control。

因此：

> **Graph 是 orchestration representation；Agent 是 control/autonomy pattern。**

不要混用。

---

## 12. TinyStateGraph 故意省略什么

它不实现：

- persistent checkpoints；
- interrupts；
- streaming；
- reducers；
- parallel supersteps；
- async execution；
- subgraphs；
- time-travel debugging；
- durable retry semantics；
- distributed execution。

这些省略恰恰说明：当编排需求变复杂时，引入成熟 runtime 是合理的。

---

## 完成检查

你应该能解释：

1. Node vs edge；
2. Router vs conditional edge；
3. START/END；
4. 为什么 ReAct 会形成 graph cycle；
5. 为什么 cycle 仍需 application budget；
6. builder vs compiled runtime；
7. reducer 为什么对 accumulated/parallel state 很重要；
8. 为什么 graph 不自动等于 Agent。
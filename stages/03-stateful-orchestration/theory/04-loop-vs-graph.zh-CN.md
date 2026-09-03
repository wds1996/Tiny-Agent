# Loop vs Graph：到底改变了什么？

一个常见误区，是把手写 Agent loop 和 LangGraph 比成“简单版”和“智能版”。

这不是正确比较方式。

二者完全可以实现相同的 Agent policy。

真正变化的是：**orchestration state 与 transition 如何被表示、检查和管理。**

---

## 1. Stage 01 loop

Stage 01 的 runtime 概念上是：

```python
for step in range(max_steps):
    response = model.generate(messages, tool_schemas)

    if response.tool_calls:
        execute_tools()
        append_observations()
        continue

    if response.final_answer is not None:
        return final_answer
```

这是很好的教学代码：你可以从上到下一口气读完整个 control flow。

---

## 2. 等价 graph

同样逻辑可以画成：

```text
START
  |
  v
model
  |
  +-- final/error --> END
  |
  +-- tool calls --> tools
                       |
                       +----> model
```

Agent 没有因此“更自主”。仍然是：

```text
model decides action
runtime executes tool
observation goes back to model
```

只是 orchestration representation 改了。

---

## 3. 两种实现如何映射

### Loop variable

```python
messages
```

变成：

```python
state["messages"]
```

### `continue`

```python
continue
```

变成 edge：

```text
tools -> model
```

### `if tool_calls`

变成 conditional edge：

```text
model --route--> tools / END
```

### Step counter

仍然是 application state/policy：

```python
state["model_steps"]
```

### final `return`

变成：

```text
model -> END
```

---

## 4. Graph 会让什么事情更容易

### A. 查看 topology

Loop 的 topology 藏在代码里；graph 把 transition 显式声明出来。

流程变大后，更容易回答：

```text
哪些 node 可以到 approval？
retrieval fail 后去哪？
哪个 cycle 会回 planning？
```

### B. Pause / resume

Process-local loop 默认进程一直活着。带 checkpoint 的 graph runtime 可以保存 execution state，之后继续。

### C. Streaming progress

可以按 node/state update 暴露进度，不用到处散落 `print()`。

### D. Human-in-the-loop

可在 approval point suspend，并保留恢复所需 state。

### E. Persistence / replay

State snapshot 支持 debug、resume、replay，甚至从旧 checkpoint 分出不同 trajectory。

---

## 5. Graph 会带来什么额外复杂度

Graph 不是免费午餐，会引入：

```text
state schemas
merge/reducer semantics
node boundaries
graph configuration
checkpoint identity
framework versioning
streaming modes
interrupt semantics
```

如果只是三个固定步骤，这些可能全是多余负担。

---

## 6. Graph 也可以把 control flow 写得更糟

坏 graph 常见表现：

- 数十个没有语义边界的小 node；
- 同一个 state key 被拿来干多种无关事情；
- routing logic 分散在 prompt 和隐藏 middleware 中；
- 为了图大一点，把每个函数都变成 node；
- 主流程没搞懂就疯狂上 subgraph。

Tiny-Agent 的规则是：

> **Node 应代表有意义的 orchestration boundary，而不是每一次 function call。**

---

## 7. Graph 不等于 multi-Agent

```text
model -> tools -> model
```

可以只有一个 Agent。

```text
parse -> validate -> save
```

可以一个 Agent 都没有。

```text
supervisor -> specialist A / specialist B
```

才可能是 multi-Agent。

Graph topology 本身不决定 Agent 数量。

---

## 8. Graph 不等于 planning

Graph 可以只是固定：

```text
A -> B -> C
```

Planner 也可以完全不用 graph framework，动态生成 plan。

二者是两个独立维度：

- Stage 02：planning policy；
- Stage 03：execution representation。

它们可以组合：

```text
Planner node
    |
    v
Executor subflow
    |
    v
Validation / replan edge
```

---

## 9. 为什么保留旧 loop

Tiny-Agent 不会因为加入 LangGraph 就删掉 Stage 01。

因为它们回答的是不同问题：

### Stage 01

> 最小 Agent loop 是什么？

### Stage 03

> 什么时候、为什么要把 loop 升级成显式有状态编排？

删除旧实现反而会失去最有价值的对照。

---

## 10. 如何选择 loop 还是 graph

优先 loop/workflow，当：

- control flow 很小；
- state 很自然地放在局部变量；
- 不需要 pause/resume；
- 不需要 persistence；
- 一个开发者可以轻松跟完整个函数。

考虑 graph，当：

- branch/cycle 较多；
- execution 要跨 interruption；
- state 要被外部检查；
- 需要 checkpoint；
- 需要 human approval；
- 需要 node-level progress streaming；
- 多团队/组件需要稳定 orchestration boundary。

---

## 11. 真正应该问的问题

不要先问：

> 要不要用 LangGraph？

先问：

> 普通 Python 中哪个 orchestration problem 已经难以管理？LangGraph 的哪项 runtime capability 能让它更简单或更安全？

答不出来，就说明引入 graph 很可能过早。

---

## 完成检查

不用框架术语解释：

1. `continue` 如何映射到 edge；
2. `if` 如何映射到 conditional edge；
3. local variable 如何映射到 state；
4. graph 除了语法变化还真正提供什么；
5. graph 新增哪些复杂度；
6. 为什么 graph、Agent、planning、multi-Agent 是不同概念。
# LangGraph 核心概念

只有在我们已经自己实现过相同机制之后，Tiny-Agent 才正式引入 LangGraph。

这样你会更容易理解它的抽象：

```text
TinyStateGraph concept        LangGraph concept
----------------------        -----------------
shared dict state             State schema
node(state) -> updates        Graph node
fixed transition              add_edge
conditional transition        add_conditional_edges
START / END                   START / END
compile                       StateGraph.compile()
invoke                        compiled_graph.invoke()
```

---

## 阅读前的配套资料

如果 `StateGraph`、node、edge、reducer、checkpoint 对你都很陌生，不要只靠这一篇。

**官方资料**

- [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph Quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart)
- [Graph API Overview](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph Essentials — Python](https://academy.langchain.com/courses/langgraph-essentials-python)
- [LangGraph 101](https://github.com/langchain-ai/langgraph-101)

**中文配套教程**

- [Dive into LangGraph — LangGraph 1.0 完全指南](https://www.luochang.ink/dive-into-langgraph/)

推荐初学顺序：

```text
Tiny-Agent handwritten state graph
    -> LangGraph official Overview
    -> 本章
    -> official Graph API / Quickstart
    -> Tiny-Agent LangGraph examples
    -> Dive into LangGraph 补充练习
```

框架 API 变化很快。社区教程负责讲解，官方文档负责当前事实。

---

## 1. LangGraph 是什么

LangGraph 是面向 long-running、stateful workflow 与 Agent 的低层 orchestration framework/runtime。

它主要负责：

- shared state；
- graph transition；
- durable execution；
- streaming；
- human-in-the-loop；
- persistence。

它并不要求使用 LangChain，尽管二者经常一起出现。

---

## 2. State schema

最简单的 state 可以用 `TypedDict`：

```python
from typing import TypedDict

class State(TypedDict, total=False):
    request: str
    route: str
    answer: str
```

然后：

```python
from langgraph.graph import StateGraph

builder = StateGraph(State)
```

Schema 不只是 IDE 装饰，它描述了 graph 中什么数据能够流动，是 orchestration design 的一部分。

---

## 3. Node

Node 读取 state，返回 update：

```python
def classify(state: State):
    return {"route": "billing"}
```

概念上：

```text
State -> Partial<State>
```

Node 内部可以是：

- deterministic Python；
- model call；
- Tool execution；
- retrieval；
- validation；
- approval logic。

Graph 从来没规定每个 node 都必须调用 LLM。

---

## 4. 添加 node

```python
builder.add_node("classify", classify)
builder.add_node("billing", billing)
```

当前 LangGraph 也支持直接传 callable 并推断 node name；Tiny-Agent 更常显式命名，因为 topology 更清楚。

Node name 也是 operational identifier，会进入：

- trace；
- streaming update；
- interrupt；
- debugging；
- test assertion。

所以名字应描述“做什么工作”，而不是实现琐事。

---

## 5. START 与 END

```python
from langgraph.graph import START, END

builder.add_edge(START, "classify")
builder.add_edge("billing", END)
```

它们显式表示 entry 与 termination。

---

## 6. Fixed edge

固定 edge 表示：

```text
node A 完成 -> node B
```

例如：

```python
builder.add_edge("tools", "model")
```

这就是 ReAct feedback edge。

---

## 7. Conditional edge

Router 可以输出 route key：

```python
def route_after_model(state):
    if state["final_answer"] is not None:
        return "end"
    return "tools"
```

Graph 再把 route key 映射到 destination：

```python
builder.add_conditional_edges(
    "model",
    route_after_model,
    {
        "tools": "tools",
        "end": END,
    },
)
```

这里继续保持 Stage 02 的 safety boundary：

```text
router output
    ↓
application-owned route mapping
    ↓
actual destination
```

模型输出不是任意跳转地址。

---

## 8. Compile

`StateGraph` 是 builder，需要先：

```python
graph = builder.compile()
```

编译后的 graph 才有：

```text
invoke
ainvoke
stream
astream
```

Persistence/checkpointer 也在 compile 时配置。

---

## 9. Invoke

```python
result = graph.invoke(
    {"request": "I was charged twice"}
)
```

对于正常完成的简单 graph，返回 final graph state。

这与 Stage 01 的 `AgentResult` 不完全一样。Graph-oriented application 往往携带更多 internal state，因此后续更需要明确 public output schema。

---

## 10. Stream

不必等整个 graph 结束：

```python
for update in graph.stream(
    initial_state,
    stream_mode="updates",
):
    print(update)
```

`updates` 可以观察 graph step 之后的 state update。

Streaming 不只等于 token streaming，还可以是：

- node/state update；
- model message chunk；
- custom progress signal；
- checkpoint/task event。

第 06 章继续展开。

---

## 11. 用 graph 表达 ReAct

Stage 01：

```text
while True:
    response = model()
    if tool_calls:
        execute_tools()
        continue
    return final
```

Stage 03：

```text
             +---------+
      START ->|  model  |
             +----+----+
                  |
            conditional
             /         \
            v           v
       +---------+     END
       |  tools  |
       +----+----+
            |
            +----------> model
```

**Agent semantics 没变，orchestration representation 变了。**

---

## 12. `MessagesState`

LangGraph 提供 `MessagesState` 等 message-oriented helper，适合 chat/tool Agent，因为 message accumulation 需要 merge semantics。

Tiny-Agent 的第一个 graph 示例故意不用它，而是把字段显式写出来：

```text
messages
pending_tool_calls
final_answer
error
model_steps
```

先理解字段，再使用 helper，你才能判断 abstraction 是否适合，而不是把它当魔法。

---

## 13. Reducer

State field 可以定义 reducer：

```text
old_value + new_update -> merged_value
```

对于 list/message 或 parallel branch 尤其重要。

每当两个 node 可能写同一 state key，都应该问：

> 合并到底应该是什么意思？

不要因为教程写了某个 reducer 就照抄。

---

## 14. Graph API vs Functional API

当前 LangGraph 同时提供：

- Graph API：显式 node/edge；
- Functional API：function/task-oriented syntax + runtime capability。

Tiny-Agent 先教 Graph API，因为本阶段就是要把 state transition 展开给你看。先上 Functional API 会把我们真正想学的东西藏起来。

---

## 15. LangGraph 不替代 policy

LangGraph 可以运行 workflow，但它不决定：

- permission model；
- tool allowlist；
- business budget；
- security policy；
- safe error redaction；
- quality threshold。

框架是 infrastructure，不是 governance。

因此 Tiny-Agent graph Agent 仍保留：

```python
max_model_steps
```

---

## 16. Version discipline

Agent framework 更新很快。Tiny-Agent 把 LangGraph/LangChain 保持为 Stage 03 optional dependency，而不是 core dependency。

当前目标版本：

```text
langgraph >= 1.2, < 2
langchain >= 1.3, < 2
```

未来更新示例时，应重新核对官方文档，而不是让旧博客变成“祖传 API”。

---

## 完成检查

你应该能凭记忆写出：

1. TypedDict state；
2. 两个 node；
3. START edge；
4. conditional edge；
5. END transition；
6. `compile()`；
7. `invoke()` 与 `stream()`。

更重要的是，你要能解释每一个东西为什么存在。
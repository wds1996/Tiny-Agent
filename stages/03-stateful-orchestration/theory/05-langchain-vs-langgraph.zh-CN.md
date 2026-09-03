# LangChain vs LangGraph

很多初学者会同时看到这两个名字，然后以为它们是“做同一件事的两个框架”。

这过于粗糙。

在 Tiny-Agent 中，请先使用这个心智模型：

```text
LangChain
    -> 可复用的 LLM 应用抽象与 integrations

LangGraph
    -> 低层 stateful orchestration / runtime
```

当前 LangChain 的高层 Agent 本身也建立在 LangGraph 之上，所以理解分层非常重要。

---

## 推荐配套资料

如果第一次接触 LangChain，先读这些：

- [LangChain Overview](https://docs.langchain.com/oss/python/langchain/overview)
- [LangChain Quickstart](https://docs.langchain.com/oss/python/langchain/quickstart)
- [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain Messages](https://docs.langchain.com/oss/python/langchain/messages)
- [LangChain Tools](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain Essentials — Python](https://academy.langchain.com/courses/langchain-essentials-python)

LangGraph 相关：

- [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [Graph API Overview](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph Essentials — Python](https://academy.langchain.com/courses/langgraph-essentials-python)
- [Dive into LangGraph — LangGraph 1.0 完全指南](https://www.luochang.ink/dive-into-langgraph/)

别急着同时背两个框架。每看到一个 abstraction，先问：

> 它描述的是 LLM/application primitive，还是控制 stateful execution？

这个问题能过滤掉大量概念噪声。

---

## 1. LangChain 提供什么

LangChain 为常见 LLM application component 提供标准化 abstraction，例如：

- messages；
- model interfaces；
- tools；
- agent abstractions；
- document/retriever integrations；
- provider integrations。

它的主要价值之一是减少 provider-specific 和 application boilerplate。

---

## 2. Messages

Tiny-Agent 当前用普通 dict：

```python
{
    "role": "user",
    "content": "hello",
}
```

LangChain 提供：

```python
HumanMessage(content="hello")
AIMessage(content="...")
ToolMessage(content="42", tool_call_id="call_1")
```

这些对象标准化了 message metadata、multimodal/provider interaction。

但要先理解 Stage 00/01 中的 role 与 tool-call correlation，否则 abstraction 很容易变成“会跑就行”的黑箱。

---

## 3. Tools

Tiny-Agent：

```python
Tool(
    name="multiply",
    description="Multiply two numbers.",
    parameters={...},
    handler=multiply,
)
```

LangChain：

```python
from langchain.tools import tool

@tool
def multiply(a: int, b: int) -> int:
    """Multiply two integers exactly."""
    return a * b
```

Decorator 可以根据 type hint 与 docstring 推导 metadata/schema。

这是 convenience abstraction，不是另一种 Function Calling 原理。

模型依然看到 Tool description/schema，并生成 ToolCall proposal。

---

## 4. Models

Tiny-Agent 自己实现 provider-neutral `Model` protocol 和 OpenAI adapter，是为了把 boundary 展开教学。

LangChain 则提供跨 provider 的标准 model interface，适合需要：

- consistent model invocation；
- provider switching；
- standard tool binding；
- standard message types；
- middleware/integration support。

但如果在理解 provider boundary 之前就只会高层 API，很容易看不到 `call_id`、provider state 等关键细节。

---

## 5. LangChain Agent

LangChain 提供高层 Agent API，适合快速建立 production-oriented tool-calling Agent。

Tiny-Agent 故意不在 Stage 01 直接写：

```python
create_agent(...)
```

因为教学目标是：

```text
先理解 loop
        ↓
再理解 graph orchestration
        ↓
最后评估 high-level abstraction
```

只有知道一个 shortcut 省掉了什么，它才真正有价值。

---

## 6. LangGraph 提供什么

LangGraph 聚焦 execution orchestration：

- explicit state；
- node/edge；
- conditional transition；
- cycle；
- persistence/checkpoint；
- durable execution；
- interrupt；
- streaming；
- subgraph；
- HITL infrastructure。

它不要求 node 必须用 LangChain。普通 Python、自定义 model client、Tiny-Agent component 都可以放进去。

---

## 7. 二者可以一起使用

常见架构：

```text
LangChain model abstraction
          |
          v
LangGraph model node
          |
          v
LangChain tool abstraction
          |
          v
LangGraph tool node / workflow
```

简单说：

```text
LangChain supplies reusable components
LangGraph supplies orchestration
```

---

## 8. Tiny-Agent 的角色

Tiny-Agent 不试图替代这两个项目，而是做透明 reference implementation：

```text
Stage 00/01
    -> 学 API/tool/Agent mechanism

Stage 02
    -> 学 workflow/planning control

Stage 03
    -> 对照 handwritten orchestration 与 LangGraph/LangChain
```

目标是当你以后看到：

```python
create_agent(...)
```

或者：

```python
StateGraph(...)
```

你能指出下面隐藏了哪些责任，而不是只会复制示例。

---

## 9. 不要为了“像框架代码”而引入 abstraction

不好的理由：

```text
“这是 LangChain 项目，所以必须用 PromptTemplate。”
“这是 Agent，所以一定要 graph。”
“所有函数都包成 @tool。”
```

应该问：

- 这个 abstraction 是否减少了有意义的 boilerplate？
- 是否标准化了 provider variation？
- 是否改善 observability/composition？
- 团队是否需要它带来的 interoperability？

有目的地使用 abstraction。

---

## 10. 实际比较

| Concern | Tiny-Agent | LangChain | LangGraph |
|---|---|---|---|
| 学 raw Agent loop | 非常适合 | 通常被抽象 | 能表达，但 infrastructure 更多 |
| model/provider abstraction | 最小自定义 protocol | 强 | 非主要重点 |
| Tool abstraction | 最小自定义 Tool | 强 | 可消费 Tool，但非主角 |
| Stateful graph orchestration | 教学/最小 | 高层 Agent 间接使用 | 核心重点 |
| Checkpoint / interrupt | 手写 core 没有 | 在相关 Agent runtime 中暴露 | 核心能力 |
| RAG integration | Stage 04 | 生态成熟 | 编排 retrieval workflow |
| 快速高层 Agent | 故意手写 | `create_agent` | 更低层 |

---

## 11. 2026 生态分层心智模型

```text
High-level prebuilt Agent
        LangChain
            |
            v
Low-level orchestration runtime
        LangGraph
            |
            v
Provider/model/tool integrations
  LangChain components or your own code
```

这个 layering 以后仍可能变化，所以生产代码必须重新查看官方文档。

---

## 完成检查

你应该能回答：

1. 为什么 LangChain 与 LangGraph 不是可互换标签；
2. 为什么 LangGraph 可以不依赖 LangChain 使用；
3. 为什么 LangChain `@tool` 不改变 Function Calling 本质；
4. Tiny-Agent 为什么先手写 runtime 再教 `create_agent()`；
5. 哪一层更适合 model abstraction，哪一层更适合 stateful orchestration。
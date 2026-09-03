# LLM API 与基于 Message 的交互

## 1. 为什么从这里开始？

Agent 并不是一种特殊的模型类型。

绝大多数现代 Agent system，本质上都是：把普通 language model 放进一个 application runtime 中，由 runtime 反复发送 message、接收 model output、执行 external action，再把 observation 放回下一次 model call。

因此，在学习 Agent 之前，必须先理解 **model 与 application 的边界**。

## 2. 最基本的 Request–Response 模型

简化后的 LLM application：

```text
Application -> model(messages) -> model output
```

model 通常接收的是一组 messages，而不是一个完全没有结构的字符串。

概念上：

```python
messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant.",
    },
    {
        "role": "user",
        "content": "Explain tool calling.",
    },
]
```

application 把这些 messages 转换成 provider-specific API format，发送给 provider，再接收 response。

## 3. 常见 Message Role

### `system`

用于定义高层行为、约束、identity 或 task instruction。

例如：

- 以 programming tutor 身份回答；
- 使用简洁解释；
- destructive action 未获 approval 时不要执行。

不同 provider 的具体 semantics 会有差别，但架构上的概念稳定：它属于 application 提供、具有特殊 instructional importance 的 context。

### `user`

表示用户输入。

### `assistant`

表示之前的 model output。

multi-turn interaction 中，application 通常把之前的 assistant message 重新带入后续 request，使模型能够依据当前 conversation state 继续。

### `tool`

表示 external Tool 已经真正执行后返回的 observation。

这个 role 对 Agent 非常关键，因为它把：

```text
model decision
```

与：

```text
environment feedback
```

真正闭合成循环。

## 4. 如果 Application 不提供 State，就不要假设 Model 自己永久记得

一个常见误解是：API model 会永久记住上一次 call。

在多数 application architecture 中，模型真正能看到的是**当前 request 中 application 提供的 context**。

例如：

```text
Call 1:
[user: "My project is Tiny-Agent"]

Call 2:
[user: "What is my project called?"]
```

如果 Call 2 没有通过下面某种机制带回之前的信息：

- conversation history；
- memory retrieval；
- provider-managed session state；
- 其他 state mechanism；

application 就不能假设模型能够凭空恢复上一轮事实。

这直接得到一个 Agent engineering 原则：

> **Conversation history、task state、Tool observation 和 long-term memory 都是 runtime concern，而不是 LLM 隐藏在内部的魔法属性。**

## 5. Model Provider 与 Agent Runtime

稳健架构应该把 provider-specific client 与 Agent runtime 分开：

```text
Agent Runtime
     |
     v
Model Interface
  /   |    \
OpenAI Qwen Claude
```

为什么？

因为 provider API 会在这些地方不同：

- request objects；
- response objects；
- Tool-call representation；
- streaming events；
- error types；
- token accounting；
- model names；
- Structured Output feature。

如果 provider-specific code 散落在 runtime 各处，那么每次 provider API 变化都可能变成一次 Agent runtime 大手术。

更好的方式是 adapter：

```python
class Model:
    def generate(self, messages, tools):
        ...
```

每一个 provider adapter 把自己的 response 转换成统一 internal representation。

## 6. Context 是 Application Data

model 可能看到：

```text
system instructions
conversation history
retrieved documents
Tool outputs
current task state
user preferences
workflow metadata
```

这些数据来源并不因为最后都“进入 prompt”就变成同一种东西。

后续 Tiny-Agent 会进一步区分：

- current context；
- short-term / session state；
- long-term memory；
- retrieved evidence；
- runtime metadata。

## 7. 为什么这对 Agent 很重要

假设用户问：

> 东京现在天气怎么样？这个温度换成华氏度是多少？

LLM 本身并不可靠地拥有 live weather sensor，也不天然拥有 Python runtime。

application 可能需要：

1. 把用户问题发送给 model；
2. model 提议调用 weather Tool；
3. runtime 实际执行 Tool；
4. 把真实天气结果加入 Tool observation；
5. 再次调用 model；
6. 可能继续执行 calculator Tool；
7. 返回 final answer。

因此真正的执行单位已经不再是：

```text
one LLM request
```

而是：

> **由 runtime 控制的一系列 LLM request 与 environment interaction。**

## 8. 关键结论

- Agent 通常建立在普通 LLM API 上。
- model 只能消费 application runtime 当前提供的 context。
- message role 帮助组织这些 context。
- Tool observation 是新的 model input，不是模型自动知道的 hidden side effect。
- provider-specific API object 应被隔离在 interface / adapter 后面。
- runtime state 与 model inference 是两种不同责任。

## 复习题

1. 为什么 Agent runtime 不应该直接依赖某一个 provider 的 response class？
2. conversation history 到底属于 LLM，还是 application？
3. 为什么 Tool result 通常必须再次作为 model input 发送？
4. 哪些信息更应该保存在 runtime state，而不是假设 model 自己记得？
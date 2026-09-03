# Function Calling / Tool Calling

## 1. Function Calling 到底是什么？

Function Calling 经常被描述成：

> LLM 调用了一个函数。

这句话方便理解，但技术上并不准确。

Language model 通常**不会自己执行你的本地 Python function、访问 database 或发 HTTP request**。

真正发生的是：application 把当前可用 Tool 的 machine-readable description 提供给模型；模型可能输出一个 structured request，说明自己希望使用哪个 Tool、参数是什么。

概念上：

```text
Available tool:
get_weather(city: string)

User:
What is the weather in Tokyo?

Model output:
ToolCall(
    name="get_weather",
    arguments={"city": "Tokyo"}
)
```

接下来由 **application runtime** 接收这个 proposal，并决定是否真正执行。

## 2. Tool 的四个层次

很多教程会把下面四件事混在一起。最好从一开始就拆开。

### 2.1 Tool Name

```text
get_weather
```

name 是 model-facing interface 的一部分。

### 2.2 Tool Description

```text
Get the current weather for a city.
```

description 很重要，因为 Tool selection 本身也是一个语言理解问题。

描述含糊、重叠，会直接提高选错 Tool 的概率。

### 2.3 Argument Schema

```json
{
  "type": "object",
  "properties": {
    "city": {"type": "string"}
  },
  "required": ["city"]
}
```

schema 定义的是**模型可以提出的 action shape**。

### 2.4 Executable Handler

```python
def get_weather(city: str) -> str:
    ...
```

真正 function implementation 属于 application / runtime。

模型不需要看到 Python source code，也可以提出 `get_weather` ToolCall。

## 3. Tool Schema 与 Executable Function 是两个对象

必须记住这条分层：

```text
             MODEL SIDE
                |
                v
     name + description + schema
                |
          proposes action
                |
                v
             RUNTIME
                |
                v
        executable handler
```

为什么必须分开？

因为同一个逻辑 Tool，可以由不同 execution mechanism 实现：

- local Python function；
- HTTP API；
- database driver；
- remote worker；
- MCP server；
- sandboxed execution environment。

model-facing contract 可以保持稳定，而底层 execution mechanism 随部署变化。

## 4. 一次完整 Function-Calling Turn

典型流程：

```text
1. Application 把 user message + Tool schemas 发给 model。
2. Model 提议一个 ToolCall。
3. Runtime 验证 Tool 与 arguments。
4. Runtime 真正执行 Tool。
5. Runtime 把结果转换成 Tool observation。
6. Application 把 observation 放回下一次 model context。
7. Model 提出下一步 decision 或 final answer。
```

第 6 步尤其关键。

Python process 中某个 function 已经执行，并不意味着 model 自动知道结果。

Tool result 必须进入后续 model context。

## 5. 为什么 Tool Result 必须返回给 Model

假设 model 提议：

```text
calculator(a=23, b=17)
```

runtime 得到真实结果：

```text
391
```

如果 application 不把它发回模型，模型不能可靠地继续依据真实 computation result 做推理。

完整 interaction：

```text
User: calculate 23 * 17
Assistant: tool_call calculator(...)
Tool: 391
Assistant: 23 * 17 = 391
```

这里第一次出现 Agent 中非常核心的 feedback loop：

```text
proposal -> action -> observation -> next proposal
```

## 6. 多次 Tool Call

一个任务可能需要多个 external action：

```text
User
  |
  v
Model -> weather("Tokyo")
  ^            |
  |            v
  +------ 31 C observation
  |
  +-> calculator(celsius_to_fahrenheit)
               |
               v
             87.8 F
               |
               v
             Model
               |
               v
          Final answer
```

此时 application 已经不再处理“一次孤立 function call”，而是在管理 iterative tool-use process。

这就是 Function Calling 到 Agent Loop 的桥梁。

## 7. Tool Selection 是 Model Decision；Execution 是 Runtime Decision

这句话必须记牢：

> **LLM proposes；runtime executes。**

runtime 对下面这些事情保持最终 authority：

- Tool 是否存在；
- caller 是否有 permission；
- arguments 是否 valid；
- 是否需要 approval；
- 当前 environment 是否允许执行；
- timeout；
- retry；
- rate limit；
- logging；
- sandboxing。

所以 model-generated ToolCall 只是一个 **proposal**，不是不可拒绝的命令。

## 8. ToolCall Validation

永远不要假设 generated arguments 一定正确。

可能出现：

```text
Unknown Tool
Missing required argument
Wrong argument type
Invalid enum value
Unsafe path
Out-of-range number
Unauthorized operation
```

robust runtime 在 execution 前必须验证。

后续 Tiny-Agent 会进一步引入：

- explicit error classes；
- permissions；
- retry；
- approval gates；
- sandbox concepts。

## 9. Tool Error 也可以成为 Observation

Tool fail 时，最简单的方法是让整个 program crash。

更 Agent-friendly 的方式，通常是把**可恢复的 operational failure**转换成 observation：

```text
ToolError: city must be a non-empty string
```

model 随后可以：

- 修复 argument；
- 选择另一个 Tool；
- 向用户补问缺失信息；
- 说明 operation failed。

并不是所有 exception 都应该让模型自己恢复；Stage 07 会进一步区分 safe/typed failure。

这里先理解：environment failure 是 Agent 必须面对的一部分。

## 10. Function Calling 还不是 Production Agent

最小 Tool loop 提供：

```text
model -> action -> observation -> model
```

production Agent 还必须回答：

- loop 什么时候停止？
- 最多允许多少 step？
- state 怎么表示？
- error 如何分类？
- 怎么 persist / resume？
- 哪些 action 需要 approval？
- 如何 trace decision？
- 如何 evaluate success？
- 如何限制 cost / latency？

Stage 01 会开始建立第一个 explicit Agent runtime abstraction。

## 11. Function Calling vs Structured Output

| 概念 | 主要目的 |
|---|---|
| Natural-language output | 与人沟通 |
| Structured output | 返回 machine-readable data |
| Function / Tool calling | 提议 external action |

ToolCall 通常是 structured 的，但 structured output 并不都代表 ToolCall。

## 12. 关键结论

- model 通常不会直接执行你的 Python function。
- model 看到 Tool interface；runtime 拥有实现。
- Tool description / schema 是 model-facing contract。
- generated arguments 必须 validate。
- Tool result 必须作为 observation 返回给 model。
- 多轮 Tool use 自然发展成 Agent loop。
- Tool execution 是 runtime 控制的 security / reliability boundary。

## 复习题

1. 模型“调用 Tool”时，实际上生成了什么？
2. 为什么 Tool handler 与 Tool schema 不是同一个东西？
3. dangerous ToolCall 最终是否执行，由谁决定？
4. 为什么 Tool result 还要在后续 message 中返回给 model？
5. 当 ToolCall 开始反复发生时，runtime 新增了哪些工程问题？
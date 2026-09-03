# 03 — 模型不能“调用 Python”：真正的 Tool Calling 是什么

> Language: [English](03-function-calling.md) | 简体中文

上一章我们解决了一个问题：让模型把结果按程序需要的结构交回来。

现在旅行助手已经能够识别：

```json
{
  "city": "东京",
  "needs_weather": true
}
```

但这仍然只是“知道应该查天气”。

真实天气在模型外部。它可能来自天气 API、数据库、MCP Server，或者我们自己的 Python 函数。

于是问题变成：

> **模型怎样使用它本来没有的能力？**

很多资料会把答案简写成：

> “LLM 调用了一个函数。”

这句话方便，但很容易让初学者形成错误的系统模型。

更准确的说法是：

> **模型生成一个结构化 ToolCall；应用 Runtime 校验并执行真实 Tool，再把执行结果交回模型。**

这一章如果真正理解了，Stage 01 的 Agent loop 基本就已经看见一半了。

---

## 1. 先把最容易误解的一句话改掉

假设你的 Python 里有：

```python
def get_weather(city: str) -> dict:
    ...
```

模型不会因为这个函数存在，就自动获得它。

模型也不会神秘地“跳进你的 Python 进程”执行：

```python
get_weather("东京")
```

模型真正看到的是应用发送给它的一份 **Tool 描述**。

例如：

```python
TOOLS = [
    {
        "type": "function",
        "name": "get_weather",
        "description": "查询指定城市的天气。",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"}
            },
            "required": ["city"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]
```

模型根据名字、描述和参数 Schema，可能输出：

```text
function_call
name = "get_weather"
arguments = {"city": "东京"}
```

到这里为止，**真实天气函数还没有执行。**

这只是模型提出：

> “我认为下一步应该使用 `get_weather`，参数是东京。”

真正的执行仍然在你的 Python 程序里。

---

## 2. 一个 Tool 实际上有两个世界

这是本章最值得画出来的一张图。

```text
              模型看到的世界
┌─────────────────────────────────┐
│ name: get_weather               │
│ description: 查询城市天气       │
│ parameters: {city: string}      │
└─────────────────────────────────┘
                 │
                 │ 模型提出 ToolCall
                 ▼
              Runtime 边界
┌─────────────────────────────────┐
│ Tool 是否存在？                 │
│ 参数是否合法？                  │
│ 当前用户有权限吗？              │
│ 是否需要审批？                  │
└─────────────────────────────────┘
                 │
                 │ 允许后才执行
                 ▼
              真实执行世界
┌─────────────────────────────────┐
│ def get_weather(city):          │
│     调 API / 数据库 / 本地代码   │
└─────────────────────────────────┘
```

所以请牢牢记住：

```text
Tool schema
!=
Tool handler
```

Tool schema 是模型能看到的“接口说明书”。

Tool handler 是 Runtime 真正能执行的代码。

同一个 Tool schema 后面甚至可以换实现：

```text
本地 Python
HTTP API
数据库查询
远程 Worker
MCP Server
Sandbox
```

只要接口契约不变，模型不需要知道后面换了什么基础设施。

---

## 3. 先看一次完整的 OpenAI Tool Calling

下面这个例子故意不用 LangChain、LangGraph 或 Agents SDK。

我们只使用 OpenAI Responses API，加两个本地 Tool：

```text
get_weather(city)
celsius_to_fahrenheit(temperature_c)
```

天气数据是教学用的本地模拟值，这样你能把注意力放在 Tool loop，而不是第三方天气 API 的注册和鉴权上。

```python
import json
from openai import OpenAI

client = OpenAI()

TOOLS = [
    {
        "type": "function",
        "name": "get_weather",
        "description": "获取课程示例中的城市天气数据。",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"}
            },
            "required": ["city"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "celsius_to_fahrenheit",
        "description": "把摄氏温度转换成华氏温度。",
        "parameters": {
            "type": "object",
            "properties": {
                "temperature_c": {"type": "number"}
            },
            "required": ["temperature_c"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def get_weather(city: str) -> dict:
    # 教学用固定数据，不是真实实时天气。
    if city not in {"东京", "Tokyo"}:
        raise ValueError("这个课程示例只准备了东京数据")
    return {"city": "东京", "temperature_c": 18.0}


def celsius_to_fahrenheit(temperature_c: float) -> dict:
    value = temperature_c * 9 / 5 + 32
    return {"temperature_f": round(value, 1)}


def execute_tool(name: str, arguments: dict) -> dict:
    if name == "get_weather":
        return get_weather(**arguments)
    if name == "celsius_to_fahrenheit":
        return celsius_to_fahrenheit(**arguments)
    raise ValueError(f"未知 Tool: {name}")


instructions = (
    "你是旅行助手。"
    "天气和温度换算必须使用提供的 Tool，不要自己猜。"
    "课程中的天气数据是模拟数据，请明确告诉用户这一点。"
)

response = client.responses.create(
    model="gpt-5.6-luna",
    instructions=instructions,
    input="东京示例天气是多少摄氏度？再换算成华氏度。",
    tools=TOOLS,
    parallel_tool_calls=False,
)

for step in range(1, 6):
    calls = [item for item in response.output if item.type == "function_call"]

    if not calls:
        print("final:", response.output_text)
        break

    call = calls[0]
    arguments = json.loads(call.arguments)
    print(f"step {step}: model -> {call.name}({arguments})")

    result = execute_tool(call.name, arguments)
    print(f"step {step}: tool  -> {result}")

    response = client.responses.create(
        model="gpt-5.6-luna",
        instructions=instructions,
        previous_response_id=response.id,
        tools=TOOLS,
        parallel_tool_calls=False,
        input=[
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result, ensure_ascii=False),
            }
        ],
    )
else:
    raise RuntimeError("Tool loop 超过最大步骤数")
```

完整可运行版本：

[`../code/minimal_tool_loop.py`](../code/minimal_tool_loop.py)

### 预期输出

实际模型措辞和 ToolCall 顺序可能略有变化。合理的一次运行大概是：

```text
step 1: model -> get_weather({'city': '东京'})
step 1: tool  -> {'city': '东京', 'temperature_c': 18.0}
step 2: model -> celsius_to_fahrenheit({'temperature_c': 18.0})
step 2: tool  -> {'temperature_f': 64.4}
final: 课程示例中的东京天气是 18°C，换算后约为 64.4°F。这里的天气是模拟数据，不是实时天气。
```

现在不要只觉得“代码变长了”。真正重要的是看清模型和 Runtime 每一步分别做了什么。

---

## 4. 第一轮：模型没有执行任何 Python

第一次请求：

```python
response = client.responses.create(
    model="gpt-5.6-luna",
    input="东京示例天气是多少摄氏度？再换算成华氏度。",
    tools=TOOLS,
)
```

模型看到：

```text
用户的问题
+ instructions
+ Tool 的名字、描述、参数 Schema
```

模型的输出里可能出现：

```python
item.type == "function_call"
item.name == "get_weather"
item.arguments == '{"city":"东京"}'
```

注意：`arguments` 还是模型生成的数据。

这时程序应该把它当成：

```text
untrusted proposal
```

而不是：

```text
已经授权的命令
```

即使我们设置了 `strict=True`，它主要帮助参数符合 Schema；Runtime 仍然需要检查业务规则和权限。

---

## 5. `call_id` 为什么这么重要？

ToolCall 里除了 `name` 和 `arguments`，还有：

```python
call.call_id
```

它的作用是把：

```text
模型提出的这一次 ToolCall
```

和：

```text
你随后返回的这一次 Tool 结果
```

准确关联起来。

所以我们返回：

```python
{
    "type": "function_call_output",
    "call_id": call.call_id,
    "output": json.dumps(result),
}
```

这相当于告诉模型：

> “你刚才 ID 为 `call_xxx` 的那次调用，真实执行结果在这里。”

不要只按 Tool 名称关联结果。以后同一个模型可能连续调用同一个 Tool 多次，`call_id` 才是单次调用的身份。

---

## 6. 为什么 Tool 执行完还要再调用一次模型？

这是另一个高频误区。

假设 Python 已经执行：

```python
result = get_weather("东京")
```

得到：

```python
{"city": "东京", "temperature_c": 18.0}
```

模型不会因为“同一个 Python 进程里刚刚算出了这个变量”就自动知道结果。

模型和你的 Python 内存之间没有心灵感应。

所以必须明确地把结果送回下一轮：

```python
input=[
    {
        "type": "function_call_output",
        "call_id": call.call_id,
        "output": json.dumps(result),
    }
]
```

于是形成：

```text
Model
  ↓ ToolCall
Runtime
  ↓ execute
Environment / Python / API
  ↓ result
Runtime
  ↓ function_call_output
Model
```

这就是 Agent 中最基础的 **action → observation** 反馈闭环。

---

## 7. 为什么 `instructions` 和 `tools` 每轮都显式提供？

在示例的下一次调用中，我们仍然写了：

```python
instructions=instructions,
tools=TOOLS,
previous_response_id=response.id,
```

这不是多余代码，而是在培养一个重要习惯：

> **当前这一轮允许模型看到什么、遵守什么、使用什么能力，应由应用显式构造。**

不要把安全和控制策略建立在“上一轮应该还记得”上。

在更复杂 Runtime 中，这些内容会被封装成更好的抽象，但底层责任不会消失。

---

## 8. `strict=True` 为什么仍然不等于安全？

Tool schema：

```json
{
  "city": {"type": "string"}
}
```

可以保证参数是一个字符串。

但它不能回答：

```text
这个用户有权限查询吗？
这个 Tool 会不会产生副作用？
这个路径是否越权？
金额是否超过业务限制？
是否需要人类审批？
```

例如：

```text
delete_database(database="production")
```

即使 JSON Schema 100% 合法，也不代表应该执行。

因此必须区分：

```text
参数结构合法
!=
业务合法
!=
权限允许
!=
副作用安全
```

Stage 07 会把这些 Runtime policy 系统化，但边界从这里就应该建立正确。

---

## 9. Tool description 不是装饰文字

模型选择哪个 Tool，很大程度上依赖：

```text
Tool name
Tool description
参数说明
当前任务 Context
```

例如两个 Tool：

```text
search(query)
find(query)
```

描述都写成：

```text
Search something.
```

那就不要惊讶模型经常选错。

更好的描述应该告诉模型：

```text
这个 Tool 做什么
什么时候使用
返回什么
有什么重要限制
```

例如：

```text
search_papers:
搜索论文元数据，返回标题、作者、DOI 和摘要信息。
它不会返回论文全文，因此不要把元数据结果当成论文正文证据。
```

Tool interface 本身就是 Agent-Computer Interface 的一部分。Stage 01 会继续深入这个问题。

---

## 10. Tool error 应该怎样处理？

我们的教学函数可能抛出：

```python
ValueError("这个课程示例只准备了东京数据")
```

最简单的程序可以直接崩溃。

真正的 Agent Runtime 往往需要更细致地决定：

```text
这是可修复参数错误？
    -> 返回安全的 Tool failure observation

这是权限拒绝？
    -> 不允许模型通过重试绕过

这是内部异常？
    -> 不把敏感堆栈直接塞进模型 Context

这是暂时网络错误？
    -> 是否允许重试还要看操作是否 retry-safe
```

你现在不用实现全部内容，但要知道：**Tool failure 是 Runtime 设计的一部分，不只是 try/except 的语法问题。**

---

## 11. 从 Function Calling 到 Agent loop，只差什么？

我们已经拥有：

```text
model
  ↓ proposes action
runtime
  ↓ executes
observation
  ↓
model
```

这已经非常接近 ReAct loop。

但现在的代码仍然缺很多东西：

```text
明确的消息 / 状态类型
统一 ToolRegistry
参数 validation 层
step budget
cost budget
timeout
retry policy
权限
审批
持久化
trace
评价
```

这就是 Stage 01 为什么要出现。

Stage 01 并不是“换成一个更高级框架”。

它是在回答：

> **既然模型和 Tool 已经要反复交互，我们怎样把这段循环写成一个清晰、可测试、可限制的 Runtime？**

---

## 12. 本章最重要的一条链路

请尝试不看文字，自己把它画出来：

```text
用户
 ↓
应用把 Tool schema 交给模型
 ↓
模型生成 function_call
 ↓
Runtime 读取 name + arguments
 ↓
Runtime 校验 / 授权
 ↓
Python / API 真正执行
 ↓
Runtime 得到 result
 ↓
以 function_call_output + call_id 返回
 ↓
模型看到 observation
 ↓
继续调用 Tool 或给最终答案
```

如果你能准确解释每一条箭头是谁负责的，那么你已经理解了 Tool Calling 的核心。

请不要再说：

> “模型执行了 Python 函数。”

更准确的说法是：

> **模型提出 ToolCall，Runtime 执行 Tool。**

这句话会一直保护你不把“模型能力”和“应用权限”混在一起。

---

## 官方参考

- OpenAI Responses API：<https://developers.openai.com/api/reference/resources/responses>
- OpenAI Function Calling：<https://help.openai.com/en/articles/8555517-function-calling-in-the-openai-api>

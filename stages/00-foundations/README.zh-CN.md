# Stage 00：先别急着造 Agent——把一次模型调用讲明白

> Language: [English](README.md) | **简体中文**

很多 Agent 教程一上来就摆出框架、装饰器和一长串名词，像是刚学会拧螺丝，就有人递来一架波音飞机的维修手册。本章换一种顺序：先把最基本的零件看清楚。

我们从一次普通的大模型调用出发，依次解决三个问题：

1. Python 程序怎样向模型发出请求并读取响应？
2. 当结果要交给程序而不是人阅读时，怎样得到稳定的数据结构？
3. 当任务需要查询数据或执行函数时，模型和应用程序分别负责什么？

读完本章，你会亲手完成一次完整的 **model → tool → model** 往返，并能准确解释本章最重要的边界：

> **模型负责生成提案，应用程序负责决定是否执行。**

本章所有完整代码都在 [`code/`](code/) 中，正文在概念第一次出现的位置给出与文件一致的完整代码。阅读时不需要在多个文档之间来回跳转。

---

## 1. 大模型在程序里到底是什么

先暂时忘掉“Agent”这个词。对 Python 程序来说，大模型首先是一个远程计算服务：程序提交输入，服务返回响应。

```text
用户的问题
    ↓
Python 程序构造请求
    ↓
模型服务生成响应
    ↓
Python 程序读取响应
```

这条链里有两个行为主体：

- 模型服务会**生成内容**；
- 你的 Python 程序会**发请求、读结果、调用函数、修改数据**。

两者不能混为一谈。模型说“邮件已经发送”不代表邮件真的发出去了，正如导航软件说“前方左转”并不会替你转方向盘。它给出了下一步建议，真正的动作仍由外部系统完成。

### 1.1 准备运行环境

本章示例使用 Python 3.10 或更高版本，以及 OpenAI Python SDK。先在仓库根目录安装依赖：

```bash
python -m pip install -r stages/00-foundations/code/requirements.txt
```

依赖文件很短：

```text
openai>=2,<3
pydantic>=2.11,<3
```

然后设置两个环境变量。`OPENAI_MODEL` 应选择你项目中可用、并支持 Responses API、Structured Outputs 与 Function Calling 的模型：

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-id"
```

不要把 API Key 写进代码或提交到 Git。Windows PowerShell 可以这样设置：

```powershell
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_MODEL="your-model-id"
```

示例没有偷偷写死一个“默认模型”。模型名称会变化，不同项目可用的模型也可能不同；显式配置能让报错发生在程序启动时，而不是在读者猜测“为什么教程里的神秘型号用不了”之后。

### 1.2 第一次调用

运行：

```bash
python stages/00-foundations/code/first_llm_call.py
```

完整代码如下：

```python
from __future__ import annotations

import os
from typing import Any


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Set {name} before running this example.")
    return value.strip()


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI SDK is not installed. Run:\n"
            "python -m pip install -r "
            "stages/00-foundations/code/requirements.txt"
        ) from exc

    required_env("OPENAI_API_KEY")
    return OpenAI()


def main() -> None:
    client = create_client()
    model = required_env("OPENAI_MODEL")

    response = client.responses.create(
        model=model,
        instructions=(
            "You are a patient programming teacher. Explain the idea accurately, "
            "use one concrete analogy, and avoid unexplained jargon."
        ),
        input=(
            "In no more than 120 words, explain why a language model response is "
            "a proposal produced by a model rather than an action performed by my "
            "Python program."
        ),
    )

    if response.status != "completed":
        raise RuntimeError(f"The response did not complete: {response.status}")
    if not response.output_text.strip():
        raise RuntimeError("The response completed without text output.")

    print("=== response metadata ===")
    print("response_id:", response.id)
    print("model:", response.model)

    print("\n=== model output ===")
    print(response.output_text)

    usage = response.usage
    if usage is not None:
        print("\n=== token usage ===")
        print("input_tokens:", usage.input_tokens)
        print("output_tokens:", usage.output_tokens)
        print("total_tokens:", usage.total_tokens)


if __name__ == "__main__":
    main()
```

这段程序只有一条主线：创建客户端、提交请求、检查状态、读取结果。

```python
response = client.responses.create(...)
```

返回的 `response` 不是一段裸字符串，而是一个响应对象。文本只是其中一部分；对象还带有响应编号、实际使用的模型、状态和 token 用量等信息。`response.output_text` 是读取最终文本的便捷入口，不代表整个协议只有文本。

程序还明确检查了：

```python
if response.status != "completed":
    ...
if not response.output_text.strip():
    ...
```

“请求没有抛异常”与“得到了可用答案”不是同一件事。把检查写出来，能避免后面的代码抱着空字符串继续狂奔，最后在十公里外摔倒。

### 1.3 `instructions` 和 `input` 为什么分开

示例中：

```python
instructions="You are a patient programming teacher..."
input="In no more than 120 words..."
```

两者承担不同职责：

```text
instructions  应用希望模型遵守的行为约束
input         当前这一次真正要处理的任务
```

将来源不同的内容分开，比把所有文字拼成一条巨型字符串更容易维护。程序以后需要替换任务时，不必同时改动行为约束；需要调整输出风格时，也不必重写用户问题。

到这里，我们完成的是一次普通模型调用。人可以直接阅读自然语言，但程序很快会提出一个更挑剔的问题：**我怎样稳定地读取这些内容？**

---

## 2. 自然语言适合交流，不适合充当脆弱的接口

假设程序要把用户请求整理成任务卡。模型返回下面这段话，人一眼就能看懂：

```text
This looks fairly important. We probably need current weather data first.
```

程序却很为难。你当然可以写：

```python
if "important" in answer.lower():
    priority = "high"
```

但这相当于拿关键词猜协议。模型把 `important` 换成 `urgent`，程序就突然失忆。

程序更希望得到这样的对象：

```json
{
  "goal": "compare current weather in Tokyo and Paris",
  "priority": "medium",
  "needs_external_data": true,
  "reason": "current weather must be retrieved"
}
```

这就是 **Structured Output（结构化输出）** 要解决的问题：让模型输出满足一个机器可检查的数据结构。

### 2.1 用 Pydantic 写出数据契约

运行：

```bash
python stages/00-foundations/code/structured_output.py
```

完整代码：

```python
from __future__ import annotations

import os
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    priority: Priority
    needs_external_data: bool
    reason: str = Field(min_length=1)


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Set {name} before running this example.")
    return value.strip()


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI SDK is not installed. Run:\n"
            "python -m pip install -r "
            "stages/00-foundations/code/requirements.txt"
        ) from exc

    required_env("OPENAI_API_KEY")
    return OpenAI()


def main() -> None:
    client = create_client()
    model = required_env("OPENAI_MODEL")

    response = client.responses.parse(
        model=model,
        instructions=(
            "Turn the request into a task card. Describe only the request itself; "
            "do not guess the weather or pretend that external data was retrieved."
        ),
        input=(
            "Compare the current weather in Tokyo and Paris and tell me which city "
            "is warmer."
        ),
        text_format=TaskCard,
    )

    if response.status != "completed":
        raise RuntimeError(f"The response did not complete: {response.status}")

    task = response.output_parsed
    if task is None:
        raise RuntimeError("The response contained no parsed TaskCard.")

    print(task.model_dump_json(indent=2))
    print(
        "\nThe shape is validated. The claims still need to be checked against "
        "real data."
    )


if __name__ == "__main__":
    main()
```

这里先用 Pydantic 定义程序真正需要的数据：

```python
class TaskCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    priority: Priority
    needs_external_data: bool
    reason: str = Field(min_length=1)
```

这不是“请尽量返回 JSON”的礼貌请求，而是一份明确契约：

- `priority` 只能取 `low`、`medium`、`high`；
- 必要字段不能缺失；
- `goal` 和 `reason` 不能为空；
- `extra="forbid"` 禁止模型随手塞入契约之外的字段。

随后，SDK 根据这个模型解析响应：

```python
response = client.responses.parse(
    ...,
    text_format=TaskCard,
)
task = response.output_parsed
```

拿到的 `task` 已经是 `TaskCard`，程序可以直接写 `task.priority`，而不必从一段自然语言里考古。

### 2.2 结构正确，不等于内容正确

这是本节最重要的边界：

```text
字段齐全、类型正确
        ≠
判断真实、结论可靠
```

结构化输出可以保证 `needs_external_data` 是布尔值，却不能保证模型对它的判断一定正确。模型也可能生成一个格式无可挑剔、内容一本正经地错了的对象——西装穿得很整齐，不代表简历没有注水。

因此，Structured Output 解决的是：

> **程序怎样可靠地读取模型输出。**

它没有解决：

> **模型怎样获得它本来不知道的外部事实。**

而“比较当前天气”恰好需要外部数据。接下来，我们让模型学会请求一个由 Python 提供的能力。

---

## 3. Tool Calling：模型提议调用，程序真正执行

模型本身不会自动运行你的 Python 函数。要让它使用外部能力，应用需要准备两样东西：

```text
给模型看的工具说明
├── name
├── description
└── parameters（JSON Schema）

给程序执行的函数
└── Python handler
```

工具说明告诉模型“有什么能力、何时使用、参数长什么样”；Python 函数才负责真正查询或计算。

可以把模型想成隔着玻璃办公的聪明同事。它能递出一张申请单：

```json
{
  "name": "get_teaching_weather",
  "arguments": {"city": "Tokyo"}
}
```

但玻璃门的钥匙仍在应用程序手里。程序要检查工具名、解析参数、调用函数，再把结果送回去。

### 3.1 为什么使用“教学天气”而不使用实时天气

本章使用固定数据：

```python
TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}
```

它不是天气预报。固定数据能让每位读者看到相同结果，把注意力放在 Tool Calling 的控制流程上，而不是先处理网络、认证和第三方接口波动。

### 3.2 完成一次 model → tool → model 往返

运行：

```bash
python stages/00-foundations/code/tool_calling.py
```

完整代码：

```python
from __future__ import annotations

import json
import os
from typing import Any


TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}

WEATHER_TOOL = {
    "type": "function",
    "name": "get_teaching_weather",
    "description": (
        "Return the deterministic teaching weather record for Tokyo or Paris. "
        "Use this function whenever the user asks about those teaching records."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "enum": sorted(TEACHING_WEATHER),
                "description": "The city whose teaching record should be read.",
            }
        },
        "required": ["city"],
        "additionalProperties": False,
    },
    "strict": True,
}


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Set {name} before running this example.")
    return value.strip()


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI SDK is not installed. Run:\n"
            "python -m pip install -r "
            "stages/00-foundations/code/requirements.txt"
        ) from exc

    required_env("OPENAI_API_KEY")
    return OpenAI()


def get_teaching_weather(city: str) -> dict[str, Any]:
    try:
        record = TEACHING_WEATHER[city]
    except KeyError as exc:
        raise ValueError(f"Unsupported city: {city}") from exc
    return {"city": city, **record}


def parse_arguments(raw_arguments: str) -> dict[str, Any]:
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Tool arguments are not valid JSON: {raw_arguments!r}") from exc
    if not isinstance(arguments, dict):
        raise RuntimeError("Tool arguments must decode to a JSON object.")
    return arguments


def validate_weather_arguments(arguments: dict[str, Any]) -> str:
    if set(arguments) != {"city"}:
        raise RuntimeError("get_teaching_weather expects exactly one field: city")
    city = arguments["city"]
    if not isinstance(city, str):
        raise RuntimeError("The city argument must be a string.")
    if city not in TEACHING_WEATHER:
        raise RuntimeError(f"Unsupported city: {city}")
    return city


def main() -> None:
    client = create_client()
    model = required_env("OPENAI_MODEL")

    first = client.responses.create(
        model=model,
        instructions=(
            "Use the supplied function to read teaching weather records. A function "
            "call only requests an action; never claim a result before the function "
            "output is returned."
        ),
        input=(
            "Read Tokyo's deterministic teaching weather record and report the "
            "temperature and condition."
        ),
        tools=[WEATHER_TOOL],
        tool_choice={"type": "function", "name": "get_teaching_weather"},
        parallel_tool_calls=False,
    )

    if first.status != "completed":
        raise RuntimeError(f"The first response did not complete: {first.status}")

    calls = [item for item in first.output if item.type == "function_call"]
    if len(calls) != 1:
        raise RuntimeError(f"Expected exactly one function call, received {len(calls)}.")

    call = calls[0]
    if call.name != "get_teaching_weather":
        raise RuntimeError(f"The model requested an unknown function: {call.name}")

    arguments = parse_arguments(call.arguments)
    city = validate_weather_arguments(arguments)
    result = get_teaching_weather(city)

    print("=== model proposed ===")
    print(call.name, arguments)
    print("\n=== application executed ===")
    print(result)

    final = client.responses.create(
        model=model,
        instructions=(
            "Answer only from the returned function output. Make clear that this is "
            "a deterministic teaching record, not live weather."
        ),
        previous_response_id=first.id,
        input=[
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result, ensure_ascii=False),
            }
        ],
        tools=[WEATHER_TOOL],
        tool_choice="none",
    )

    if final.status != "completed":
        raise RuntimeError(f"The final response did not complete: {final.status}")
    if not final.output_text.strip():
        raise RuntimeError("The final response completed without text output.")

    print("\n=== final answer ===")
    print(final.output_text)


if __name__ == "__main__":
    main()
```

不要把这段程序当成一坨一百多行的代码。按时间顺序看，它只有五步。

#### 第一步：把工具说明交给模型

```python
first = client.responses.create(
    ...,
    tools=[WEATHER_TOOL],
    tool_choice={"type": "function", "name": "get_teaching_weather"},
    parallel_tool_calls=False,
)
```

`tool_choice` 在这个教学例子中强制模型请求指定函数，`parallel_tool_calls=False` 将本轮限制为单个调用。这样我们可以稳定观察一条最小路径，而不是把“模型这次会不会主动调用”混进控制流程实验。

此时模型返回的是 Function Call（函数调用）。**函数还没有执行。**

#### 第二步：验证模型请求的工具

```python
if call.name != "get_teaching_weather":
    raise RuntimeError(...)
```

不要把模型返回的字符串直接交给 `globals()` 或动态执行。模型可以提议一个名称，但程序只允许调用自己明确注册和检查过的函数。

#### 第三步：解析参数并由 Python 执行

```python
arguments = parse_arguments(call.arguments)
result = get_teaching_weather(**arguments)
```

真正读取 `TEACHING_WEATHER` 的是 Python 函数。模型没有越过边界，也没有神秘地“接管”解释器。

#### 第四步：把结果与原调用关联起来

```python
{
    "type": "function_call_output",
    "call_id": call.call_id,
    "output": json.dumps(result, ensure_ascii=False),
}
```

`call_id` 不是装饰。它说明这份结果属于哪一次请求。即使两个调用使用同一个工具名，它们仍可能是不同动作：

```text
call_A -> get_teaching_weather(Tokyo)
call_B -> get_teaching_weather(Paris)
```

只看工具名无法区分二者，`call_id` 保留了这条因果关系。

#### 第五步：让模型基于真实结果回答

```python
final = client.responses.create(
    previous_response_id=first.id,
    input=[function_call_output],
    tools=[WEATHER_TOOL],
    tool_choice="none",
)
```

`previous_response_id` 把第二次响应接在第一次响应之后；新的输入只包含程序刚刚产生的工具结果。第二轮使用 `tool_choice="none"`，明确要求模型停止请求工具并生成文字。

完整时间线是：

```text
用户提出任务
    ↓
模型生成 Function Call（提案）
    ↓
Python 检查名称与参数
    ↓
Python 执行函数（动作）
    ↓
程序生成 Function Call Output（观察结果）
    ↓
模型根据观察结果生成最终文字
```

这就是本章真正要建立的心智模型。

---

## 4. 三个容易混淆的概念

### 4.1 Structured Output 不是 Tool Calling

两者都使用结构化数据，但目的不同：

```text
Structured Output
    模型返回一个供程序读取的数据对象

Tool Calling
    模型返回一个希望程序执行的动作请求
```

一张填写规范的申请表仍然只是申请表，不会自己跑去仓库取货。

### 4.2 Tool Calling 不是 Tool Execution

```text
模型返回 Tool Call
        ≠
Python 函数已经运行
```

只有当应用程序完成检查并显式调用处理函数，动作才真正发生。这个边界决定了谁拥有控制权。

### 4.3 模型输出不是系统事实

无论是自然语言、结构化对象还是 Tool Call，它们首先都是模型生成的内容。程序需要根据用途进行解析、验证和执行，不能因为内容“看起来很像协议”就自动授予它事实地位或执行能力。

---

## 5. 我们现在完成了什么

本章没有造出一个可以无限自主工作的 Agent，也没有必要假装已经造出来。

我们完成的是一个边界清楚的最小闭环：

```text
一次模型调用
    ↓
机器可读的结构化输出
    ↓
模型提出工具调用
    ↓
应用执行并返回结果
    ↓
模型基于结果回答
```

当前 `tool_calling.py` 明确写死了“先调用一次工具，再请求一次最终回答”。如果任务需要零次、两次或更多次工具调用，继续复制 `first`、`second`、`third` 很快会把程序写成报站员。下一章会从这个实际问题出发，把重复的控制流程整理成一个小型 Runtime。

➡️ [Stage 01：让模型循环工作——亲手写一个最小 Agent Runtime](../01-react-runtime/README.zh-CN.md)

---

## 6. 动手练习

练习的目标不是背术语，而是通过修改程序观察边界。

### 练习一：让结构约束与事实判断打架

给 `TaskCard` 增加一个 `confidence: float` 字段，并约束在 0 到 1 之间。观察结构校验能保证什么，再回答：`confidence=0.99` 是否证明模型判断正确？

### 练习二：允许查询巴黎

修改 `tool_calling.py` 的用户问题，让模型读取巴黎。不要改 handler，只观察参数如何沿着函数调用、Python 函数和函数调用结果传播。

### 练习三：故意制造未知工具

把允许的工具名检查临时改错，观察程序在哪一步停止。然后思考：为什么“模型知道一个名字”不等于“程序里存在这个能力”？

### 练习四：去掉 `call_id`

先在纸上画两次同名调用，再尝试说明每份结果属于谁。这个实验通常只需要三十秒，就能治好“这个字段看起来可以省略”的冲动。

---

## 7. 本章检查表

读完后，你应该能够不用背定义，直接解释下面这些问题：

- `response.output_text` 与完整 `response` 对象有什么区别？
- Structured Output 保证了什么，又没有保证什么？
- Tool 的参数结构和 Python 处理函数分别给谁使用？
- 为什么函数调用只是提案？
- `call_id` 和 `previous_response_id` 各自关联什么？
- 为什么本章使用固定教学数据而不是实时天气？

本章目录：

```text
stages/00-foundations/
├── README.zh-CN.md
├── README.md
└── code/
    ├── first_llm_call.py
    ├── structured_output.py
    ├── tool_calling.py
    └── requirements.txt
```

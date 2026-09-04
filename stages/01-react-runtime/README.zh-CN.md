# Stage 01：让模型循环工作——亲手写一个最小 Agent Runtime

> Language: [English](README.md) | **简体中文**

上一章的 `tool_calling.py` 能完成一次工具往返，但它把步骤写死了：第一次请求工具，第二次要求回答。只要任务变成“先查教学天气，再把摄氏度换成华氏度”，代码就会自然长成 `first`、`second`、`third`。再多几步，变量名就要开始按辈分排座次。

这一章解决的不是“怎样再调用一个工具”，而是更根本的问题：

> **怎样把不确定次数的模型决策和工具执行，组织成一个有边界、可检查、可替换的循环？**

我们会从零写出一个小型 Agent Runtime。它不依赖 Agent 框架，离线即可运行和测试；最后再用一个 Adapter 接入真实的 OpenAI Responses API。

本章完整教学内容集中在这个 README 中，完整代码只放在 [`code/`](code/) 中，并在正文对应位置原样给出。

---

## 1. 固定脚本为什么不够用

先看上一章的控制流程：

```python
first = call_model(user_request)
call = read_function_call(first)
result = execute(call)
final = call_model(result)
return final.output_text
```

这段代码暗中假设了三件事：

```text
模型一定先调用工具
工具一定只调用一次
第二轮一定直接给最终答案
```

但真实决策路径可能是：

```text
直接回答
```

也可能是：

```text
查询天气
→ 转换温度
→ 回答
```

还可能是：

```text
查询天气
→ 发现参数不够
→ 改用另一个参数再次查询
→ 回答
```

应用程序不能提前给每一轮起名。它需要一个统一循环：每次让模型给出下一步，如果是工具请求就执行并记录结果，如果是最终文字就结束。

最小控制流可以写成：

```python
for step in range(max_steps):
    turn = model.generate(messages, tools)

    if turn.final_text is not None:
        return turn.final_text

    for call in turn.tool_calls:
        observation = execute(call)
        messages.append(observation)

raise MaxStepsExceeded
```

这一小段代码就是本章要逐步长出来的 Runtime 核心。

---

## 2. ReAct：重点是可观察的循环，不是展示隐藏思维

**ReAct** 来自 Reasoning and Acting。对工程实现而言，最有用的理解是：模型根据当前信息决定下一步动作，环境执行动作并返回观察结果（Observation），模型再根据新信息继续决定。

```text
Decision
   ↓
Action / Tool Call
   ↓
Application executes
   ↓
Observation
   ↓
Decision
   ↓
...
```

这里不要求程序读取或打印模型的私有推理过程。Runtime 真正需要处理的是可观察、可记录的协议对象：

- 模型请求了哪个工具；
- 参数是什么；
- 程序执行后返回了什么；
- 模型何时给出最终答案。

把 ReAct 简化成不断输出 `Thought:`、`Action:` 字符串，会让控制逻辑依赖自然语言格式。模型少打一个冒号，程序就像听错口令的仪仗队。我们会直接使用结构化的 Tool Call。

### 2.1 本章的任务轨迹

为了观察多轮循环，我们继续使用固定教学数据，并增加一个温度换算工具：

```text
用户：读取东京的教学天气，并换算成华氏度

模型请求 get_teaching_weather(city="Tokyo")
    ↓
程序返回 18.0°C、cloudy
    ↓
模型请求 celsius_to_fahrenheit(temperature_c=18.0)
    ↓
程序返回 64.4°F
    ↓
模型生成最终答案
```

真实模型可能选择不同路径。为了先验证 Runtime 本身，我们会先使用行为完全确定的 `ScriptedWeatherModel`。控制器考试时先不要把随机数也请进考场。

---

## 3. 先划分职责：Model、Tool、Runtime

一个最小系统里有三个清晰角色：

```text
                 ┌──────────────┐
                 │    Model     │
                 │ decide next  │
                 └──────┬───────┘
                        │ ModelTurn
                        ▼
┌────────────┐   ┌──────────────┐   ┌────────────┐
│ 运行记录   │◀─▶│   Runtime    │──▶│    Tool    │
└────────────┘   │  控制循环  │   │ 处理函数   │
                 └──────────────┘   └─────┬──────┘
                                         │
                                         ▼
                                    观察结果
```

**Model** 根据当前消息和工具说明，返回一次决策。它可以给出最终文字，也可以提出一个或多个 Tool Call。

**Tool** 把模型可见的接口说明与应用内部的 Python 处理函数（handler）连接起来。它还要在执行前验证参数。

**Runtime** 拥有控制流。它调用模型、查找工具、执行处理函数、记录观察结果，并在满足停止条件时结束。

核心边界可以浓缩成一句话：

> **模型决定想做什么，Runtime 决定这次运行实际上怎样推进。**

---

## 4. 不让 Runtime 认识某一家模型服务商的字段

如果核心循环直接写：

```python
for item in response.output:
    if item.type == "function_call":
        ...
```

它就认识了某个模型服务商的响应格式。以后响应字段变化，或者更换模型服务，控制循环也要跟着动手术。

Runtime 实际只需要很少的信息：

```text
ToolCall
├── call_id
├── name
└── arguments

ModelTurn
├── final_text
└── tool_calls
```

因此我们先定义内部协议，再让 Adapter 负责翻译外部格式：

```text
模型服务响应
       ↓
     Adapter
       ↓
ModelTurn / ToolCall
       ↓
     Runtime
```

这样，Runtime 测试不需要网络，也不需要知道 模型服务商把函数调用放在哪个字段里。

### 4.1 `ModelTurn` 为什么要求二选一

本章规定一次模型决策只有两个合法出口：

```text
final_text   结束本次运行
或
tool_calls   执行动作后继续
```

不能两个都没有，也不能同时出现。真实 API 可能允许更复杂的输出组合，但教学 Runtime 不必把所有外部复杂度原封不动搬进内部。

明确约束会让状态转移非常容易推理：

```text
ModelTurn(final_text=...)
        → END

ModelTurn(tool_calls=...)
        → ACT → OBSERVE → NEXT TURN
```

---

## 5. Tool 不只是函数，还包括输入契约

一个工具由四部分组成：

```python
@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: Callable[[Any], Any]
```

`name`、`description` 和参数结构给模型看；处理函数（`handler`）由应用程序调用。`arguments_model` 同时承担两个任务：

1. 生成可交给模型的 JSON Schema；
2. 在执行前重新验证模型返回的参数。

为什么还要在 Runtime 里验证？因为 Tool Call 可能来自网络响应，也可能来自保存的记录、测试数据或其他输入。即使上游声称已经严格约束，执行边界仍应检查自己真正接受的数据。

```text
上游尽量生成正确参数
        ≠
处理函数可以跳过输入验证
```

本章使用 Pydantic：

```python
class WeatherArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    city: Literal["Tokyo", "Paris"]
```

`extra="forbid"` 拒绝多余字段，`strict=True` 减少静默类型转换，`Literal` 将城市限制在教学数据实际支持的范围内。

---

## 6. 完整实现：离线可运行的 Runtime

安装本章依赖：

```bash
python -m pip install -r stages/01-react-runtime/code/requirements.txt
```

依赖文件：

```text
openai>=2,<3
pydantic>=2.11,<3
```

先运行离线示例：

```bash
python stages/01-react-runtime/code/runtime.py
```

预期会看到类似轨迹：

```text
[1] ACTION  get_teaching_weather({'city': 'Tokyo'})
[1] OBSERVE {"city": "Tokyo", "temperature_c": 18.0, "condition": "cloudy"}
[2] ACTION  celsius_to_fahrenheit({'temperature_c': 18.0})
[2] OBSERVE {"temperature_f": 64.4}
[3] FINAL   Tokyo's deterministic teaching record is 18.0°C (64.4°F), cloudy.
```

完整代码如下：

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError


class AgentRuntimeError(RuntimeError):
    """Base error for this chapter's runtime."""


class InvalidModelTurnError(AgentRuntimeError):
    pass


class UnknownToolError(AgentRuntimeError):
    pass


class ToolArgumentsError(AgentRuntimeError):
    pass


class ToolExecutionError(AgentRuntimeError):
    pass


class MaxStepsExceeded(AgentRuntimeError):
    pass


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.call_id, str) or not self.call_id.strip():
            raise ValueError("ToolCall.call_id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("ToolCall.name must be a non-empty string")
        if not isinstance(self.arguments, dict):
            raise ValueError("ToolCall.arguments must be a dictionary")


@dataclass(frozen=True)
class ModelTurn:
    final_text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.tool_calls, tuple) or not all(
            isinstance(call, ToolCall) for call in self.tool_calls
        ):
            raise InvalidModelTurnError(
                "tool_calls must be a tuple containing only ToolCall objects"
            )

        has_final = self.final_text is not None
        has_calls = bool(self.tool_calls)
        if has_final == has_calls:
            raise InvalidModelTurnError(
                "A model turn must contain exactly one of final_text or tool_calls"
            )
        if self.final_text is not None:
            if not isinstance(self.final_text, str) or not self.final_text.strip():
                raise InvalidModelTurnError("final_text must be a non-empty string")
        call_ids = [call.call_id for call in self.tool_calls]
        if len(call_ids) != len(set(call_ids)):
            raise InvalidModelTurnError("tool call IDs must be unique within a turn")


class Model(Protocol):
    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        """Return one provider-neutral model turn."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: Callable[[Any], Any]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Tool.name must be a non-empty string")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Tool.description must be a non-empty string")
        if not isinstance(self.arguments_model, type) or not issubclass(
            self.arguments_model, BaseModel
        ):
            raise TypeError("Tool.arguments_model must be a Pydantic BaseModel class")

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.arguments_model.model_json_schema(),
        }

    def invoke(self, raw_arguments: dict[str, Any]) -> Any:
        try:
            arguments = self.arguments_model.model_validate(raw_arguments)
        except ValidationError as exc:
            raise ToolArgumentsError(
                f"Arguments for tool {self.name!r} failed validation: {exc}"
            ) from exc

        try:
            return self.handler(arguments)
        except Exception as exc:
            raise ToolExecutionError(
                f"Tool {self.name!r} failed with {type(exc).__name__}"
            ) from exc


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, call: ToolCall) -> Any:
        tool = self._tools.get(call.name)
        if tool is None:
            raise UnknownToolError(f"Unknown tool: {call.name}")
        return tool.invoke(call.arguments)


@dataclass(frozen=True)
class RunResult:
    answer: str
    model_turns: int
    messages: tuple[dict[str, Any], ...]


class AgentRuntime:
    """A small synchronous decide-act-observe runtime."""

    def __init__(
        self,
        model: Model,
        tools: list[Tool],
        *,
        max_steps: int = 8,
        verbose: bool = True,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        self.model = model
        self.registry = ToolRegistry(tools)
        self.max_steps = max_steps
        self.verbose = verbose

    def run(self, user_input: str) -> RunResult:
        if not user_input.strip():
            raise ValueError("user_input must not be blank")

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_input}
        ]
        seen_call_ids: set[str] = set()

        for step in range(1, self.max_steps + 1):
            turn = self.model.generate(messages, self.registry.schemas())
            if not isinstance(turn, ModelTurn):
                raise InvalidModelTurnError(
                    "Model.generate() must return a ModelTurn"
                )

            if turn.final_text is not None:
                messages.append({"role": "assistant", "content": turn.final_text})
                if self.verbose:
                    print(f"[{step}] FINAL   {turn.final_text}")
                return RunResult(
                    answer=turn.final_text,
                    model_turns=step,
                    messages=tuple(messages),
                )

            repeated = [
                call.call_id for call in turn.tool_calls if call.call_id in seen_call_ids
            ]
            if repeated:
                raise InvalidModelTurnError(
                    f"Tool call IDs must be unique within a run: {repeated}"
                )
            seen_call_ids.update(call.call_id for call in turn.tool_calls)

            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [asdict(call) for call in turn.tool_calls],
                }
            )

            for call in turn.tool_calls:
                if self.verbose:
                    print(f"[{step}] ACTION  {call.name}({call.arguments})")

                result = self.registry.execute(call)
                observation = json.dumps(result, ensure_ascii=False, default=str)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.call_id,
                        "name": call.name,
                        "content": observation,
                    }
                )

                if self.verbose:
                    print(f"[{step}] OBSERVE {observation}")

        raise MaxStepsExceeded(
            f"The run did not finish within max_steps={self.max_steps} model turns"
        )


TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}


class WeatherArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    city: Literal["Tokyo", "Paris"]


class TemperatureArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    temperature_c: float


def get_teaching_weather(arguments: WeatherArguments) -> dict[str, Any]:
    return {"city": arguments.city, **TEACHING_WEATHER[arguments.city]}


def celsius_to_fahrenheit(arguments: TemperatureArguments) -> dict[str, float]:
    converted = round(arguments.temperature_c * 9 / 5 + 32, 1)
    return {"temperature_f": converted}


def build_tools() -> list[Tool]:
    return [
        Tool(
            name="get_teaching_weather",
            description=(
                "Return the deterministic teaching weather record for Tokyo or "
                "Paris. Use it instead of guessing those records."
            ),
            arguments_model=WeatherArguments,
            handler=get_teaching_weather,
        ),
        Tool(
            name="celsius_to_fahrenheit",
            description="Convert a Celsius value to Fahrenheit.",
            arguments_model=TemperatureArguments,
            handler=celsius_to_fahrenheit,
        ),
    ]


class ScriptedWeatherModel:
    """A deterministic model double: weather, conversion, then final text."""

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        del tools
        observations = [m for m in messages if m.get("role") == "tool"]

        if not observations:
            return ModelTurn(
                tool_calls=(
                    ToolCall(
                        call_id="call-weather",
                        name="get_teaching_weather",
                        arguments={"city": "Tokyo"},
                    ),
                )
            )

        if len(observations) == 1:
            weather = json.loads(observations[0]["content"])
            return ModelTurn(
                tool_calls=(
                    ToolCall(
                        call_id="call-convert",
                        name="celsius_to_fahrenheit",
                        arguments={"temperature_c": weather["temperature_c"]},
                    ),
                )
            )

        conversion = json.loads(observations[1]["content"])
        return ModelTurn(
            final_text=(
                "Tokyo's deterministic teaching record is 18.0°C "
                f"({conversion['temperature_f']}°F), cloudy."
            )
        )


def main() -> None:
    runtime = AgentRuntime(
        model=ScriptedWeatherModel(),
        tools=build_tools(),
        max_steps=5,
        verbose=True,
    )
    result = runtime.run(
        "Read Tokyo's teaching weather and convert its temperature to Fahrenheit."
    )

    print("\nmodel_turns:", result.model_turns)
    print("final_answer:", result.answer)


if __name__ == "__main__":
    main()
```

代码较长，但结构并不复杂。下面沿着一次运行拆开看。

### 6.1 Runtime 先建立显式运行记录

```python
messages = [{"role": "user", "content": user_input}]
```

`messages` 是本次运行的显式记录。它不是“藏在模型脑子里的状态”，而是应用自己维护的数据。

每当模型提出 Tool Call，Runtime 先记录模型请求：

```text
assistant
└── tool_calls
```

随后记录工具结果：

```text
tool
├── tool_call_id
├── name
└── content
```

下一轮模型因而能看到清楚的因果链：谁请求了什么，哪个结果属于哪次调用。

### 6.2 每一轮只做一次明确决策

核心循环是：

```python
for step in range(1, self.max_steps + 1):
    turn = self.model.generate(messages, self.registry.schemas())
```

Runtime 不替模型选择工具。它把当前运行记录和工具参数结构交给模型，得到一个 `ModelTurn`。

如果是最终文字：

```python
if turn.final_text is not None:
    return RunResult(...)
```

如果是 Tool Call，Runtime 逐个执行：

```python
for call in turn.tool_calls:
    result = self.registry.execute(call)
```

注意，模型产生的是 `name` 字符串，真正的处理函数来自 `ToolRegistry`。Registry 中不存在的名称会触发 `UnknownToolError`，而不是凭空变成一段可执行代码。

### 6.3 观察结果必须回到下一轮输入

工具返回值被序列化并写入运行记录：

```python
messages.append(
    {
        "role": "tool",
        "tool_call_id": call.call_id,
        "name": call.name,
        "content": observation,
    }
)
```

没有这一步，模型下一轮并不知道函数返回了什么。Runtime 不是“调用工具以后自己心领神会”，它必须把可观察结果明确交回模型。

### 6.4 `max_steps` 是控制边界，不是性能装饰

如果模型不断请求工具，循环不能永远继续：

```python
raise MaxStepsExceeded(...)
```

`max_steps` 计算的是模型决策轮数。它限制最多发起多少轮决策，避免循环在逻辑上无限继续；它不是超时器，也不能单独保证固定费用。

一个没有停止条件的 `while True` 看起来自由奔放，账单也会自由奔放。

### 6.5 错误按责任层分开

本章区分四类核心错误：

```text
InvalidModelTurnError  模型内部响应不满足本章协议
UnknownToolError       请求的工具没有注册
ToolArgumentsError     参数未通过 Pydantic 验证
ToolExecutionError     处理函数在执行时失败
```

这些错误表面上都可能表现为“Agent 没完成任务”，但修复位置不同。把它们揉成一个 `except Exception: pass`，只是把问题从报错改造成失踪人口。

当前 Runtime 遇到工具错误会立即停止，不会自动重试。这是刻意选择的简单语义：读者可以准确知道处理函数执行了几次，不必猜某个有副作用的函数是否被悄悄重复调用。

---

## 7. 为什么要有 `ScriptedWeatherModel`

`ScriptedWeatherModel` 不是在模仿语言能力，它是一个确定性的 Model 替身：

```text
没有观察结果
    → 请求教学天气

有一个观察结果
    → 请求温度换算

有两个观察结果
    → 返回最终文字
```

它让我们单独验证 Runtime：

- 不需要 API Key；
- 每次运行得到同一轨迹；
- 失败时可以先检查控制逻辑，而不是猜模型为什么临时换了主意。

这也是 `Model` 使用 `Protocol` 的价值。只要对象提供相同的 `generate(messages, tools) -> ModelTurn` 接口，它可以是真实 服务商 Adapter，也可以是测试替身。Runtime 不需要为两者写两套循环。

---

## 8. 用确定性检查验证关键边界

“我手动跑了一次，看起来挺像 Agent”不算可靠验证。我们至少要检查成功路径、未知工具、坏参数和不结束的模型。

运行：

```bash
python stages/01-react-runtime/code/runtime_checks.py
```

完整检查代码：

```python
from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from typing import Any

from openai_runtime import OpenAIResponsesModel
from runtime import (
    AgentRuntime,
    InvalidModelTurnError,
    MaxStepsExceeded,
    ModelTurn,
    ScriptedWeatherModel,
    Tool,
    ToolArgumentsError,
    ToolCall,
    ToolExecutionError,
    UnknownToolError,
    WeatherArguments,
    build_tools,
)


class NeverFinishModel:
    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        del tools
        completed_calls = sum(
            1 for message in messages if message.get("role") == "tool"
        )
        return ModelTurn(
            tool_calls=(
                ToolCall(
                    call_id=f"loop-{completed_calls}",
                    name="echo",
                    arguments={"city": "Tokyo"},
                ),
            )
        )


class UnknownToolModel:
    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        del messages, tools
        return ModelTurn(
            tool_calls=(
                ToolCall(
                    call_id="missing",
                    name="move_the_moon",
                    arguments={},
                ),
            )
        )


class InvalidArgumentsModel:
    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        del messages, tools
        return ModelTurn(
            tool_calls=(
                ToolCall(
                    call_id="bad-city",
                    name="get_teaching_weather",
                    arguments={"city": "Atlantis"},
                ),
            )
        )


class RepeatedCallIdModel:
    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        del tools
        if sum(1 for message in messages if message.get("role") == "tool") < 2:
            return ModelTurn(
                tool_calls=(
                    ToolCall(
                        call_id="repeated",
                        name="echo",
                        arguments={"city": "Tokyo"},
                    ),
                )
            )
        return ModelTurn(final_text="done")


class FailingToolModel:
    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        del messages, tools
        return ModelTurn(
            tool_calls=(
                ToolCall(
                    call_id="explode",
                    name="explode",
                    arguments={"city": "Tokyo"},
                ),
            )
        )


class FakeResponsesAPI:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> Any:
        self.requests.append(request)
        if len(self.requests) == 1:
            return SimpleNamespace(
                id="response-1",
                status="completed",
                output=[
                    SimpleNamespace(
                        type="function_call",
                        call_id="call-weather",
                        name="get_teaching_weather",
                        arguments='{"city": "Tokyo"}',
                    )
                ],
                output_text="",
            )
        return SimpleNamespace(
            id="response-2",
            status="completed",
            output=[],
            output_text="The teaching record says 18°C and cloudy.",
        )


class RuntimeChecks(unittest.TestCase):
    def test_happy_path(self) -> None:
        result = AgentRuntime(
            ScriptedWeatherModel(), build_tools(), verbose=False
        ).run("weather then conversion")

        self.assertEqual(result.model_turns, 3)
        self.assertIn("64.4°F", result.answer)
        tool_messages = [
            message for message in result.messages if message.get("role") == "tool"
        ]
        self.assertEqual(
            [message["tool_call_id"] for message in tool_messages],
            ["call-weather", "call-convert"],
        )

    def test_model_turn_requires_exactly_one_exit(self) -> None:
        with self.assertRaises(InvalidModelTurnError):
            ModelTurn()
        with self.assertRaises(InvalidModelTurnError):
            ModelTurn(
                final_text="done",
                tool_calls=(ToolCall("call", "tool", {}),),
            )
        with self.assertRaises(InvalidModelTurnError):
            ModelTurn(
                tool_calls=(
                    ToolCall("duplicate", "tool-a", {}),
                    ToolCall("duplicate", "tool-b", {}),
                )
            )

    def test_unknown_tool_is_rejected(self) -> None:
        runtime = AgentRuntime(
            UnknownToolModel(), build_tools(), max_steps=2, verbose=False
        )
        with self.assertRaises(UnknownToolError):
            runtime.run("request an unregistered tool")

    def test_invalid_arguments_are_rejected_before_handler(self) -> None:
        runtime = AgentRuntime(
            InvalidArgumentsModel(), build_tools(), max_steps=2, verbose=False
        )
        with self.assertRaises(ToolArgumentsError):
            runtime.run("request an unsupported city")

    def test_handler_failure_is_wrapped(self) -> None:
        def explode(arguments: WeatherArguments) -> dict[str, str]:
            del arguments
            raise ValueError("boom")

        tool = Tool(
            name="explode",
            description="Raise a deterministic teaching error.",
            arguments_model=WeatherArguments,
            handler=explode,
        )
        runtime = AgentRuntime(
            FailingToolModel(), [tool], max_steps=2, verbose=False
        )
        with self.assertRaises(ToolExecutionError):
            runtime.run("trigger the tool error")

    def test_call_id_cannot_repeat_across_turns(self) -> None:
        echo = Tool(
            name="echo",
            description="Return the validated city.",
            arguments_model=WeatherArguments,
            handler=lambda arguments: {"city": arguments.city},
        )
        runtime = AgentRuntime(
            RepeatedCallIdModel(), [echo], max_steps=3, verbose=False
        )
        with self.assertRaises(InvalidModelTurnError):
            runtime.run("repeat a call ID")

    def test_max_steps_stops_a_non_finishing_model(self) -> None:
        echo = Tool(
            name="echo",
            description="Return the validated city.",
            arguments_model=WeatherArguments,
            handler=lambda arguments: {"city": arguments.city},
        )
        runtime = AgentRuntime(
            NeverFinishModel(), [echo], max_steps=2, verbose=False
        )
        with self.assertRaises(MaxStepsExceeded):
            runtime.run("keep going")

    def test_openai_adapter_chains_and_sends_only_new_tool_output(self) -> None:
        fake_api = FakeResponsesAPI()
        fake_client = SimpleNamespace(responses=fake_api)
        adapter = OpenAIResponsesModel(model="test-model", client=fake_client)
        schemas = [tool.schema() for tool in build_tools()]

        first_turn = adapter.generate(
            [{"role": "user", "content": "Read Tokyo's teaching weather."}],
            schemas,
        )
        self.assertEqual(first_turn.tool_calls[0].call_id, "call-weather")

        tool_result = json.dumps(
            {"city": "Tokyo", "temperature_c": 18.0, "condition": "cloudy"}
        )
        second_turn = adapter.generate(
            [
                {"role": "user", "content": "Read Tokyo's teaching weather."},
                {
                    "role": "tool",
                    "tool_call_id": "call-weather",
                    "name": "get_teaching_weather",
                    "content": tool_result,
                },
            ],
            schemas,
        )

        self.assertEqual(
            second_turn.final_text,
            "The teaching record says 18°C and cloudy.",
        )
        second_request = fake_api.requests[1]
        self.assertEqual(second_request["previous_response_id"], "response-1")
        self.assertEqual(
            second_request["input"],
            [
                {
                    "type": "function_call_output",
                    "call_id": "call-weather",
                    "output": tool_result,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

八个测试分别确认：

1. 两个工具按顺序执行，最终得到 `64.4°F`；
2. `ModelTurn` 必须二选一，并拒绝同一轮中的重复调用编号；
3. 未注册工具不能执行；
4. 非法城市在进入处理函数前被拒绝；
5. 处理函数异常会被包装成明确的 `ToolExecutionError`；
6. 同一个调用编号不能跨轮次重复使用；
7. 不结束的模型会被 `max_steps` 截断；
8. OpenAI Adapter 会正确续接响应，并且只发送新产生的工具结果。

最后一个测试使用伪客户端，不会访问网络。我们验证的是 Adapter 组装了什么请求，而不是某个远程模型今天是否愿意配合演出。

---

## 9. 接入真实模型：Adapter 只负责翻译

离线 Runtime 已经能够独立工作。现在接入 OpenAI Responses API 时，不修改 `AgentRuntime.run()`；只增加一个满足 `Model` 协议的 Adapter。

运行前设置：

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-id"
```

然后执行：

```bash
python stages/01-react-runtime/code/openai_runtime.py
```

完整代码：

```python
from __future__ import annotations

import json
import os
from typing import Any

from runtime import AgentRuntime, ModelTurn, ToolCall, build_tools


class ProviderResponseError(RuntimeError):
    pass


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
            "stages/01-react-runtime/code/requirements.txt"
        ) from exc

    required_env("OPENAI_API_KEY")
    return OpenAI()


class OpenAIResponsesModel:
    """Translate between the chapter runtime and the OpenAI Responses API.

    One adapter instance represents one run. It chains provider responses with
    previous_response_id and sends only newly produced tool outputs on later turns.
    """

    def __init__(
        self,
        model: str,
        *,
        client: Any | None = None,
        instructions: str = (
            "Use the supplied tools when they are needed. Base the final answer on "
            "tool outputs and do not invent tool results."
        ),
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")
        self.model = model
        self.client = client if client is not None else create_client()
        self.instructions = instructions
        self._previous_response_id: str | None = None
        self._submitted_tool_call_ids: set[str] = set()

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        input_items, pending_call_ids = self._next_input(messages)

        request: dict[str, Any] = {
            "model": self.model,
            "instructions": self.instructions,
            "input": input_items,
            "tools": [self._to_openai_tool(tool) for tool in tools],
            "parallel_tool_calls": False,
        }
        if self._previous_response_id is not None:
            request["previous_response_id"] = self._previous_response_id

        response = self.client.responses.create(**request)
        if response.status != "completed":
            raise ProviderResponseError(
                f"The provider response did not complete: {response.status}"
            )

        response_id = getattr(response, "id", None)
        if not isinstance(response_id, str) or not response_id.strip():
            raise ProviderResponseError("The provider response has no valid ID")

        calls = self._extract_tool_calls(response)
        if calls:
            turn = ModelTurn(tool_calls=tuple(calls))
        else:
            text = response.output_text
            if not text or not text.strip():
                raise ProviderResponseError(
                    "The provider returned neither function calls nor final text"
                )
            turn = ModelTurn(final_text=text)

        self._previous_response_id = response_id
        self._submitted_tool_call_ids.update(pending_call_ids)
        return turn

    def _next_input(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], set[str]]:
        if self._previous_response_id is None:
            initial = [
                {"role": message["role"], "content": message.get("content", "")}
                for message in messages
                if message.get("role") in {"system", "developer", "user"}
            ]
            if not initial:
                raise ProviderResponseError("The first provider turn needs user input")
            return initial, set()

        outputs: list[dict[str, Any]] = []
        pending_call_ids: set[str] = set()
        for message in messages:
            if message.get("role") != "tool":
                continue

            call_id = str(message.get("tool_call_id", ""))
            if not call_id or call_id in self._submitted_tool_call_ids:
                continue

            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": str(message.get("content", "")),
                }
            )
            pending_call_ids.add(call_id)

        if not outputs:
            raise ProviderResponseError(
                "A continued provider turn needs at least one new tool output"
            )
        return outputs, pending_call_ids

    @staticmethod
    def _to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"],
            "strict": True,
        }

    @staticmethod
    def _extract_tool_calls(response: Any) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for item in response.output:
            if item.type != "function_call":
                continue

            try:
                arguments = json.loads(item.arguments)
            except json.JSONDecodeError as exc:
                raise ProviderResponseError(
                    f"Arguments for function {item.name!r} are not valid JSON"
                ) from exc
            if not isinstance(arguments, dict):
                raise ProviderResponseError(
                    f"Arguments for function {item.name!r} must be a JSON object"
                )

            calls.append(
                ToolCall(
                    call_id=item.call_id,
                    name=item.name,
                    arguments=arguments,
                )
            )
        return calls


def main() -> None:
    model = OpenAIResponsesModel(model=required_env("OPENAI_MODEL"))
    runtime = AgentRuntime(
        model=model,
        tools=build_tools(),
        max_steps=6,
        verbose=True,
    )
    result = runtime.run(
        "Read Tokyo's teaching weather and convert its temperature to Fahrenheit."
    )
    print("\nfinal_answer:", result.answer)


if __name__ == "__main__":
    main()
```

Adapter 的职责只有三类翻译：

```text
Runtime Tool schema
    → OpenAI function tool

OpenAI function_call
    → ToolCall

Runtime tool message
    → function_call_output
```

核心 Runtime 仍然只认识 `ModelTurn` 和 `ToolCall`。为了让真实示例保持单线、便于观察，Adapter 设置了 `parallel_tool_calls=False`，将服务商每轮限制为至多一个工具调用；Runtime 的内部协议仍然能够表示多个调用。

### 9.1 为什么使用 `previous_response_id`

第一次模型服务请求可能返回函数调用。第二次请求需要把 Python 产生的工具结果接到那次响应之后：

```python
request["previous_response_id"] = self._previous_response_id
```

Adapter 在第一次调用后保存 `response.id`。后续只发送本轮新产生的 `function_call_output`，由 `previous_response_id` 保留响应链关系。

这比手工重建模型服务商的全部历史输出更稳妥。某些模型响应除了函数调用还可能包含其他协议项；随手只摘取自己认识的字段，容易让下一轮缺少必要状态。

### 9.2 为什么 Adapter 实例只服务一次 run

`OpenAIResponsesModel` 内部保存：

```python
self._previous_response_id
self._submitted_tool_call_ids
```

这些值属于一条运行轨迹。因此，一个 Adapter 实例对应一次 `runtime.run(...)`。两个用户任务不应共用同一个实例，否则第二个任务可能被错误地接到第一个响应后面。

把这条限制写在类注释和教程里，比让它以“偶尔串台”的形式自行教学要便宜得多。

### 9.3 为什么只发送新的工具结果

Runtime 的 `messages` 每轮包含完整运行记录。如果 Adapter 每次把所有工具结果重新发送一遍，同一个 `call_id` 就会被重复提交。

因此代码维护：

```python
self._submitted_tool_call_ids: set[str]
```

只有尚未提交的工具结果会进入下一次模型服务请求。请求成功后再把 ID 标记为已提交；如果网络调用抛错，这些结果仍可由调用方决定是否再次尝试，而不会在发送前就被错误标记为完成。

### 9.4 Tool schema 仍然不是执行权限

Adapter 把本章 Tool 转为：

```python
{
    "type": "function",
    "name": ...,
    "description": ...,
    "parameters": ...,
    "strict": True,
}
```

这只是在模型输入中描述可请求的函数。真正执行仍然经过：

```text
ToolCall
   ↓
ToolRegistry 查找
   ↓
Pydantic 参数验证
   ↓
处理函数调用
```

模型服务商能约束正常生成的参数结构，Runtime 的执行边界仍然自行验证。两层检查服务于不同位置，不应互相冒充替代品。

---

## 10. 本章 Runtime 的明确边界

这个实现已经具备一个最小 Agent 循环所需的核心部件：

```text
provider-neutral model contract
registered tools
runtime-side argument validation
decide → act → observe loop
显式运行记录
call/result correlation
step limit
separate error types
deterministic tests
真实模型服务 Adapter
```

它同时有意保持简单：

- 所有工具按顺序、同步执行；
- 运行记录只保存在当前进程内；
- 工具失败会停止本次运行；
- 一个 Adapter 实例只处理一条运行轨迹；
- `max_steps` 限制模型轮数，但不等同于完整的时间或费用控制。

这些不是藏起来的缺陷，而是本章代码的准确规格。判断一段 Agent 代码是否可靠，第一步不是问“它看起来有多聪明”，而是问“它承诺了哪些行为，没有承诺哪些行为”。

---

## 11. 动手练习

### 练习一：一次返回两个 Tool Call

让 确定性模型替身 在同一轮返回两个不同 `call_id` 的调用。观察 Runtime 按什么顺序执行、怎样记录结果。然后尝试故意复用同一个 `call_id`，思考是否应该在 Runtime 中增加唯一性检查。

### 练习二：让错误成为观察结果

当前处理函数失败会终止运行。尝试把错误序列化成一条 工具观察结果 再交给模型，但必须同时添加一个明确的尝试次数上限。比较两种语义下，调用次数是否仍然容易推断。

### 练习三：增加第三个工具

加入 `describe_temperature`，输入一个华氏温度并返回 `cold`、`mild` 或 `hot`。更新 `ScriptedWeatherModel`，让轨迹多一轮，但不要修改 `AgentRuntime.run()`。如果必须改核心循环，说明抽象还不够通用。

### 练习四：破坏 Adapter 的去重

暂时移除 `_submitted_tool_call_ids`，用伪客户端 记录第三次请求。观察旧工具结果 如何被再次发送，再恢复代码。

### 练习五：检查空输入

调用 `runtime.run("   ")`，确认错误在模型调用前发生。输入边界越早失败，越容易定位。

---

## 12. 本章总结

这一章不是把 `while` 循环换成了一个更响亮的类名。我们完成了一个职责拆分过程：

```text
固定的两次 API 调用
        ↓
发现步骤数量无法预先写死
        ↓
定义 ToolCall 与 ModelTurn
        ↓
用 Tool 封装参数结构、验证和处理函数
        ↓
用 ToolRegistry 限制可执行能力
        ↓
用运行记录保存动作与观察结果
        ↓
用 AgentRuntime 统一控制继续与停止
        ↓
用确定性模型替身和测试验证运行语义
        ↓
用 Adapter 接入真实模型服务
```

现在你应该能从代码回答：模型拥有什么决策权，Runtime 拥有什么控制权，Tool Call 又在哪一步才真正变成 Python 执行。

本章目录：

```text
stages/01-react-runtime/
├── README.zh-CN.md
├── README.md
├── code/
│   ├── runtime.py
│   ├── openai_runtime.py
│   ├── runtime_checks.py
│   └── requirements.txt
└── theory/
    └── 旧链接兼容入口；正文已经合并到本 README
```

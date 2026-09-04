# Stage 01: Make the Model Work in a Loop—Build a Minimal Agent Runtime

> Language: **English** | [简体中文](README.zh-CN.md)

The previous chapter completed one tool round trip, but its sequence was hard-coded: ask for a tool once, execute it once, then ask for final text. Change the task to “read the teaching weather and convert Celsius to Fahrenheit,” and the program starts collecting variables named `first`, `second`, and `third`. A few more turns and the code needs a family tree.

This chapter addresses the real problem:

> **How can an application organize an unknown number of model decisions and tool executions into a bounded, inspectable, replaceable loop?**

We will build a small Agent Runtime without an Agent framework. It runs and tests offline. Only after the control logic is clear will we connect a real OpenAI Responses API adapter.

The complete lesson is in this README. Complete runnable files live only in [`code/`](code/) and are reproduced in full at the point where they are taught.

---

## 1. Why a fixed script is not enough

The previous control flow looked roughly like this:

```python
first = call_model(user_request)
call = read_function_call(first)
result = execute(call)
final = call_model(result)
return final.output_text
```

It quietly assumes:

```text
the model always asks for a tool first
the model asks exactly once
the second turn always produces final text
```

A real decision path may be just:

```text
answer directly
```

or:

```text
read weather
→ convert temperature
→ answer
```

or:

```text
read weather
→ discover that an argument is missing
→ make a corrected request
→ answer
```

The application cannot name every turn in advance. It needs one control loop: ask the model for the next decision, execute requested tools and record their results, or stop when final text arrives.

The core shape is small:

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

The rest of the chapter derives the contracts that make this loop safe enough to reason about.

---

## 2. ReAct: an observable loop, not a demand for hidden thoughts

**ReAct** combines reasoning and acting. In practical runtime terms, the model chooses an action from its current information, the application executes it, an Observation comes back, and the model decides again.

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

The runtime does not need to read or print a model’s private chain of thought. It needs observable protocol objects:

- the requested tool;
- the arguments;
- the application-produced result;
- the final answer.

A parser built around strings such as `Thought:` and `Action:` turns punctuation into infrastructure. A missing colon should not bring down the control plane. We will use structured Tool Calls instead.

### 2.1 The trace used in this chapter

We keep deterministic teaching data and add a temperature conversion tool:

```text
user: read Tokyo's teaching weather and convert it to Fahrenheit

model requests get_teaching_weather(city="Tokyo")
    ↓
application returns 18.0°C and cloudy
    ↓
model requests celsius_to_fahrenheit(temperature_c=18.0)
    ↓
application returns 64.4°F
    ↓
model returns final text
```

A real model may choose differently. We first use a fully deterministic `ScriptedWeatherModel` so that runtime bugs are not mixed with model variability.

---

## 3. Separate the responsibilities: Model, Tool, Runtime

A minimal system has three roles:

```text
                 ┌──────────────┐
                 │    Model     │
                 │ decide next  │
                 └──────┬───────┘
                        │ ModelTurn
                        ▼
┌────────────┐   ┌──────────────┐   ┌────────────┐
│ transcript │◀─▶│   Runtime    │──▶│    Tool    │
└────────────┘   │ control loop │   │  handler   │
                 └──────────────┘   └─────┬──────┘
                                         │
                                         ▼
                                    Observation
```

The **Model** returns one decision from the current messages and tool interfaces: final text or one or more Tool Calls.

A **Tool** joins a model-visible interface to an application-owned Python handler. It also validates arguments before execution.

The **Runtime** owns control flow. It invokes the Model, resolves tools, executes handlers, records Observations, and enforces stopping conditions.

The boundary is simple:

> **The model decides what it would like to do; the runtime decides how the run actually advances.**

---

## 4. Keep provider fields out of the core loop

A runtime written like this:

```python
for item in response.output:
    if item.type == "function_call":
        ...
```

already depends on one provider’s wire format. A field change or a new provider now requires surgery inside the control loop.

The runtime needs a much smaller internal vocabulary:

```text
ToolCall
├── call_id
├── name
└── arguments

ModelTurn
├── final_text
└── tool_calls
```

An adapter translates the external response into that vocabulary:

```text
provider response
       ↓
     adapter
       ↓
ModelTurn / ToolCall
       ↓
     runtime
```

The runtime can then be tested without a network and without knowing where a provider stores function calls.

### 4.1 Why `ModelTurn` has exactly two exits

This chapter permits one of two outcomes per model turn:

```text
final_text   end the run
or
tool_calls   execute, observe, and continue
```

Neither “both” nor “neither” is valid. A real API may expose more complicated mixtures, but an internal teaching contract does not need to mirror every external possibility.

The state transitions stay explicit:

```text
ModelTurn(final_text=...)
        → END

ModelTurn(tool_calls=...)
        → ACT → OBSERVE → NEXT TURN
```

---

## 5. A Tool is a function plus an input contract

The chapter represents a tool with four fields:

```python
@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: Callable[[Any], Any]
```

The name, description, and generated parameter schema are shown to the model. The handler stays inside the application. The Pydantic argument model serves two purposes:

1. generate JSON Schema for the model interface;
2. validate returned arguments again at the execution boundary.

Why validate twice? A Tool Call may arrive from a provider, a saved trace, a test fixture, or another input path. Even when an upstream system promises strict generation, the component about to execute code should verify the data it accepts.

```text
upstream tries to produce valid arguments
        ≠
the handler can skip validation
```

For example:

```python
class WeatherArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    city: Literal["Tokyo", "Paris"]
```

Extra fields are rejected, silent coercion is reduced, and the city must exist in the teaching dataset.

---

## 6. Complete implementation: an offline runtime

Install the chapter dependencies:

```bash
python -m pip install -r stages/01-react-runtime/code/requirements.txt
```

Dependency file:

```text
openai>=2,<3
pydantic>=2.11,<3
```

Run the offline example:

```bash
python stages/01-react-runtime/code/runtime.py
```

Expected trace:

```text
[1] ACTION  get_teaching_weather({'city': 'Tokyo'})
[1] OBSERVE {"city": "Tokyo", "temperature_c": 18.0, "condition": "cloudy"}
[2] ACTION  celsius_to_fahrenheit({'temperature_c': 18.0})
[2] OBSERVE {"temperature_f": 64.4}
[3] FINAL   Tokyo's deterministic teaching record is 18.0°C (64.4°F), cloudy.
```

Complete source:

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

The file is substantial, but the runtime path is straightforward.

### 6.1 Start with an explicit transcript

```python
messages = [{"role": "user", "content": user_input}]
```

`messages` is application-owned state for this run. It is not hidden model memory.

When the model requests a tool, the runtime records the assistant request and then the tool result:

```text
assistant
└── tool_calls

tool
├── tool_call_id
├── name
└── content
```

The next model turn receives a causal trace: which action was requested and which Observation belongs to it.

### 6.2 Ask for one explicit decision per turn

The loop begins with:

```python
for step in range(1, self.max_steps + 1):
    turn = self.model.generate(messages, self.registry.schemas())
```

The runtime does not choose the next tool for the model. It supplies the transcript and interfaces, then receives a `ModelTurn`.

Final text ends the run:

```python
if turn.final_text is not None:
    return RunResult(...)
```

Tool Calls are resolved by the registry:

```python
for call in turn.tool_calls:
    result = self.registry.execute(call)
```

The model only produced a name. The executable handler comes from `ToolRegistry`. An absent name raises `UnknownToolError`; it does not materialize into executable code by optimism.

### 6.3 Feed Observations into the next turn

The result is serialized and added to the transcript:

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

Without this step, the model cannot know what the function returned. Tool execution and model observation are separate operations.

### 6.4 `max_steps` is a control boundary

A model can keep requesting actions. The application must not continue forever:

```python
raise MaxStepsExceeded(...)
```

Here, `max_steps` counts model turns. It prevents the control loop from continuing forever, but it is not a timeout and cannot by itself guarantee a fixed bill. An unbounded `while True` has a certain adventurous charm until it meets a paid API.

### 6.5 Separate errors by responsibility

The runtime distinguishes:

```text
InvalidModelTurnError  the model-facing contract is internally invalid
UnknownToolError       no registered tool matches the requested name
ToolArgumentsError     Pydantic rejected the arguments
ToolExecutionError     the Python handler failed
```

They may all look like “the Agent failed” from far away, but they are repaired in different components. Catching everything and continuing would hide both the cause and the number of executions.

This runtime stops on a tool error and does not retry automatically. That simple rule makes execution counts predictable, especially for functions that may have side effects.

---

## 7. Why use `ScriptedWeatherModel`

`ScriptedWeatherModel` is not pretending to be intelligent. It is a deterministic Model double:

```text
no Observations
    → request teaching weather

one Observation
    → request conversion

two Observations
    → return final text
```

That lets us test the runtime without an API key and obtain the same trace every time. When a test fails, the control logic is the first suspect rather than a model’s changing choice.

The `Model` `Protocol` makes this possible. Any object that implements `generate(messages, tools) -> ModelTurn` can occupy the boundary: a provider adapter or a deterministic test double. The runtime loop remains the same.

---

## 8. Verify the boundaries with deterministic checks

“I ran it once and it looked agent-like” is not a test strategy. We need at least a successful trace, an unknown tool, invalid arguments, and a model that never finishes.

Run:

```bash
python stages/01-react-runtime/code/runtime_checks.py
```

Complete checks:

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

The eight tests verify that:

1. two tools execute in order and produce `64.4°F`;
2. a `ModelTurn` has exactly one exit and rejects duplicate IDs within a turn;
3. unregistered tools cannot execute;
4. invalid cities are rejected before the handler;
5. handler failures are wrapped as `ToolExecutionError`;
6. a call ID cannot be reused across model turns;
7. `max_steps` stops a non-finishing model;
8. the OpenAI adapter continues from the correct response and submits only new Tool Output.

The last test uses a Fake Client. It checks the request assembled by the adapter without contacting a remote service.

---

## 9. Connect a real model: the adapter only translates

The offline runtime is complete. To use the OpenAI Responses API, we add an object that satisfies the same `Model` protocol; `AgentRuntime.run()` does not change.

Set:

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-id"
```

Run:

```bash
python stages/01-react-runtime/code/openai_runtime.py
```

Complete source:

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

The adapter translates three boundaries:

```text
runtime Tool schema
    → OpenAI function tool

OpenAI function_call
    → ToolCall

runtime tool message
    → function_call_output
```

The core runtime still knows only `ModelTurn` and `ToolCall`. To keep the live trace linear and easy to inspect, the adapter sets `parallel_tool_calls=False`, so the provider proposes at most one tool call per turn; the runtime contract can still represent multiple calls.

### 9.1 Continue with `previous_response_id`

After the first provider response requests a function, the next request must attach the Python-produced Tool Output to that response:

```python
request["previous_response_id"] = self._previous_response_id
```

The adapter stores `response.id` after each completed call. Later turns submit only the newly produced `function_call_output`, while `previous_response_id` preserves the response lineage.

This avoids manually rebuilding every provider output item. Provider responses may include protocol state beyond the fields this teaching runtime normalizes; copying only familiar fragments can silently lose necessary context.

### 9.2 One adapter instance represents one run

`OpenAIResponsesModel` stores:

```python
self._previous_response_id
self._submitted_tool_call_ids
```

Those values belong to one trace. Create a fresh adapter for each `runtime.run(...)`. Reusing one instance for unrelated tasks would connect the second task to the first response chain.

Documenting that lifetime rule is cheaper than debugging a conversation that occasionally changes subjects on its own.

### 9.3 Submit each Tool Output once

The runtime passes the complete transcript on every turn. If the adapter resent every tool message, an old `call_id` would be submitted repeatedly.

The adapter therefore tracks:

```python
self._submitted_tool_call_ids: set[str]
```

Only unseen outputs are included. IDs are marked after a successful provider response, not before the network call.

### 9.4 A schema is still not execution authority

The adapter emits strict function schemas, but the execution path remains:

```text
ToolCall
   ↓
ToolRegistry lookup
   ↓
Pydantic validation
   ↓
handler invocation
```

Provider-side structured generation and runtime-side validation protect different boundaries. Neither should be treated as a substitute for the other.

---

## 10. State the runtime’s limits accurately

The implementation now has the core pieces of a minimal Agent loop:

```text
provider-neutral model contract
registered tools
runtime-side argument validation
decide → act → observe loop
explicit transcript
call/result correlation
step limit
separate error types
deterministic tests
real provider adapter
```

It intentionally remains small:

- tools execute synchronously and in sequence;
- the transcript exists only in the current process;
- tool failures stop the run;
- one adapter instance serves one trace;
- `max_steps` limits model turns, not every possible time or cost dimension.

These are not secret shortcomings. They are the specification. Before asking whether an Agent looks intelligent, ask what behavior its runtime actually promises.

---

## 11. Exercises

### Exercise 1: return two Tool Calls in one turn

Modify the fake model to return two calls with distinct `call_id` values. Observe execution order and result correlation. Then intentionally reuse an ID and decide whether the runtime should reject duplicates.

### Exercise 2: turn an error into an Observation

The current runtime stops when a handler fails. Serialize the failure as a Tool Observation and let the Model decide again, but add an explicit attempt limit. Compare how easy it is to determine the number of executions under each policy.

### Exercise 3: add a third tool

Create `describe_temperature`, which maps a Fahrenheit value to `cold`, `mild`, or `hot`. Extend `ScriptedWeatherModel` by one turn without changing `AgentRuntime.run()`. If the loop must change, the abstraction is not yet general enough.

### Exercise 4: break adapter deduplication

Temporarily remove `_submitted_tool_call_ids`, record a third request with the Fake Client, and observe old outputs being submitted again. Then restore the guard.

### Exercise 5: pass blank input

Call `runtime.run("   ")` and confirm that it fails before invoking the Model. Early boundary failures are easier to diagnose.

---

## 12. Chapter summary

This chapter did more than rename a `while` loop. It separated responsibilities:

```text
fixed API calls
        ↓
unknown number of decisions
        ↓
ToolCall and ModelTurn contracts
        ↓
Tool schema, validation, and handler
        ↓
ToolRegistry capability lookup
        ↓
Action and Observation transcript
        ↓
AgentRuntime control and stopping
        ↓
deterministic model double and tests
        ↓
real provider adapter
```

You should now be able to point to the exact line where a model decision becomes Python execution, explain what the Runtime controls, and identify which data belongs to a single run.

Chapter layout:

```text
stages/01-react-runtime/
├── README.md
├── README.zh-CN.md
├── code/
│   ├── runtime.py
│   ├── openai_runtime.py
│   ├── runtime_checks.py
│   └── requirements.txt
└── theory/
    └── compatibility entry points for old links; all teaching is in this README
```

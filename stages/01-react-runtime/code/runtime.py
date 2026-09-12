"""A synchronous tool loop, plus a clearly labeled offline weather exercise."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import json
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError


class AgentRuntimeError(RuntimeError):
    """A failed run retains observations, not a fabricated final answer."""

    messages: tuple[dict[str, Any], ...] = ()
    model_turns: int = 0
    tool_executions: int = 0


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


class ToolBudgetExceeded(AgentRuntimeError):
    pass


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]

    def __post_init__(self) -> None:
        for value in (self.call_id, self.name):
            if not isinstance(value, str) or not value.strip():
                raise InvalidModelTurnError("Call ID and tool name must be non-empty strings.")
        if not isinstance(self.arguments, dict):
            raise InvalidModelTurnError("Tool arguments must be a dictionary.")


@dataclass(frozen=True)
class ModelTurn:
    final_text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    # Opaque transport items are replayed by the adapter, never used to select actions.
    provider_items: tuple[dict[str, Any], ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.tool_calls, tuple) or not all(
            isinstance(call, ToolCall) for call in self.tool_calls
        ):
            raise InvalidModelTurnError("tool_calls must be a tuple of ToolCall objects.")
        has_final = self.final_text is not None
        has_calls = bool(self.tool_calls)
        if has_final == has_calls:
            raise InvalidModelTurnError("Return either final_text or tool_calls, not both or neither.")
        if has_final and (not isinstance(self.final_text, str) or not self.final_text.strip()):
            raise InvalidModelTurnError("Final text must be non-empty.")
        ids = [call.call_id for call in self.tool_calls]
        if len(ids) != len(set(ids)):
            raise InvalidModelTurnError("Call IDs must be unique within a turn.")
        if not isinstance(self.provider_items, tuple) or not all(
            isinstance(item, dict) for item in self.provider_items
        ):
            raise InvalidModelTurnError("Provider continuation items must be dictionaries.")


class Model(Protocol):
    def generate(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn: ...


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: Callable[[Any], Any]

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip()
               for value in (self.name, self.description)):
            raise ValueError("Tools need a name and description.")
        if not isinstance(self.arguments_model, type) or not issubclass(self.arguments_model, BaseModel):
            raise TypeError("arguments_model must be a Pydantic model class.")
        if not callable(self.handler):
            raise TypeError("handler must be callable.")

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.arguments_model.model_json_schema(),
        }

    def validate(self, raw_arguments: dict[str, Any]) -> BaseModel:
        try:
            return self.arguments_model.model_validate(deepcopy(raw_arguments))
        except ValidationError as exc:
            raise ToolArgumentsError(f"Invalid arguments for {self.name}.") from exc

    def execute(self, arguments: BaseModel) -> str:
        try:
            result = self.handler(arguments)
        except Exception as exc:
            raise ToolExecutionError(f"Handler failed for {self.name}.") from exc
        try:
            return json.dumps(result, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ToolExecutionError(f"{self.name} did not return serializable JSON data.") from exc


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Duplicate tool: {tool.name}")
            self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def prepare(self, call: ToolCall) -> tuple[Tool, BaseModel]:
        tool = self._tools.get(call.name)
        if tool is None:
            raise UnknownToolError(f"Unknown tool: {call.name}")
        return tool, tool.validate(call.arguments)


@dataclass(frozen=True)
class RunResult:
    answer: str
    model_turns: int
    messages: tuple[dict[str, Any], ...]
    tool_executions: int


class AgentRuntime:
    """One run owns one transcript; all tools execute sequentially, with no retry."""

    def __init__(
        self, model: Model, tools: list[Tool], *, max_steps: int = 6,
        max_tool_calls: int = 6, verbose: bool = True,
    ) -> None:
        if type(max_steps) is not int or max_steps < 1:
            raise ValueError("max_steps must be a positive integer.")
        if type(max_tool_calls) is not int or max_tool_calls < 0:
            raise ValueError("max_tool_calls must be a non-negative integer.")
        self.model = model
        self.registry = ToolRegistry(tools)
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls
        self.verbose = verbose

    def run(self, user_input: str) -> RunResult:
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("user_input must be a non-empty string.")
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_input}]
        seen_call_ids: set[str] = set()
        tool_executions = 0
        step = 0
        try:
            for step in range(1, self.max_steps + 1):
                turn = self.model.generate(deepcopy(messages), self.registry.schemas())
                if not isinstance(turn, ModelTurn):
                    raise InvalidModelTurnError("Model.generate() must return ModelTurn.")

                if turn.final_text is not None:
                    messages.append({"role": "assistant", "content": turn.final_text})
                    if self.verbose:
                        print(f"[{step}] FINAL   {turn.final_text}")
                    return RunResult(
                        answer=turn.final_text,
                        model_turns=step,
                        messages=tuple(deepcopy(messages)),
                        tool_executions=tool_executions,
                    )

                messages.append({
                    "role": "assistant", "content": "",
                    "tool_calls": [asdict(call) for call in turn.tool_calls],
                    "provider_items": deepcopy(list(turn.provider_items)),
                })
                if any(call.call_id in seen_call_ids for call in turn.tool_calls):
                    raise InvalidModelTurnError("A call ID was reused within this run.")
                if tool_executions + len(turn.tool_calls) > self.max_tool_calls:
                    raise ToolBudgetExceeded("This batch would exceed the tool-call budget.")

                # Validate the whole batch before starting its first handler.
                prepared = [self.registry.prepare(call) for call in turn.tool_calls]
                seen_call_ids.update(call.call_id for call in turn.tool_calls)
                for call, (tool, arguments) in zip(turn.tool_calls, prepared):
                    if self.verbose:
                        print(f"[{step}] ACTION  {call.name}({call.arguments})")
                    tool_executions += 1
                    observation = tool.execute(arguments)
                    messages.append({
                        "role": "tool", "tool_call_id": call.call_id,
                        "name": call.name, "content": observation,
                    })
                    if self.verbose:
                        print(f"[{step}] OBSERVE {observation}")
            raise MaxStepsExceeded(f"No final answer within {self.max_steps} model turns.")
        except AgentRuntimeError as exc:
            exc.messages = tuple(deepcopy(messages))
            exc.model_turns = step
            exc.tool_executions = tool_executions
            raise


TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}


class WeatherArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    city: Literal["Tokyo", "Paris"]


class TemperatureArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    temperature_c: float


def get_teaching_weather(arguments: WeatherArguments) -> dict[str, Any]:
    return {
        "city": arguments.city,
        **TEACHING_WEATHER[arguments.city],
        "source": "fixed teaching record",
    }


def celsius_to_fahrenheit(arguments: TemperatureArguments) -> dict[str, float]:
    converted = round(arguments.temperature_c * 9 / 5 + 32, 1)
    return {"temperature_f": converted}


def build_tools() -> list[Tool]:
    return [
        Tool(
            name="get_teaching_weather",
            description="Read the fixed teaching record for Tokyo or Paris; not live weather.",
            arguments_model=WeatherArguments,
            handler=get_teaching_weather,
        ),
        Tool(
            name="celsius_to_fahrenheit",
            description="Convert a supplied numeric Celsius value to Fahrenheit.",
            arguments_model=TemperatureArguments,
            handler=celsius_to_fahrenheit,
        ),
    ]


def request_for(city: str, task: str, language: str) -> str:
    if (city not in TEACHING_WEATHER or task not in {"convert", "weather", "greet"}
            or language not in {"zh-CN", "en"}):
        raise ValueError("Unsupported exercise option.")
    if task == "greet":
        if language == "zh-CN":
            return "你好，请打个招呼，不用查询天气。"
        return "Hello. Just greet me; no weather lookup."
    if language == "zh-CN":
        text = f"请读取 {city} 的教学天气，报告摄氏温度和天气状况。"
        if task == "convert":
            text += "请调用换算工具，把查到的温度换成华氏度。"
        return text + "这不是实时天气。"
    text = f"Read {city}'s teaching weather, reporting Celsius and condition. "
    if task == "convert":
        text += "Use the conversion tool to convert that reading to Fahrenheit. "
    return text + "This is not live weather."


class ScriptedWeatherModel:
    """A configured test double, NOT a natural-language model."""

    def __init__(
        self, *, city: str = "Tokyo", task: str = "convert", language: str = "zh-CN"
    ) -> None:
        request_for(city, task, language)  # Validate the exercise configuration.
        self.city, self.task, self.language = city, task, language

    def generate(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn:
        del tools
        if self.task == "greet":
            return ModelTurn(final_text="你好！" if self.language == "zh-CN" else "Hello!")
        observations = {
            m["name"]: json.loads(m["content"])
            for m in messages if m["role"] == "tool"
        }
        weather = observations.get("get_teaching_weather")
        if weather is None:
            return ModelTurn(tool_calls=(
                ToolCall("call-weather", "get_teaching_weather", {"city": self.city}),
            ))
        conversion = observations.get("celsius_to_fahrenheit")
        if self.task == "convert" and conversion is None:
            return ModelTurn(tool_calls=(
                ToolCall(
                    "call-convert", "celsius_to_fahrenheit",
                    {"temperature_c": weather["temperature_c"]},
                ),
            ))
        celsius = weather["temperature_c"]
        units = f"{celsius:.1f}°C"
        if self.task == "convert":
            units += f" / {conversion['temperature_f']:.1f}°F"
        if self.language == "zh-CN":
            translations = {"cloudy": "多云", "light rain": "小雨"}
            condition = translations.get(weather["condition"], weather["condition"])
            answer = f"{weather['city']} 的教学记录：{units}，{condition}；这不是实时天气。"
        else:
            answer = (
                f"{weather['city']}'s teaching record: {units}, "
                f"{weather['condition']}; not live weather."
            )
        return ModelTurn(final_text=answer)


def parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--city", choices=tuple(TEACHING_WEATHER), default="Tokyo")
    parser.add_argument("--task", choices=("convert", "weather", "greet"), default="convert")
    parser.add_argument("--language", choices=("zh-CN", "en"), default="zh-CN")
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--max-tool-calls", type=int, default=6)
    parser.add_argument("--show-transcript", action="store_true")
    return parser.parse_args()


def format_transcript(messages: tuple[dict[str, Any], ...]) -> str:
    """Show observed actions/results, not provider reasoning or hidden state."""
    lines = []
    for message in messages:
        if message.get("tool_calls"):
            for call in message["tool_calls"]:
                lines.append(f"assistant -> {call['call_id']}: {call['name']} {call['arguments']}")
        elif message["role"] == "tool":
            lines.append(f"tool -> {message['tool_call_id']}: {message['content']}")
        else:
            lines.append(f"{message['role']}: {message['content']}")
    return "\n".join(lines)


def run_exercise(model: Model, args: argparse.Namespace) -> int:
    try:
        runtime = AgentRuntime(
            model, build_tools(), max_steps=args.max_steps,
            max_tool_calls=args.max_tool_calls,
        )
        result = runtime.run(request_for(args.city, args.task, args.language))
    except AgentRuntimeError as exc:
        print(f"{type(exc).__name__}: {exc}")
        print(f"model_turns={exc.model_turns}, tool_executions={exc.tool_executions}")
        if args.show_transcript:
            print(format_transcript(exc.messages))
        return 1
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 1
    print(f"model_turns={result.model_turns}, tool_executions={result.tool_executions}")
    if args.show_transcript:
        print(format_transcript(result.messages))
    return 0


def main() -> int:
    args = parse_args("Offline weather exercise; no model service is called.")
    print("=== 离线模型替身 / offline model double: no API request ===")
    model = ScriptedWeatherModel(city=args.city, task=args.task, language=args.language)
    return run_exercise(model, args)


if __name__ == "__main__":
    raise SystemExit(main())

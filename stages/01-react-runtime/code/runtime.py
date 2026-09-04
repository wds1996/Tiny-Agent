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

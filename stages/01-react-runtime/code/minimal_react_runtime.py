"""Stage 01: build a tiny ReAct-style Runtime from first principles.

This file is intentionally self-contained. It keeps the model deterministic so
you can study the Runtime control flow without network access, API keys, or LLM
sampling noise.

Run:
    python stages/01-react-runtime/code/minimal_react_runtime.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


# ---------------------------------------------------------------------------
# 1) Provider-neutral model/runtime types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ToolCall:
    """One model proposal to invoke a named Tool."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ModelResponse:
    """One normalized model decision."""

    final_answer: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class Model(Protocol):
    """The only model contract AgentRuntime depends on."""

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        ...


# ---------------------------------------------------------------------------
# 2) Tool interface and execution registry
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]

    def schema(self) -> dict[str, Any]:
        """Return the provider-neutral interface shown to the model."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    """Own Tool registration, schema export, lookup, and execution."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate Tool: {tool.name}")
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown Tool: {name}")
        return tool.handler(**arguments)


# ---------------------------------------------------------------------------
# 3) Agent Runtime
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class AgentResult:
    output: str
    steps: int
    messages: list[dict[str, Any]]


class AgentRuntime:
    """A minimal Decide -> Act -> Observe -> Decide-again Runtime."""

    def __init__(
        self,
        model: Model,
        tools: ToolRegistry,
        *,
        system_prompt: str = "You are a helpful travel assistant.",
        max_steps: int = 6,
    ) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")

        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        self.max_steps = max_steps

    def run(self, user_input: str) -> AgentResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        for step in range(1, self.max_steps + 1):
            # One model turn only. The Runtime keeps ownership of the loop.
            response = self.model.generate(messages, self.tools.schemas())

            # Outcome A: the model proposes one or more external actions.
            if response.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": call.id,
                                "name": call.name,
                                "arguments": call.arguments,
                            }
                            for call in response.tool_calls
                        ],
                    }
                )

                for call in response.tool_calls:
                    observation = self._execute_tool(call)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.name,
                            "content": observation,
                        }
                    )
                continue

            # Outcome B: the model says the task is complete.
            if response.final_answer is not None:
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.final_answer,
                    }
                )
                return AgentResult(
                    output=response.final_answer,
                    steps=step,
                    messages=messages,
                )

            # Guessing what an invalid model response "probably meant" would make
            # the Runtime contract ambiguous. Fail explicitly instead.
            raise RuntimeError(
                "Model returned neither Tool calls nor a final answer"
            )

        raise RuntimeError(f"Agent exceeded max_steps={self.max_steps}")

    def _execute_tool(self, call: ToolCall) -> str:
        try:
            result = self.tools.execute(call.name, call.arguments)
        except Exception:
            # Minimal safe teaching boundary: do not copy an arbitrary exception
            # string into model context. Stage 07 introduces proper failure
            # classification, diagnostics, retry policy, and redaction.
            return "ToolFailure[execution_error]: Tool execution failed."

        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        return str(result)


# ---------------------------------------------------------------------------
# 4) Deterministic travel Tools
# ---------------------------------------------------------------------------


def get_mock_weather(city: str) -> dict[str, Any]:
    """Return deterministic course data, not live weather."""
    if city.lower() != "tokyo":
        raise ValueError("The Stage 01 demo only defines Tokyo mock weather.")

    return {
        "city": "Tokyo",
        "temperature_c": 18.0,
        "condition": "cloudy",
        "source": "course_mock",
    }


def celsius_to_fahrenheit(temperature_c: float) -> float:
    return round(temperature_c * 9 / 5 + 32, 1)


CITY_SCHEMA = {
    "type": "object",
    "properties": {
        "city": {
            "type": "string",
            "description": "City name in English, for example Tokyo.",
        }
    },
    "required": ["city"],
    "additionalProperties": False,
}

TEMPERATURE_SCHEMA = {
    "type": "object",
    "properties": {
        "temperature_c": {
            "type": "number",
            "description": "Temperature in degrees Celsius.",
        }
    },
    "required": ["temperature_c"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# 5) FakeModel: remove model randomness so we can inspect the real Runtime
# ---------------------------------------------------------------------------


class ScriptedTravelModel:
    """Deterministically simulate weather -> conversion -> final answer."""

    def __init__(self) -> None:
        self.turn = 0

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        self.turn += 1

        if self.turn == 1:
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        id="call_weather",
                        name="get_mock_weather",
                        arguments={"city": "Tokyo"},
                    )
                ]
            )

        if self.turn == 2:
            weather = json.loads(messages[-1]["content"])
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        id="call_convert",
                        name="celsius_to_fahrenheit",
                        arguments={
                            "temperature_c": weather["temperature_c"],
                        },
                    )
                ]
            )

        fahrenheit = float(messages[-1]["content"])
        return ModelResponse(
            final_answer=(
                "The course's mock Tokyo weather is 18°C "
                f"(about {fahrenheit:.1f}°F) and cloudy. "
                "This is deterministic course data, not live weather."
            )
        )


# ---------------------------------------------------------------------------
# 6) Read the trajectory, not only the final answer
# ---------------------------------------------------------------------------


def print_trajectory(messages: list[dict[str, Any]]) -> None:
    visible_index = 0

    for message in messages:
        # The system prompt matters to model behavior, but we hide it from this
        # compact trajectory so the Action/Observation loop is easier to inspect.
        if message["role"] == "system":
            continue

        visible_index += 1
        role = message["role"]

        if role == "assistant" and "tool_calls" in message:
            for call in message["tool_calls"]:
                print(
                    f"{visible_index:02d}. ACTION      "
                    f"{call['name']}({call['arguments']}) "
                    f"[id={call['id']}]"
                )
            continue

        if role == "tool":
            print(
                f"{visible_index:02d}. OBSERVATION "
                f"{message['name']} -> {message['content']}"
            )
            continue

        label = "USER" if role == "user" else "ASSISTANT"
        print(
            f"{visible_index:02d}. {label:11s} "
            f"{message.get('content', '')}"
        )


if __name__ == "__main__":
    tools = ToolRegistry(
        [
            Tool(
                name="get_mock_weather",
                description=(
                    "Return the course's deterministic mock weather for one "
                    "city. It does not provide live weather."
                ),
                parameters=CITY_SCHEMA,
                handler=get_mock_weather,
            ),
            Tool(
                name="celsius_to_fahrenheit",
                description="Convert one Celsius temperature to Fahrenheit.",
                parameters=TEMPERATURE_SCHEMA,
                handler=celsius_to_fahrenheit,
            ),
        ]
    )

    runtime = AgentRuntime(
        model=ScriptedTravelModel(),
        tools=tools,
        system_prompt=(
            "You are a travel assistant. The weather Tool returns deterministic "
            "course data, not live weather. Use Tools for retrieval and conversion."
        ),
        max_steps=5,
    )

    result = runtime.run(
        "Use the course's mock Tokyo weather, convert it to Fahrenheit, "
        "and explain the temperature."
    )

    print_trajectory(result.messages)
    print(f"\nsteps={result.steps}")

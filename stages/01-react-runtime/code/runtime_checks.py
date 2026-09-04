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

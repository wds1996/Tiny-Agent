import pytest

from tiny_agent.runtime import AgentRuntime
from tiny_agent.tool import Tool, ToolRegistry
from tiny_agent.types import ModelResponse, ToolCall


class EndlessToolModel:
    """Always asks for the same tool so the runtime must stop it."""

    def __init__(self) -> None:
        self.turn = 0

    def generate(self, messages, tools):
        self.turn += 1
        return ModelResponse(
            tool_calls=[
                ToolCall(
                    id=f"call_{self.turn}",
                    name="echo",
                    arguments={"value": "again"},
                )
            ]
        )


class ErrorAwareModel:
    """Checks that a tool failure is observable on the next model turn."""

    def __init__(self) -> None:
        self.turn = 0

    def generate(self, messages, tools):
        self.turn += 1
        if self.turn == 1:
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        id="call_fail",
                        name="fail",
                        arguments={},
                    )
                ]
            )

        assert messages[-1]["role"] == "tool"
        assert messages[-1]["tool_call_id"] == "call_fail"
        assert messages[-1]["content"].startswith("ToolError[ValueError]:")
        return ModelResponse(final_answer="The tool failed, so I stopped safely.")


class EmptyModel:
    def generate(self, messages, tools):
        return ModelResponse()


def test_runtime_enforces_max_steps():
    tools = ToolRegistry(
        [
            Tool(
                name="echo",
                description="Return a value unchanged.",
                parameters={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                    "additionalProperties": False,
                },
                handler=lambda value: value,
            )
        ]
    )

    runtime = AgentRuntime(
        model=EndlessToolModel(),
        tools=tools,
        max_steps=2,
    )

    with pytest.raises(RuntimeError, match="exceeded max_steps=2"):
        runtime.run("Keep calling the tool forever.")


def test_runtime_returns_tool_error_as_observation_for_stage_01_recovery_demo():
    def fail():
        raise ValueError("demonstration failure")

    runtime = AgentRuntime(
        model=ErrorAwareModel(),
        tools=ToolRegistry(
            [
                Tool(
                    name="fail",
                    description="Always fail for a teaching test.",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                    handler=fail,
                )
            ]
        ),
        max_steps=3,
    )

    result = runtime.run("Demonstrate tool-error recovery.")

    assert result.output == "The tool failed, so I stopped safely."
    assert result.steps == 2


def test_runtime_rejects_model_response_without_action_or_final_answer():
    runtime = AgentRuntime(
        model=EmptyModel(),
        tools=ToolRegistry(),
        max_steps=1,
    )

    with pytest.raises(
        RuntimeError,
        match="neither tool calls nor a final answer",
    ):
        runtime.run("Return an invalid empty model response.")

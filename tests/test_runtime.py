from tiny_agent.runtime import AgentRuntime
from tiny_agent.tool import Tool, ToolRegistry
from tiny_agent.types import ModelResponse, ToolCall


class ScriptedModel:
    """Deterministic fake model used to test the runtime without an API key."""

    def __init__(self) -> None:
        self.turn = 0

    def generate(self, messages, tools):
        self.turn += 1
        if self.turn == 1:
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="calculator",
                        arguments={"a": 12, "b": 7},
                    )
                ]
            )
        assert messages[-1]["role"] == "tool"
        assert messages[-1]["content"] == "19"
        return ModelResponse(final_answer="12 + 7 = 19")


def test_agent_executes_tool_then_finishes():
    calculator = Tool(
        name="calculator",
        description="Add two numbers.",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        handler=lambda a, b: a + b,
    )

    runtime = AgentRuntime(
        model=ScriptedModel(),
        tools=ToolRegistry([calculator]),
        max_steps=3,
    )

    result = runtime.run("What is 12 + 7?")

    assert result.output == "12 + 7 = 19"
    assert result.steps == 2
    assert [m["role"] for m in result.messages] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
    ]

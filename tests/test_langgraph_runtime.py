from tiny_agent.langgraph_runtime import (
    build_langgraph_agent,
    initial_agent_graph_state,
)
from tiny_agent.tool import Tool, ToolRegistry
from tiny_agent.types import ModelResponse, ToolCall


class ScriptedMathModel:
    def __init__(self) -> None:
        self.turn = 0

    def generate(self, messages, tools):
        self.turn += 1

        if self.turn == 1:
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        id="call_mul",
                        name="multiply",
                        arguments={"a": 6, "b": 7},
                    )
                ]
            )

        assert messages[-1]["role"] == "tool"
        assert messages[-1]["content"] == "42"
        return ModelResponse(final_answer="6 * 7 = 42")


class EndlessToolModel:
    def generate(self, messages, tools):
        return ModelResponse(
            tool_calls=[
                ToolCall(
                    id=f"call_{len(messages)}",
                    name="ping",
                    arguments={},
                )
            ]
        )


def test_langgraph_agent_reproduces_react_tool_loop():
    tools = ToolRegistry(
        [
            Tool(
                name="multiply",
                description="Multiply two numbers.",
                parameters={
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                    },
                    "required": ["a", "b"],
                    "additionalProperties": False,
                },
                handler=lambda a, b: a * b,
            )
        ]
    )
    graph = build_langgraph_agent(
        model=ScriptedMathModel(),
        tools=tools,
        max_model_steps=4,
    )

    result = graph.invoke(initial_agent_graph_state("What is 6 * 7?"))

    assert result["final_answer"] == "6 * 7 = 42"
    assert result["error"] is None
    assert result["model_steps"] == 2
    assert [message["role"] for message in result["messages"]] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
    ]


def test_langgraph_agent_keeps_application_owned_model_budget():
    tools = ToolRegistry(
        [
            Tool(
                name="ping",
                description="Return pong.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                handler=lambda: "pong",
            )
        ]
    )
    graph = build_langgraph_agent(
        model=EndlessToolModel(),
        tools=tools,
        max_model_steps=2,
    )

    result = graph.invoke(initial_agent_graph_state("Keep using the tool."))

    assert result["final_answer"] is None
    assert result["error"] == "Agent exceeded max_model_steps=2"
    assert result["model_steps"] == 2


def test_langgraph_agent_surfaces_tool_failure_as_observation_at_this_stage():
    class RecoveringModel:
        def __init__(self):
            self.turn = 0

        def generate(self, messages, tools):
            self.turn += 1
            if self.turn == 1:
                return ModelResponse(
                    tool_calls=[
                        ToolCall(id="call_fail", name="fail", arguments={})
                    ]
                )
            assert messages[-1]["role"] == "tool"
            assert "ToolError[ValueError]" in messages[-1]["content"]
            return ModelResponse(final_answer="The tool failed, so I stopped.")

    tools = ToolRegistry(
        [
            Tool(
                name="fail",
                description="Always fail for this test.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                handler=lambda: (_ for _ in ()).throw(ValueError("demo failure")),
            )
        ]
    )
    graph = build_langgraph_agent(model=RecoveringModel(), tools=tools)

    result = graph.invoke(initial_agent_graph_state("Try the failing tool."))

    assert result["final_answer"] == "The tool failed, so I stopped."

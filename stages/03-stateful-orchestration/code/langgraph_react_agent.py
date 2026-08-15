"""Stage 03 example 3: rebuild the Stage 01 ReAct loop as a LangGraph graph.

This example uses a scripted model so the graph can be inspected without an API
key. The only new concept is orchestration.

Run:

    pip install -e ".[stage03]"
    python stages/03-stateful-orchestration/code/langgraph_react_agent.py
"""

from tiny_agent.langgraph_runtime import (
    build_langgraph_agent,
    initial_agent_graph_state,
)
from tiny_agent.tool import Tool, ToolRegistry
from tiny_agent.types import ModelResponse, ToolCall


class ScriptedModel:
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
                        arguments={"a": 23, "b": 17},
                    )
                ]
            )

        if self.turn == 2:
            assert messages[-1]["role"] == "tool"
            return ModelResponse(
                tool_calls=[
                    ToolCall(
                        id="call_add",
                        name="add",
                        arguments={"a": float(messages[-1]["content"]), "b": 41},
                    )
                ]
            )

        return ModelResponse(final_answer="The final result is 432.")


def multiply(a: float, b: float) -> float:
    return a * b


def add(a: float, b: float) -> float:
    return a + b


NUMBER_PAIR_SCHEMA = {
    "type": "object",
    "properties": {
        "a": {"type": "number"},
        "b": {"type": "number"},
    },
    "required": ["a", "b"],
    "additionalProperties": False,
}


tools = ToolRegistry(
    [
        Tool(
            name="multiply",
            description="Multiply two numbers.",
            parameters=NUMBER_PAIR_SCHEMA,
            handler=multiply,
        ),
        Tool(
            name="add",
            description="Add two numbers.",
            parameters=NUMBER_PAIR_SCHEMA,
            handler=add,
        ),
    ]
)

graph = build_langgraph_agent(
    model=ScriptedModel(),
    tools=tools,
    max_model_steps=6,
)


if __name__ == "__main__":
    initial = initial_agent_graph_state("Calculate (23 * 17) + 41.")

    for update in graph.stream(initial, stream_mode="updates"):
        print(update)

    # ScriptedModel is stateful, so use a fresh graph for a second full invoke.
    final_graph = build_langgraph_agent(
        model=ScriptedModel(),
        tools=tools,
        max_model_steps=6,
    )
    result = final_graph.invoke(initial)

    print("\nFinal answer:")
    print(result["final_answer"])
    print("\nModel steps:")
    print(result["model_steps"])

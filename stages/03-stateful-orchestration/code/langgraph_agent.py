from __future__ import annotations

from dataclasses import dataclass
from operator import add
from typing import Annotated, Any, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ModelTurn:
    final_answer: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


class AgentState(TypedDict, total=False):
    messages: Annotated[list[dict[str, Any]], add]
    pending_tool_calls: list[ToolCall]
    final_answer: str | None
    error: str | None
    model_steps: int


class ScriptedModel:
    """A deterministic model double so graph behavior is easy to inspect."""

    def generate(self, messages: list[dict[str, Any]]) -> ModelTurn:
        tool_messages = [
            message for message in messages if message["role"] == "tool"
        ]
        if not tool_messages:
            return ModelTurn(
                tool_calls=(
                    ToolCall(
                        call_id="call_mul",
                        name="multiply",
                        arguments={"a": 6, "b": 7},
                    ),
                )
            )

        result = tool_messages[-1]["content"]
        return ModelTurn(final_answer=f"6 * 7 = {result}")


TOOLS = {
    "multiply": lambda a, b: a * b,
}


def build_agent_graph(*, max_model_steps: int = 4):
    model = ScriptedModel()

    def model_node(state: AgentState) -> dict:
        steps = state.get("model_steps", 0)
        if steps >= max_model_steps:
            return {
                "error": f"agent exceeded max_model_steps={max_model_steps}",
                "final_answer": None,
                "pending_tool_calls": [],
            }

        turn = model.generate(state["messages"])
        update: dict[str, Any] = {
            "model_steps": steps + 1,
            "pending_tool_calls": list(turn.tool_calls),
        }

        if turn.tool_calls:
            update["messages"] = [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": call.call_id,
                            "name": call.name,
                            "arguments": call.arguments,
                        }
                        for call in turn.tool_calls
                    ],
                }
            ]
        else:
            update["final_answer"] = turn.final_answer
            update["messages"] = [
                {
                    "role": "assistant",
                    "content": turn.final_answer or "",
                }
            ]

        return update

    def route_after_model(
        state: AgentState,
    ) -> Literal["tools", "end"]:
        if state.get("error") is not None:
            return "end"
        if state.get("pending_tool_calls"):
            return "tools"
        return "end"

    def tool_node(state: AgentState) -> dict:
        observations: list[dict[str, Any]] = []

        for call in state.get("pending_tool_calls", []):
            try:
                handler = TOOLS[call.name]
            except KeyError as exc:
                raise RuntimeError(f"unknown tool: {call.name}") from exc

            result = handler(**call.arguments)
            observations.append(
                {
                    "role": "tool",
                    "tool_call_id": call.call_id,
                    "content": str(result),
                }
            )

        return {
            "messages": observations,
            "pending_tool_calls": [],
        }

    builder = StateGraph(AgentState)
    builder.add_node("model", model_node)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "model")
    builder.add_conditional_edges(
        "model",
        route_after_model,
        {
            "tools": "tools",
            "end": END,
        },
    )
    builder.add_edge("tools", "model")

    return builder.compile()


def initial_state(question: str) -> AgentState:
    return {
        "messages": [
            {
                "role": "user",
                "content": question,
            }
        ],
        "pending_tool_calls": [],
        "final_answer": None,
        "error": None,
        "model_steps": 0,
    }


def main() -> None:
    graph = build_agent_graph()
    result = graph.invoke(
        initial_state("What is 6 * 7?"),
        config={"recursion_limit": 20},
    )

    print("final_answer:", result["final_answer"])
    print("model_steps:", result["model_steps"])
    print("message roles:", [message["role"] for message in result["messages"]])


if __name__ == "__main__":
    main()

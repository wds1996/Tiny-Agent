from __future__ import annotations

from dataclasses import dataclass
from operator import add
from typing import Annotated, Any, Literal, Protocol
import math

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

    def __post_init__(self) -> None:
        if (self.final_answer is not None) == bool(self.tool_calls):
            raise ValueError("Return exactly one of final_answer or tool_calls")
        if self.final_answer is not None and not self.final_answer.strip():
            raise ValueError("final_answer must not be blank")
        ids = [call.call_id for call in self.tool_calls]
        if any(not value for value in ids) or len(set(ids)) != len(ids):
            raise ValueError("Tool call IDs must be nonempty and unique")


class Model(Protocol):
    def generate(self, messages: list[dict[str, Any]]) -> ModelTurn: ...


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


def build_agent_graph(*, model: Model | None = None, max_model_steps: int = 4):
    if max_model_steps < 1:
        raise ValueError("max_model_steps must be positive")
    model = model if model is not None else ScriptedModel()

    def model_node(state: AgentState) -> dict:
        steps = state.get("model_steps", 0)
        if steps >= max_model_steps:
            return {
                "error": f"agent exceeded max_model_steps={max_model_steps}",
                "final_answer": None,
                "pending_tool_calls": [],
            }

        turn = model.generate(state["messages"])
        seen = {
            message["tool_call_id"]
            for message in state["messages"]
            if message["role"] == "tool"
        }
        if any(call.call_id in seen for call in turn.tool_calls):
            raise ValueError("Tool call IDs must not repeat across turns")
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

            if set(call.arguments) != {"a", "b"} or any(
                type(value) not in (int, float) or not math.isfinite(value)
                for value in call.arguments.values()
            ):
                raise ValueError("multiply requires exactly two finite numbers: a, b")
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

from __future__ import annotations

import json
import math
import os
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

    def __post_init__(self) -> None:
        if (self.final_answer is not None) == bool(self.tool_calls):
            raise ValueError("Return exactly one of final_answer or tool_calls")
        if self.final_answer is not None and not self.final_answer.strip():
            raise ValueError("final_answer must not be blank")
        call_ids = [call.call_id for call in self.tool_calls]
        if any(not call_id for call_id in call_ids) or len(set(call_ids)) != len(call_ids):
            raise ValueError("Tool call IDs must be nonempty and unique")


class AgentState(TypedDict, total=False):
    messages: Annotated[list[dict[str, Any]], add]
    pending_tool_calls: list[ToolCall]
    final_answer: str | None
    error: str | None
    model_steps: int


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this example.")
    return value


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The OpenAI-compatible Python SDK is not installed. Run:\n"
            "python -m pip install -r "
            "stages/03-stateful-orchestration/code/requirements.txt"
        ) from exc

    return OpenAI(
        api_key=required_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )


MULTIPLY_TOOL = {
    "type": "function",
    "name": "multiply",
    "description": "Multiply two finite numbers. Use for multiplication questions.",
    "parameters": {
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        "required": ["a", "b"],
        "additionalProperties": False,
    },
    "strict": True,
}


class DeepSeekModel:
    """Translate graph state into stateless DeepSeek Responses API requests."""

    def __init__(self, *, client: Any, model: str) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")
        self.client = client
        self.model = model

    def generate(self, messages: list[dict[str, Any]]) -> ModelTurn:
        response = self.client.responses.create(
            model=self.model,
            instructions=(
                "Use multiply for multiplication. Answer only from returned tool "
                "output. Do not invent results or repeat completed calls."
            ),
            input=self._to_input(messages),
            tools=[MULTIPLY_TOOL],
        )
        if response.status != "completed":
            raise RuntimeError(f"DeepSeek response did not complete: {response.status}")

        calls: list[ToolCall] = []
        for item in response.output:
            if item.type != "function_call":
                continue
            try:
                arguments = json.loads(item.arguments)
            except json.JSONDecodeError as exc:
                raise ValueError("Tool arguments are not valid JSON") from exc
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be a JSON object")
            calls.append(ToolCall(item.call_id, item.name, arguments))

        if calls:
            return ModelTurn(tool_calls=tuple(calls))
        return ModelTurn(final_answer=response.output_text)

    @staticmethod
    def _to_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for message in messages:
            if message["role"] == "tool":
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": message["tool_call_id"],
                        "output": message["content"],
                    }
                )
            elif message.get("tool_calls"):
                for call in message["tool_calls"]:
                    items.append(
                        {
                            "type": "function_call",
                            "call_id": call["id"],
                            "name": call["name"],
                            "arguments": json.dumps(call["arguments"]),
                        }
                    )
            else:
                items.append(
                    {"role": message["role"], "content": message["content"]}
                )
        if not items:
            raise ValueError("The model needs at least one input message")
        return items


TOOLS = {"multiply": lambda a, b: a * b}


def build_agent_graph(*, model: DeepSeekModel, max_model_steps: int = 4):
    if max_model_steps < 1:
        raise ValueError("max_model_steps must be positive")

    def model_node(state: AgentState) -> dict[str, Any]:
        steps = state.get("model_steps", 0)
        if steps >= max_model_steps:
            return {
                "error": f"agent exceeded max_model_steps={max_model_steps}",
                "final_answer": None,
                "pending_tool_calls": [],
            }

        turn = model.generate(state["messages"])
        completed_call_ids = {
            message["tool_call_id"]
            for message in state["messages"]
            if message["role"] == "tool"
        }
        if any(call.call_id in completed_call_ids for call in turn.tool_calls):
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
                {"role": "assistant", "content": turn.final_answer or ""}
            ]
        return update

    def route_after_model(state: AgentState) -> Literal["tools", "end"]:
        if state.get("error") is not None:
            return "end"
        return "tools" if state.get("pending_tool_calls") else "end"

    def tool_node(state: AgentState) -> dict[str, Any]:
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
            observations.append(
                {
                    "role": "tool",
                    "tool_call_id": call.call_id,
                    "content": str(handler(**call.arguments)),
                }
            )
        return {"messages": observations, "pending_tool_calls": []}

    builder = StateGraph(AgentState)
    builder.add_node("model", model_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "model")
    builder.add_conditional_edges(
        "model", route_after_model, {"tools": "tools", "end": END}
    )
    builder.add_edge("tools", "model")
    return builder.compile()


def initial_state(question: str) -> AgentState:
    return {
        "messages": [{"role": "user", "content": question}],
        "pending_tool_calls": [],
        "final_answer": None,
        "error": None,
        "model_steps": 0,
    }


def main() -> None:
    model = DeepSeekModel(client=create_client(), model=required_env("DEEPSEEK_MODEL"))
    graph = build_agent_graph(model=model, max_model_steps=4)
    for update in graph.stream(
        initial_state("What is 6 * 7? Use the multiply tool."),
        stream_mode="updates",
        config={"recursion_limit": 20},
    ):
        print(update)
        for values in update.values():
            if values.get("error"):
                raise RuntimeError(values["error"])
            if values.get("final_answer"):
                print("final_answer:", values["final_answer"])


if __name__ == "__main__":
    main()

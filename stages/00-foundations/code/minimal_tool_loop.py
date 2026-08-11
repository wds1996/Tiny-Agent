"""Stage 00: a framework-free minimal tool-use loop.

This file deliberately avoids LangChain/LangGraph/Agent SDKs.  The model is
represented by a tiny scripted fake so the control flow is deterministic and
can be run without API keys.

Run:
    python stages/00-foundations/code/minimal_tool_loop.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolCall:
    """A normalized tool call proposed by a model."""

    name: str
    arguments: dict[str, Any]


@dataclass
class ModelOutput:
    """A minimal model output used by this teaching example."""

    tool_call: ToolCall | None = None
    final_answer: str | None = None


ToolHandler = Callable[..., Any]


def add(a: float, b: float) -> float:
    return a + b


def multiply(a: float, b: float) -> float:
    return a * b


TOOLS: dict[str, ToolHandler] = {
    "add": add,
    "multiply": multiply,
}


class ScriptedModel:
    """A deterministic stand-in for an LLM.

    The purpose is to teach the runtime loop, not provider-specific APIs.
    A real provider adapter would translate its native response into
    ``ModelOutput`` / ``ToolCall`` objects with the same meaning.
    """

    def __init__(self) -> None:
        self.turn = 0

    def generate(self, messages: list[dict[str, Any]]) -> ModelOutput:
        self.turn += 1

        if self.turn == 1:
            return ModelOutput(
                tool_call=ToolCall(
                    name="multiply",
                    arguments={"a": 23, "b": 17},
                )
            )

        if self.turn == 2:
            multiplication_result = messages[-1]["content"]
            return ModelOutput(
                tool_call=ToolCall(
                    name="add",
                    arguments={"a": multiplication_result, "b": 41},
                )
            )

        result = messages[-1]["content"]
        return ModelOutput(final_answer=f"The final result is {result}.")


def execute_tool(call: ToolCall) -> Any:
    """Execute a proposed call on the runtime side.

    Notice that the model never receives the Python callable itself.  It only
    proposes ``name`` and ``arguments``.  The runtime owns the registry and the
    real function execution.
    """

    if call.name not in TOOLS:
        raise ValueError(f"Unknown tool: {call.name}")

    handler = TOOLS[call.name]
    return handler(**call.arguments)


def run_tool_loop(user_input: str, max_steps: int = 8) -> str:
    model = ScriptedModel()
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": user_input},
    ]

    for step in range(1, max_steps + 1):
        output = model.generate(messages)

        if output.final_answer is not None:
            print(f"[step {step}] final: {output.final_answer}")
            return output.final_answer

        if output.tool_call is None:
            raise RuntimeError("Model produced neither a tool call nor a final answer")

        call = output.tool_call
        print(f"[step {step}] action: {call.name}({call.arguments})")

        # Runtime executes the action.
        observation = execute_tool(call)
        print(f"[step {step}] observation: {observation}")

        # The observation becomes new model context.
        messages.append(
            {
                "role": "assistant",
                "tool_call": {
                    "name": call.name,
                    "arguments": call.arguments,
                },
            }
        )
        messages.append(
            {
                "role": "tool",
                "name": call.name,
                "content": observation,
            }
        )

    raise RuntimeError(f"Tool loop exceeded max_steps={max_steps}")


if __name__ == "__main__":
    answer = run_tool_loop("Calculate (23 * 17) + 41")
    assert answer == "The final result is 432."

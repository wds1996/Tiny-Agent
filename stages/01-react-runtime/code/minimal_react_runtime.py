"""Stage 01: a compact ReAct-style Agent runtime.

This snapshot is intentionally self-contained for learning.  The reusable,
evolving implementation lives under ``src/tiny_agent``.

Run:
    python stages/01-react-runtime/code/minimal_react_runtime.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


# ---------------------------------------------------------------------------
# Normalized model/runtime types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ModelResponse:
    final_answer: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class Model(Protocol):
    """Provider-neutral model boundary."""

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        ...


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        return self._tools[name].handler(**arguments)


# ---------------------------------------------------------------------------
# Agent runtime
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class AgentResult:
    output: str
    steps: int
    messages: list[dict[str, Any]]


class AgentRuntime:
    """Minimal action -> observation -> next-decision runtime."""

    def __init__(self, model: Model, tools: ToolRegistry, max_steps: int = 8) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        self.model = model
        self.tools = tools
        self.max_steps = max_steps

    def run(self, user_input: str) -> AgentResult:
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_input}
        ]

        for step in range(1, self.max_steps + 1):
            response = self.model.generate(messages, self.tools.schemas())

            # Outcome A: the model proposes external actions.
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
                    {"role": "assistant", "content": response.final_answer}
                )
                return AgentResult(response.final_answer, step, messages)

            raise RuntimeError(
                "Model returned neither tool calls nor a final answer"
            )

        raise RuntimeError(f"Agent exceeded max_steps={self.max_steps}")

    def _execute_tool(self, call: ToolCall) -> str:
        try:
            return str(self.tools.execute(call.name, call.arguments))
        except Exception as exc:
            # In this first runtime, recoverable tool failures become observations.
            # Later stages will classify errors and attach policies.
            return f"ToolError[{type(exc).__name__}]: {exc}"


# ---------------------------------------------------------------------------
# Deterministic fake model for a runnable demo
# ---------------------------------------------------------------------------


class ScriptedModel:
    """Simulates: multiply -> add -> final answer."""

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
                    ToolCall("call-1", "multiply", {"a": 23, "b": 17})
                ]
            )

        if self.turn == 2:
            previous_observation = float(messages[-1]["content"])
            return ModelResponse(
                tool_calls=[
                    ToolCall("call-2", "add", {"a": previous_observation, "b": 41})
                ]
            )

        return ModelResponse(
            final_answer=f"The final result is {messages[-1]['content']}."
        )


def number_tool(
    name: str,
    description: str,
    handler: Callable[[float, float], float],
) -> Tool:
    return Tool(
        name=name,
        description=description,
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
        },
        handler=handler,
    )


if __name__ == "__main__":
    registry = ToolRegistry(
        [
            number_tool("multiply", "Multiply two numbers.", lambda a, b: a * b),
            number_tool("add", "Add two numbers.", lambda a, b: a + b),
        ]
    )

    agent = AgentRuntime(model=ScriptedModel(), tools=registry)
    result = agent.run("Calculate (23 * 17) + 41")

    print(result.output)
    print(f"steps={result.steps}")

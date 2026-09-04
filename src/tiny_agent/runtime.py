from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reliability import failure_from_exception
from .tool import ToolRegistry
from .types import Model


@dataclass(slots=True)
class AgentResult:
    output: str
    steps: int
    messages: list[dict[str, Any]]


class AgentRuntime:
    """A minimal ReAct-style runtime driven by structured tool calls.

    The model decides whether to call a tool or return a final answer.
    The runtime owns execution, observations, stopping conditions, and errors.

    Stage 09 hardens one legacy boundary here: unexpected tool exception
    messages are no longer copied verbatim into the model transcript. Advanced
    validation, permissions, timeouts, retries, and budgets live in the
    dedicated GuardedToolExecutor rather than bloating this Stage 01 runtime.
    """

    def __init__(
        self,
        model: Model,
        tools: ToolRegistry,
        *,
        system_prompt: str = "You are a helpful agent. Use tools when needed.",
        max_steps: int = 8,
    ) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        self.max_steps = max_steps

    def run(self, user_input: str) -> AgentResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        for step in range(1, self.max_steps + 1):
            response = self.model.generate(messages, self.tools.schemas())

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
                    observation = self._execute_tool(call.name, call.arguments)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.name,
                            "content": observation,
                        }
                    )
                continue

            if response.final_answer is not None:
                messages.append({"role": "assistant", "content": response.final_answer})
                return AgentResult(response.final_answer, step, messages)

            raise RuntimeError("Model returned neither tool calls nor a final answer")

        raise RuntimeError(f"Agent exceeded max_steps={self.max_steps}")

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        try:
            result = self.tools.execute(name, arguments)
            return str(result)
        except Exception as exc:  # observation, not process crash
            return failure_from_exception(exc).observation()

from __future__ import annotations

import json
import os
from typing import Any

from runtime import AgentRuntime, ModelTurn, ToolCall, build_tools


class ProviderResponseError(RuntimeError):
    pass


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Set {name} before running this example.")
    return value.strip()


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI SDK is not installed. Run:\n"
            "python -m pip install -r "
            "stages/01-react-runtime/code/requirements.txt"
        ) from exc

    required_env("OPENAI_API_KEY")
    return OpenAI()


class OpenAIResponsesModel:
    """Translate between the chapter runtime and the OpenAI Responses API.

    One adapter instance represents one run. It chains provider responses with
    previous_response_id and sends only newly produced tool outputs on later turns.
    """

    def __init__(
        self,
        model: str,
        *,
        client: Any | None = None,
        instructions: str = (
            "Use the supplied tools when they are needed. Base the final answer on "
            "tool outputs and do not invent tool results."
        ),
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")
        self.model = model
        self.client = client if client is not None else create_client()
        self.instructions = instructions
        self._previous_response_id: str | None = None
        self._submitted_tool_call_ids: set[str] = set()

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        input_items, pending_call_ids = self._next_input(messages)

        request: dict[str, Any] = {
            "model": self.model,
            "instructions": self.instructions,
            "input": input_items,
            "tools": [self._to_openai_tool(tool) for tool in tools],
            "parallel_tool_calls": False,
        }
        if self._previous_response_id is not None:
            request["previous_response_id"] = self._previous_response_id

        response = self.client.responses.create(**request)
        if response.status != "completed":
            raise ProviderResponseError(
                f"The provider response did not complete: {response.status}"
            )

        response_id = getattr(response, "id", None)
        if not isinstance(response_id, str) or not response_id.strip():
            raise ProviderResponseError("The provider response has no valid ID")

        calls = self._extract_tool_calls(response)
        if calls:
            turn = ModelTurn(tool_calls=tuple(calls))
        else:
            text = response.output_text
            if not text or not text.strip():
                raise ProviderResponseError(
                    "The provider returned neither function calls nor final text"
                )
            turn = ModelTurn(final_text=text)

        self._previous_response_id = response_id
        self._submitted_tool_call_ids.update(pending_call_ids)
        return turn

    def _next_input(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], set[str]]:
        if self._previous_response_id is None:
            initial = [
                {"role": message["role"], "content": message.get("content", "")}
                for message in messages
                if message.get("role") in {"system", "developer", "user"}
            ]
            if not initial:
                raise ProviderResponseError("The first provider turn needs user input")
            return initial, set()

        outputs: list[dict[str, Any]] = []
        pending_call_ids: set[str] = set()
        for message in messages:
            if message.get("role") != "tool":
                continue

            call_id = str(message.get("tool_call_id", ""))
            if not call_id or call_id in self._submitted_tool_call_ids:
                continue

            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": str(message.get("content", "")),
                }
            )
            pending_call_ids.add(call_id)

        if not outputs:
            raise ProviderResponseError(
                "A continued provider turn needs at least one new tool output"
            )
        return outputs, pending_call_ids

    @staticmethod
    def _to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"],
            "strict": True,
        }

    @staticmethod
    def _extract_tool_calls(response: Any) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for item in response.output:
            if item.type != "function_call":
                continue

            try:
                arguments = json.loads(item.arguments)
            except json.JSONDecodeError as exc:
                raise ProviderResponseError(
                    f"Arguments for function {item.name!r} are not valid JSON"
                ) from exc
            if not isinstance(arguments, dict):
                raise ProviderResponseError(
                    f"Arguments for function {item.name!r} must be a JSON object"
                )

            calls.append(
                ToolCall(
                    call_id=item.call_id,
                    name=item.name,
                    arguments=arguments,
                )
            )
        return calls


def main() -> None:
    model = OpenAIResponsesModel(model=required_env("OPENAI_MODEL"))
    runtime = AgentRuntime(
        model=model,
        tools=build_tools(),
        max_steps=6,
        verbose=True,
    )
    result = runtime.run(
        "Read Tokyo's teaching weather and convert its temperature to Fahrenheit."
    )
    print("\nfinal_answer:", result.answer)


if __name__ == "__main__":
    main()

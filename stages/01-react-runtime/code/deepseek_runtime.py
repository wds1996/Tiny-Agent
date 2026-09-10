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
            "The OpenAI-compatible Python SDK is not installed. Run:\n"
            "python -m pip install -r "
            "stages/01-react-runtime/code/requirements.txt"
        ) from exc

    return OpenAI(
        api_key=required_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )


class DeepSeekResponsesModel:
    """Translate between the chapter runtime and the DeepSeek Responses API.

    DeepSeek's Responses API is stateless, so every request is rebuilt from the
    complete transcript maintained by AgentRuntime.
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

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        request: dict[str, Any] = {
            "model": self.model,
            "instructions": self.instructions,
            "input": self._to_deepseek_input(messages),
            "tools": [self._to_deepseek_tool(tool) for tool in tools],
        }

        response = self.client.responses.create(**request)
        if response.status != "completed":
            raise ProviderResponseError(
                f"The provider response did not complete: {response.status}"
            )

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

        return turn

    @staticmethod
    def _to_deepseek_input(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        input_items: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            if role in {"system", "developer", "user"}:
                input_items.append(
                    {"role": role, "content": str(message.get("content", ""))}
                )
                continue

            if role == "assistant":
                content = str(message.get("content", ""))
                if content:
                    input_items.append({"role": "assistant", "content": content})
                for call in message.get("tool_calls", []):
                    input_items.append(
                        {
                            "type": "function_call",
                            "call_id": str(call["call_id"]),
                            "name": str(call["name"]),
                            "arguments": json.dumps(
                                call["arguments"], ensure_ascii=False
                            ),
                        }
                    )
                continue

            if role == "tool":
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": str(message.get("tool_call_id", "")),
                        "output": str(message.get("content", "")),
                    }
                )

        if not input_items:
            raise ProviderResponseError("The provider turn needs at least one input")
        return input_items

    @staticmethod
    def _to_deepseek_tool(tool: dict[str, Any]) -> dict[str, Any]:
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


def format_conversation(
    *,
    instructions: str,
    messages: tuple[dict[str, Any], ...],
) -> str:
    """Render the provider-neutral runtime history after the debug trace."""

    lines = ["=== reconstructed model conversation ===", "system (instructions):"]
    lines.append(f"  {instructions}")

    for message in messages:
        role = message["role"]
        if role == "assistant" and message.get("tool_calls"):
            lines.append("assistant (tool calls):")
            for call in message["tool_calls"]:
                arguments = json.dumps(
                    call["arguments"], ensure_ascii=False, sort_keys=True
                )
                lines.append(
                    f"  {call['name']}({arguments}) "
                    f"[call_id={call['call_id']}]"
                )
        elif role == "tool":
            lines.append(
                f"tool ({message['tool_call_id']}): {message['content']}"
            )
        else:
            lines.append(f"{role}: {message.get('content', '')}")

    return "\n".join(lines)


def main() -> None:
    model = DeepSeekResponsesModel(model=required_env("DEEPSEEK_MODEL"))
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
    print()
    print(format_conversation(instructions=model.instructions, messages=result.messages))


if __name__ == "__main__":
    main()

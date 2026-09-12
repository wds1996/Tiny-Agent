"""Use DeepSeek Responses with the same runtime as the offline exercise."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from typing import Any

from runtime import (
    AgentRuntimeError, InvalidModelTurnError, ModelTurn, ToolCall,
    parse_args, run_exercise,
)


class ProviderResponseError(AgentRuntimeError):
    pass


INSTRUCTIONS = (
    "Help with the current request. Teaching weather is fixed local data, not live weather. "
    "For weather, use get_teaching_weather instead of guessing. When Fahrenheit is requested, "
    "first obtain the reading, then pass that observed Celsius number to celsius_to_fahrenheit. "
    "Do not request a dependent calculation before its input is available. For a greeting, "
    "answer without tools. Answer in the user's language, based only on supplied observations. "
    "A tool request is not a result. Never claim an action completed before receiving its output."
)


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running the live example.")
    return value


def create_client() -> Any:
    api_key = required_env("DEEPSEEK_API_KEY")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Install: python -m pip install -r stages/01-react-runtime/code/requirements.txt"
        ) from exc
    return OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=30.0,
        max_retries=0,
    )


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("Non-finite JSON constant.")


def parse_arguments(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str) or len(raw) > 16_000:
        raise ProviderResponseError("Tool arguments must be bounded JSON text.")
    try:
        arguments = json.loads(raw, object_pairs_hook=_unique_fields, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise ProviderResponseError("Tool arguments are not an unambiguous JSON object.") from exc
    if not isinstance(arguments, dict):
        raise ProviderResponseError("Tool arguments must decode to an object.")
    return arguments


class DeepSeekResponsesModel:
    """Stateless adapter: continuation items travel with their owning run's messages."""

    def __init__(self, model: str, *, client: Any | None = None, instructions: str = INSTRUCTIONS) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string.")
        self.model = model
        self.client = client if client is not None else create_client()
        self.instructions = instructions

    def generate(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelTurn:
        request = {
            "model": self.model,
            "instructions": self.instructions,
            "input": self._to_deepseek_input(messages),
            "tools": [self._to_deepseek_tool(tool) for tool in tools],
            "tool_choice": "auto",
            "max_output_tokens": 4096,
        }
        try:
            response = self.client.responses.create(**request)
        except Exception as exc:
            # Keep the cause for controlled debugging, not in the printed user message.
            raise ProviderResponseError("Model request failed; no automatic retry was made.") from exc
        if getattr(response, "status", None) != "completed":
            raise ProviderResponseError("Model response did not complete; no calls will execute.")
        output = getattr(response, "output", None)
        if not isinstance(output, list):
            raise ProviderResponseError("Model response has no output-item list.")
        calls: list[ToolCall] = []
        for item in output:
            kind = getattr(item, "type", None)
            if kind not in {"function_call", "message", "reasoning"}:
                raise ProviderResponseError("Unexpected provider output type for this example.")
            if kind == "function_call":
                if getattr(item, "status", "completed") not in {None, "completed"}:
                    raise ProviderResponseError("An individual tool call did not complete.")
                try:
                    calls.append(ToolCall(
                        call_id=getattr(item, "call_id", None),
                        name=getattr(item, "name", None),
                        arguments=parse_arguments(getattr(item, "arguments", None)),
                    ))
                except InvalidModelTurnError as exc:
                    raise ProviderResponseError("Malformed tool-call identity.") from exc
        try:
            provider_items = tuple(item.model_dump(mode="json", exclude_none=True) for item in output)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ProviderResponseError("Could not preserve the provider's continuation items.") from exc
        if calls:
            # Accompanying text is not treated as a final answer while actions are pending.
            return ModelTurn(tool_calls=tuple(calls), provider_items=provider_items)
        text = getattr(response, "output_text", None)
        if not isinstance(text, str) or not text.strip():
            raise ProviderResponseError("Completed response has neither calls nor usable text.")
        return ModelTurn(final_text=text.strip(), provider_items=provider_items)

    @staticmethod
    def _to_deepseek_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            if role == "assistant" and message.get("provider_items"):
                items.extend(deepcopy(message["provider_items"]))
            elif role == "assistant" and message.get("tool_calls"):
                # A scripted transcript can also be translated, without SDK objects.
                for call in message["tool_calls"]:
                    items.append({
                        "type": "function_call", "call_id": call["call_id"],
                        "name": call["name"],
                        "arguments": json.dumps(call["arguments"], ensure_ascii=False, allow_nan=False),
                    })
            elif role == "tool":
                items.append({
                    "type": "function_call_output",
                    "call_id": message["tool_call_id"],
                    "output": message["content"],
                })
            elif role in {"user", "assistant"}:
                items.append({"role": role, "content": message["content"]})
            else:
                raise ProviderResponseError("Unexpected internal message role.")
        if not items:
            raise ProviderResponseError("A model turn needs input.")
        return items

    @staticmethod
    def _to_deepseek_tool(tool: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function", "name": tool["name"],
            "description": tool["description"], "parameters": tool["parameters"],
        }


def main() -> int:
    args = parse_args("Live DeepSeek weather exercise; requires credentials and incurs API usage.")
    try:
        model = DeepSeekResponsesModel(required_env("DEEPSEEK_MODEL"))
    except (RuntimeError, ValueError) as exc:
        print(f"Configuration error: {exc}")
        return 1
    print("=== 真实 DeepSeek / live DeepSeek: API usage applies ===")
    try:
        return run_exercise(model, args)
    finally:
        model.client.close()


if __name__ == "__main__":
    raise SystemExit(main())

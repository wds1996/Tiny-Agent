"""Stateless DeepSeek Responses adapter; graph orchestration stays in agent_graph."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from typing import Any

from agent_graph import ModelTurn, ToolCall, parse_agent_args, run_demo, tool_definitions

INSTRUCTIONS = (
    "Help with fixed teaching weather records, not live weather. Use get_teaching_weather "
    "for requested records. When Fahrenheit is requested, pass the returned Celsius value "
    "to celsius_to_fahrenheit. Do not invent records or report execution before a tool result. "
    "Answer in the user's requested language. A greeting needs no tool."
)


class ProviderResponseError(RuntimeError):
    pass


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running the live example")
    return value


def create_client() -> Any:
    key = required_env("DEEPSEEK_API_KEY")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install stages/03-stateful-orchestration/code/requirements.txt first") from exc
    return OpenAI(api_key=key, base_url="https://api.deepseek.com", timeout=30.0, max_retries=0)


def to_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for message in messages:
        if message["role"] == "tool":
            items.append({"type": "function_call_output", "call_id": message["tool_call_id"],
                          "output": message["content"]})
        elif message.get("provider_items"):
            items.extend(deepcopy(message["provider_items"]))
        elif message.get("tool_calls"):
            for call in message["tool_calls"]:
                items.append({"type": "function_call", "call_id": call["call_id"], "name": call["name"],
                              "arguments": json.dumps(call["arguments"], ensure_ascii=False, allow_nan=False)})
        elif message["role"] in {"user", "assistant", "system"}:
            items.append({"role": message["role"], "content": message["content"]})
        else:
            raise ProviderResponseError("Unknown message role")
    if not items:
        raise ProviderResponseError("No model input")
    return items


def parse_response(response: Any) -> ModelTurn:
    if getattr(response, "status", None) != "completed":
        raise ProviderResponseError("Provider response did not complete")
    output = response.output
    if not isinstance(output, list):
        raise ProviderResponseError("Output must be an item list")
    calls = []
    try:
        for item in output:
            if item.type == "function_call":
                if not isinstance(item.arguments, str) or len(item.arguments) > 4096:
                    raise ValueError("Invalid argument encoding")
                arguments = json.loads(item.arguments)
                calls.append(ToolCall(item.call_id, item.name, arguments))
        provider_items = tuple(item.model_dump(mode="json", exclude_none=True) for item in output)
        if calls:
            return ModelTurn(tool_calls=tuple(calls), provider_items=provider_items)
        return ModelTurn(final_answer=response.output_text, provider_items=provider_items)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProviderResponseError("Invalid provider output") from exc


class DeepSeekModel:
    def __init__(self, *, client: Any, model: str) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be nonempty text")
        self.client, self.model = client, model

    def generate(self, messages: list[dict[str, Any]]) -> ModelTurn:
        response = self.client.responses.create(
            model=self.model, instructions=INSTRUCTIONS, input=to_input(messages),
            tools=tool_definitions(), max_output_tokens=4096,
        )
        return parse_response(response)


def main() -> None:
    args = parse_agent_args()
    model_name = required_env("DEEPSEEK_MODEL")
    print("live DeepSeek; API usage applies; no offline fallback")
    client = create_client()
    try:
        state = run_demo(DeepSeekModel(client=client, model=model_name), args)
    finally:
        client.close()
    if state["error"] is not None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

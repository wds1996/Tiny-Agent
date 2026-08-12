from __future__ import annotations

import json
from typing import Any, Literal

from ..types import ModelResponse, ToolCall


class OpenAIResponsesModel:
    """Adapter from Tiny-Agent's provider-neutral model interface to OpenAI Responses.

    Stage 01 intentionally keeps this adapter stateless: every call translates the
    complete Tiny-Agent transcript into Responses API input items. To make that
    teaching model straightforward, the default reasoning effort is ``none``.

    Later stages introduce provider-native conversation state, persisted reasoning,
    previous_response_id, retries, tracing, and asynchronous execution.
    """

    def __init__(
        self,
        model: str = "gpt-5.6-luna",
        *,
        reasoning_effort: Literal[
            "none", "low", "medium", "high", "xhigh", "max"
        ] = "none",
        strict_tools: bool = True,
        parallel_tool_calls: bool = True,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.strict_tools = strict_tools
        self.parallel_tool_calls = parallel_tool_calls

        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - environment dependent
                raise RuntimeError(
                    "OpenAI support is optional. Install it with "
                    '`pip install -e ".[openai]"`.'
                ) from exc
            client = OpenAI()

        self.client = client

    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        """Run one model turn and normalize the provider response.

        The runtime owns iteration and tool execution. This method performs exactly
        one model request, then translates OpenAI-specific output items into the
        provider-neutral ``ModelResponse`` used by Tiny-Agent.
        """

        response = self.client.responses.create(
            model=self.model,
            input=self._to_openai_input(messages),
            tools=[self._to_openai_tool(tool) for tool in tools],
            reasoning={"effort": self.reasoning_effort},
            parallel_tool_calls=self.parallel_tool_calls,
        )

        tool_calls = self._extract_tool_calls(response)
        if tool_calls:
            return ModelResponse(tool_calls=tool_calls)

        output_text = getattr(response, "output_text", None)
        if output_text is None or not str(output_text).strip():
            raise RuntimeError(
                "OpenAI response contained neither function calls nor output text"
            )

        return ModelResponse(final_answer=str(output_text))

    def _to_openai_tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        """Translate a Tiny-Agent tool schema to a Responses function tool."""

        required = {"name", "description", "parameters"}
        missing = required.difference(tool)
        if missing:
            raise ValueError(f"Tool schema missing fields: {sorted(missing)}")

        return {
            "type": "function",
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"],
            "strict": self.strict_tools,
        }

    @staticmethod
    def _to_openai_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Translate the normalized Tiny-Agent transcript to Responses input items.

        Tiny-Agent keeps its own transcript format so the core runtime is not tied
        to one provider. The adapter is the compatibility boundary.
        """

        input_items: list[dict[str, Any]] = []

        for message in messages:
            role = message.get("role")

            if role in {"system", "developer", "user"}:
                input_items.append(
                    {
                        "role": role,
                        "content": message.get("content", ""),
                    }
                )
                continue

            if role == "assistant":
                content = message.get("content")
                if content:
                    input_items.append({"role": "assistant", "content": content})

                for call in message.get("tool_calls", []):
                    input_items.append(
                        {
                            "type": "function_call",
                            "call_id": call["id"],
                            "name": call["name"],
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
                        "call_id": message["tool_call_id"],
                        "output": str(message.get("content", "")),
                    }
                )
                continue

            raise ValueError(f"Unsupported Tiny-Agent message role: {role!r}")

        return input_items

    @staticmethod
    def _extract_tool_calls(response: Any) -> list[ToolCall]:
        """Normalize all function_call output items from one Responses turn."""

        calls: list[ToolCall] = []

        for item in getattr(response, "output", []):
            if getattr(item, "type", None) != "function_call":
                continue

            raw_arguments = getattr(item, "arguments", "{}")
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Model returned invalid JSON arguments for tool "
                    f"{getattr(item, 'name', '<unknown>')!r}: {raw_arguments!r}"
                ) from exc

            if not isinstance(arguments, dict):
                raise RuntimeError(
                    "Function-call arguments must decode to a JSON object, "
                    f"got {type(arguments).__name__}"
                )

            calls.append(
                ToolCall(
                    id=item.call_id,
                    name=item.name,
                    arguments=arguments,
                )
            )

        return calls

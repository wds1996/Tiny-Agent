"""Real DeepSeek calls are the default. Test doubles are injected explicitly."""
from __future__ import annotations

import os
from typing import Any

from domain import BoundaryError, encode, object_from_json, text


class DeepSeekModel:
    def __init__(self, *, client: Any = None, model: str | None = None):
        self.client = client
        self.model = model or os.getenv("DEEPSEEK_MODEL", "").strip()

    def _client(self):
        if self.client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise RuntimeError("Install code/requirements.txt for live DeepSeek.") from exc
            key = os.getenv("DEEPSEEK_API_KEY", "").strip()
            if not key or not self.model:
                raise BoundaryError("deepseek_credentials_or_model_missing")
            self.client = AsyncOpenAI(
                api_key=key,
                base_url="https://api.deepseek.com",
                timeout=40,
                max_retries=0,
            )
        return self.client

    async def call(
        self, *, purpose: str, instructions: str, payload: dict, budget,
        tools: list | None = None, history: list | None = None,
    ) -> dict:
        client = self._client()
        serialized = encode(payload)
        if len(serialized) + len(encode(history or [])) > 36_000:
            raise BoundaryError("context_character_budget_exceeded")
        budget("model")  # Charge before sending, even if the response is lost.
        kwargs = dict(
            model=self.model,
            temperature=0.1,
            max_tokens=2400,
            extra_body={"thinking": {"type": "disabled"}},
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": serialized},
                *(history or []),
            ],
        )
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")
        else:
            kwargs["response_format"] = {"type": "json_object"}
        response = await client.chat.completions.create(**kwargs)
        if not response.choices:
            raise BoundaryError("empty_model_response")
        choice = response.choices[0]
        if choice.finish_reason not in {"stop", "tool_calls"}:
            raise BoundaryError("incomplete_model_response")
        message = choice.message
        calls = []
        for call in message.tool_calls or []:
            if call.type != "function":
                raise BoundaryError("unexpected_call_type")
            calls.append({
                "id": text(call.id, maximum=100),
                "name": text(call.function.name, maximum=80),
                "arguments": object_from_json(call.function.arguments, limit=6000),
            })
        if len(calls) > 4 or len({c["id"] for c in calls}) != len(calls):
            raise BoundaryError("invalid_tool_batch")
        usage = response.usage
        assistant = {"role": "assistant", "content": message.content or None}
        if calls:
            assistant["tool_calls"] = [
                {"id": c["id"], "type": "function", "function": {
                    "name": c["name"], "arguments": encode(c["arguments"]),
                }} for c in calls
            ]
        return {
            "text": message.content or "",
            "calls": calls,
            "assistant": assistant,
            "usage": None if usage is None else {
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
            },
        }

    async def close(self):
        if self.client is not None and hasattr(self.client, "close"):
            await self.client.close()

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from tiny_agent_mcp_bridge import AsyncToolRegistry, DEFAULT_ALLOWED_TOOLS, MCPToolBridge


INSTRUCTIONS = (
    "You are handling one fictional Acme support inquiry. Use only the available "
    "read-only tools when system facts are needed. Distinguish verified tool results "
    "from policy interpretation. Never claim that a refund or support case was created."
)


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this example.")
    return value


def create_model_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Install Stage 05 dependencies first:\n"
            "python -m pip install -r stages/05-mcp/code/requirements.txt"
        ) from exc
    return OpenAI(
        api_key=required_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        timeout=30.0,
        max_retries=0,
    )


def function_tools(registry: AsyncToolRegistry) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": schema["name"],
            "description": schema["description"],
            "parameters": schema["parameters"],
        }
        for schema in registry.schemas()
    ]


async def run_agent(registry: AsyncToolRegistry, *, max_model_turns: int = 4) -> str:
    if max_model_turns < 1:
        raise ValueError("max_model_turns must be positive")

    model_client = create_model_client()
    model = required_env("DEEPSEEK_MODEL")
    history: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                "Verify teaching order ACME-1007. Tell me the placed date, paid amount, "
                "and shipment status. Use tools for system facts."
            ),
        }
    ]

    for _ in range(max_model_turns):
        response = model_client.responses.create(
            model=model,
            instructions=INSTRUCTIONS,
            input=history,
            tools=function_tools(registry),
            max_output_tokens=4096,
        )
        if response.status != "completed":
            raise RuntimeError(f"DeepSeek response did not complete: {response.status}")

        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            answer = response.output_text.strip()
            if not answer:
                raise RuntimeError("DeepSeek completed without tool calls or usable text")
            return answer

        history.extend(
            item.model_dump(mode="json", exclude_none=True) for item in response.output
        )
        for call in calls:
            try:
                arguments = json.loads(call.arguments)
            except json.JSONDecodeError as exc:
                raise RuntimeError("DeepSeek returned invalid tool argument JSON") from exc
            if not isinstance(arguments, dict):
                raise RuntimeError("tool arguments must decode to a JSON object")
            result = await registry.execute(call.name, arguments)
            history.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result, ensure_ascii=False),
                }
            )

    raise RuntimeError(f"Agent did not finish within max_model_turns={max_model_turns}")


async def main() -> None:
    try:
        from mcp import Client
    except ImportError as exc:
        raise RuntimeError(
            "Install Stage 05 dependencies first:\n"
            "python -m pip install -r stages/05-mcp/code/requirements.txt"
        ) from exc
    from mcp_server import mcp

    registry = AsyncToolRegistry()
    async with Client(mcp) as mcp_client:
        await MCPToolBridge(
            mcp_client,
            namespace="support",
            allowed_remote_tools=DEFAULT_ALLOWED_TOOLS,
        ).populate(registry)
        print("model-visible tools:", [schema["name"] for schema in registry.schemas()])
        print("live DeepSeek: API usage applies")
        answer = await run_agent(registry)
        print("answer:", answer)


if __name__ == "__main__":
    asyncio.run(main())

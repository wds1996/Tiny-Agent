from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

from guardrails import (
    ExecutionBudget,
    ExecutionContext,
    GuardedExecutor,
    PermissionPolicy,
    Principal,
    ToolSpec,
)


SYSTEM_INSTRUCTIONS = """You are a support Agent. You may propose Tool Calls when they help answer the user.
Every Tool Call is checked by the Host for argument validity, the current caller's permissions,
budget, deadlines, and retry policy. A Tool Result reports the Host's decision. Do not claim an
action succeeded unless its Tool Result says ok is true. If a request is denied, explain the
limitation and do not invent a workaround."""


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this example.")
    return value


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Install Stage 09 dependencies first:\n"
            "python -m pip install -r stages/09-reliability-safety/code/requirements.txt"
        ) from exc
    return OpenAI(
        api_key=required_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        timeout=30.0,
        max_retries=2,
    )


def lookup_order(*, context: ExecutionContext, order_id: str) -> dict[str, str]:
    context.check_deadline()
    return {"order_id": order_id, "status": "paid"}


def issue_refund(
    *,
    context: ExecutionContext,
    order_id: str,
    amount: str,
) -> dict[str, str]:
    context.check_deadline()
    return {"order_id": order_id, "amount": amount, "status": "refunded"}


def build_executor() -> GuardedExecutor:
    tools = [
        ToolSpec("lookup_order", {"order_id": str}, lookup_order, safe_to_retry=True),
        ToolSpec("issue_refund", {"order_id": str, "amount": str}, issue_refund),
    ]
    return GuardedExecutor(
        tools,
        permissions=PermissionPolicy(
            {
                "support": {"lookup_order"},
                "refund_manager": {"lookup_order", "issue_refund"},
            }
        ),
    )


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "lookup_order",
                "description": "Look up an order by its exact ORDER-<digits> identifier.",
                "parameters": {
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "issue_refund",
                "description": "Issue a refund only when the Host authorizes this principal.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "amount": {"type": "string"},
                    },
                    "required": ["order_id", "amount"],
                    "additionalProperties": False,
                },
            },
        },
    ]


def tool_result(result: Any) -> str:
    return json.dumps(
        {
            "ok": result.ok,
            "value": result.value if result.ok else None,
            "error": result.error if not result.ok else None,
            "attempts": result.attempts,
        },
        ensure_ascii=False,
    )


def dispatch_tool_call(
    *,
    executor: GuardedExecutor,
    principal: Principal,
    budget: ExecutionBudget,
    context: ExecutionContext,
    call: Any,
) -> tuple[str, str]:
    try:
        arguments = json.loads(call.function.arguments)
    except json.JSONDecodeError:
        return call.function.name, json.dumps(
            {"ok": False, "error": "invalid JSON tool arguments", "attempts": 0}
        )
    if not isinstance(arguments, dict):
        return call.function.name, json.dumps(
            {"ok": False, "error": "tool arguments must be an object", "attempts": 0}
        )
    result = executor.execute(
        principal=principal,
        tool_name=call.function.name,
        arguments=arguments,
        budget=budget,
        context=context,
    )
    return call.function.name, tool_result(result)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send DeepSeek Tool Calls through the Stage 09 GuardedExecutor."
    )
    parser.add_argument(
        "--task",
        default="Look up ORDER-42, then refund 10.00 for it.",
        help="User task supplied to DeepSeek.",
    )
    parser.add_argument(
        "--role",
        choices=("support", "refund_manager"),
        default="support",
        help="Role checked by the Host before every Tool execution.",
    )
    args = parser.parse_args()

    client = create_client()
    model = required_env("DEEPSEEK_MODEL")
    principal = Principal("demo-user", frozenset({args.role}))
    executor = build_executor()
    budget = ExecutionBudget(max_tool_calls=6, max_retries=1, max_same_call=2)
    context = ExecutionContext(deadline_monotonic=time.monotonic() + 30.0)
    messages: list[Any] = [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        {"role": "user", "content": args.task},
    ]

    print("=== user ===")
    print(args.task)
    print("=== Host principal ===")
    print(f"id={principal.id}, roles={sorted(principal.roles)}")

    for _ in range(4):
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=messages,
            tools=tool_definitions(),
            tool_choice="auto",
        )
        if not response.choices:
            raise RuntimeError("DeepSeek did not return a response.")
        message = response.choices[0].message
        messages.append(message)
        if not message.tool_calls:
            if message.content is None or not message.content.strip():
                raise RuntimeError("DeepSeek returned empty final text.")
            print("=== assistant ===")
            print(message.content.strip())
            return

        for call in message.tool_calls:
            name, content = dispatch_tool_call(
                executor=executor,
                principal=principal,
                budget=budget,
                context=context,
                call=call,
            )
            print("=== tool call ===")
            print(f"{name}({call.function.arguments})")
            print("=== Host guarded result ===")
            print(content)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    raise RuntimeError("model exceeded the demonstration's maximum tool rounds")


if __name__ == "__main__":
    main()

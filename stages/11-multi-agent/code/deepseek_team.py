from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from typing import Any, Mapping

from team import (
    AgentMessage,
    Delegation,
    Principal,
    Specialist,
    TeamBudget,
    TeamPolicy,
    TeamRuntime,
)


SUPERVISOR_INSTRUCTIONS = """You are a customer-support supervisor.
Delegate only when a specialist's result is needed to answer the user. The Host offers
one delegate_to_specialist tool. Call it with either orders or policy and a concise
subtask. Use returned specialist results as evidence. Do not claim that a specialist
ran unless a Tool Result says it completed. Give the final answer yourself."""

SPECIALIST_INSTRUCTIONS = {
    "orders": "You are the order specialist. Answer only from the supplied task and context.",
    "policy": "You are the policy specialist. Answer only from the supplied task and context.",
}


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
            "Install Stage 11 dependencies first:\n"
            "python -m pip install -r stages/11-multi-agent/code/requirements.txt"
        ) from exc
    return OpenAI(
        api_key=required_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        timeout=30.0,
        max_retries=2,
    )


@dataclass(slots=True)
class DeepSeekSpecialist:
    name: str
    client: Any
    model: str

    def run(self, task: str, context: Mapping[str, str]) -> AgentMessage:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": SPECIALIST_INSTRUCTIONS[self.name]},
                {
                    "role": "user",
                    "content": (
                        f"Task:\n{task}\n\n"
                        "<projected_context>\n"
                        f"{json.dumps(context, ensure_ascii=False)}\n"
                        "</projected_context>"
                    ),
                },
            ],
        )
        if not response.choices or not response.choices[0].message.content:
            raise RuntimeError(f"{self.name} returned empty text")
        return AgentMessage(
            agent=self.name,
            task=task,
            status="completed",
            summary=response.choices[0].message.content.strip(),
            data=dict(context),
            provenance=(f"deepseek:{self.model}", f"specialist:{self.name}"),
        )


def delegation_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "delegate_to_specialist",
            "description": "Ask the orders or policy specialist to complete one focused subtask.",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialist": {"type": "string", "enum": ["orders", "policy"]},
                    "task": {"type": "string"},
                },
                "required": ["specialist", "task"],
                "additionalProperties": False,
            },
        },
    }


CONTEXT_KEYS_BY_SPECIALIST = {
    "orders": ("order_id",),
    "policy": ("policy_excerpt",),
}


def dispatch_delegation(
    *,
    runtime: TeamRuntime,
    principal: Principal,
    budget: TeamBudget,
    context: Mapping[str, str],
    call: Any,
) -> str:
    try:
        arguments = json.loads(call.function.arguments)
    except json.JSONDecodeError:
        return json.dumps({"ok": False, "error": "invalid JSON arguments"})
    if not isinstance(arguments, dict):
        return json.dumps({"ok": False, "error": "arguments must be an object"})
    specialist = arguments.get("specialist")
    task = arguments.get("task")
    if specialist not in CONTEXT_KEYS_BY_SPECIALIST or not isinstance(task, str):
        return json.dumps({"ok": False, "error": "invalid specialist or task"})

    try:
        result = runtime.delegate(
            caller="supervisor",
            principal=principal,
            delegation=Delegation(specialist, task, CONTEXT_KEYS_BY_SPECIALIST[specialist]),
            shared_context=context,
            budget=budget,
        )
    except (KeyError, PermissionError, RuntimeError, ValueError) as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    return json.dumps(
        {
            "ok": True,
            "agent": result.agent,
            "status": result.status,
            "summary": result.summary,
            "provenance": result.provenance,
        },
        ensure_ascii=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a DeepSeek supervisor that delegates to DeepSeek specialists."
    )
    parser.add_argument(
        "--task",
        default="Can ORDER-42 use the original payment method for a refund?",
        help="User task sent to the supervisor.",
    )
    args = parser.parse_args()
    model = required_env("DEEPSEEK_MODEL")
    client = create_client()
    runtime = TeamRuntime(
        [
            Specialist("supervisor", "supervisor placeholder"),
            DeepSeekSpecialist("orders", client, model),
            DeepSeekSpecialist("policy", client, model),
        ],
        policy=TeamPolicy({"support": frozenset({"orders", "policy"})}),
    )
    principal = Principal("demo-user", frozenset({"support"}))
    budget = TeamBudget(max_delegations=2, max_handoffs=0)
    shared_context = {
        "order_id": "ORDER-42",
        "policy_excerpt": "Refunds within 30 days may use the original payment method.",
        "internal_secret": "must-not-reach-specialists",
    }
    messages: list[Any] = [
        {"role": "system", "content": SUPERVISOR_INSTRUCTIONS},
        {"role": "user", "content": args.task},
    ]

    print("=== user ===")
    print(args.task)
    for _ in range(4):
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=messages,
            tools=[delegation_tool()],
            tool_choice="auto",
        )
        if not response.choices:
            raise RuntimeError("DeepSeek supervisor did not return a response.")
        message = response.choices[0].message
        messages.append(message)
        if not message.tool_calls:
            if message.content is None or not message.content.strip():
                raise RuntimeError("DeepSeek supervisor returned empty final text.")
            print("=== supervisor final ===")
            print(message.content.strip())
            break

        for call in message.tool_calls:
            content = dispatch_delegation(
                runtime=runtime,
                principal=principal,
                budget=budget,
                context=shared_context,
                call=call,
            )
            print("=== delegation ===")
            print(call.function.arguments)
            print("=== specialist result ===")
            print(content)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
    else:
        raise RuntimeError("supervisor exceeded the demonstration's maximum tool rounds")

    print("=== structured team events ===")
    for event in runtime.events:
        print(event)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Callable

from evaluation import AgentRun, EvalCase, score_case
from tracing import CapturePolicy, Trace, Tracer, format_trace


SYSTEM_INSTRUCTIONS = """You are a customer-support Agent.
Use the available tools when their results are needed. Answer only from tool results.
If the available evidence cannot answer the question, say that you do not have enough
evidence. Do not claim a Tool succeeded unless the Host returned its result."""


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
            "Install Stage 10 dependencies first:\n"
            "python -m pip install -r stages/10-evaluation-observability/code/requirements.txt"
        ) from exc
    return OpenAI(
        api_key=required_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        timeout=30.0,
        max_retries=2,
    )


def lookup_order(*, order_id: str) -> dict[str, Any]:
    return {
        "order_id": order_id,
        "status": "delivered",
        "days_since_delivery": 7,
    }


def search_refund_policy() -> dict[str, str]:
    return {
        "source_id": "refund-policy",
        "text": "Orders returned within 30 days may use the original payment method.",
    }


TOOL_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "lookup_order": lookup_order,
    "search_refund_policy": search_refund_policy,
}


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "lookup_order",
                "description": "Look up an order by its exact identifier.",
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
                "name": "search_refund_policy",
                "description": "Retrieve the current refund policy.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
    ]


def dispatch_tool_call(call: Any, *, tracer: Tracer) -> tuple[str, str, str | None]:
    """Run local teaching Tools and return a safe Tool Result plus its evidence ID."""

    name = call.function.name
    try:
        arguments = json.loads(call.function.arguments)
    except json.JSONDecodeError:
        return name, json.dumps({"ok": False, "error": "invalid JSON arguments"}), None
    if not isinstance(arguments, dict):
        return name, json.dumps({"ok": False, "error": "arguments must be an object"}), None

    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return name, json.dumps({"ok": False, "error": "unknown tool"}), None

    with tracer.span(f"tool.{name}", arguments=call.function.arguments) as span:
        try:
            value = handler(**arguments)
        except TypeError:
            return name, json.dumps({"ok": False, "error": "invalid tool arguments"}), None
        span["result_fields"] = sorted(value)

    source_id = value.get("source_id") if isinstance(value.get("source_id"), str) else None
    return name, json.dumps({"ok": True, "value": value}), source_id


def run_agent(*, task: str, model: str) -> tuple[AgentRun, Trace]:
    client = create_client()
    trace = Trace("live-run-001")
    tracer = Tracer(trace, capture_policy=CapturePolicy(capture_content=False))
    messages: list[Any] = [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        {"role": "user", "content": task},
    ]
    observed_tools: list[str] = []
    retrieved_ids: list[str] = []
    started = time.perf_counter()

    with tracer.span("agent.run", task=task):
        for _ in range(4):
            with tracer.span("model.generate", message_count=len(messages), model=model) as span:
                response = client.chat.completions.create(
                    model=model,
                    temperature=0,
                    messages=messages,
                    tools=tool_definitions(),
                    tool_choice="auto",
                )
                usage = response.usage
                if usage is not None:
                    span["prompt_tokens"] = usage.prompt_tokens
                    span["completion_tokens"] = usage.completion_tokens

            if not response.choices:
                raise RuntimeError("DeepSeek did not return a response.")
            message = response.choices[0].message
            messages.append(message)
            if not message.tool_calls:
                if message.content is None or not message.content.strip():
                    raise RuntimeError("DeepSeek returned empty final text.")
                answer = message.content.strip()
                latency_ms = (time.perf_counter() - started) * 1000
                return (
                    AgentRun(
                        answer=answer,
                        tools=tuple(observed_tools),
                        retrieved_ids=tuple(retrieved_ids),
                        abstained="not have enough evidence" in answer.lower(),
                        latency_ms=latency_ms,
                    ),
                    trace,
                )

            for call in message.tool_calls:
                name, content, source_id = dispatch_tool_call(call, tracer=tracer)
                observed_tools.append(name)
                if source_id is not None:
                    retrieved_ids.append(source_id)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    raise RuntimeError("model exceeded the demonstration's maximum tool rounds")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trace and score one real DeepSeek Tool Calling run."
    )
    parser.add_argument(
        "--task",
        default="Can ORDER-42 be refunded to the original payment method?",
        help="User task sent to DeepSeek.",
    )
    args = parser.parse_args()
    model = required_env("DEEPSEEK_MODEL")
    run, trace = run_agent(task=args.task, model=model)
    case = EvalCase(
        "live-refund",
        args.task,
        ("30 days", "original payment method"),
        ("lookup_order", "search_refund_policy"),
    )

    print("=== trace topology ===")
    print(format_trace(trace))
    print("=== observed run ===")
    print("answer:", run.answer)
    print("tools:", run.tools)
    print("retrieved_ids:", run.retrieved_ids)
    print("latency_ms:", round(run.latency_ms, 1))
    print("=== deterministic score for this one run ===")
    print(score_case(case, run))


if __name__ == "__main__":
    main()

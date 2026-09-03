"""Stage 00: a minimal real OpenAI Tool Calling loop.

Run:
    python stages/00-foundations/code/minimal_tool_loop.py

Required environment:
    OPENAI_API_KEY=...

Optional:
    OPENAI_MODEL=gpt-5.6-luna

The weather Tool intentionally returns deterministic mock data. The lesson is
not weather integration; it is the exact control flow:

    model proposes ToolCall
        -> Runtime validates/executes Python
        -> Runtime returns function_call_output
        -> model continues

No Agent framework is used in this file.
"""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

INSTRUCTIONS = (
    "You are a travel assistant. "
    "Use the provided Tools for weather lookup and temperature conversion; "
    "do not guess or perform the conversion yourself. "
    "The weather data in this course is mocked, so state that clearly in the final answer."
)

TOOLS = [
    {
        "type": "function",
        "name": "get_weather",
        "description": (
            "Get deterministic mock weather data used by this Stage 00 course example. "
            "This is not a live weather service."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, for example Tokyo.",
                }
            },
            "required": ["city"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "celsius_to_fahrenheit",
        "description": "Convert a Celsius temperature to Fahrenheit.",
        "parameters": {
            "type": "object",
            "properties": {
                "temperature_c": {
                    "type": "number",
                    "description": "Temperature in degrees Celsius.",
                }
            },
            "required": ["temperature_c"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def get_weather(city: str) -> dict[str, Any]:
    """Return deterministic teaching data, not real-time weather."""

    if not isinstance(city, str) or not city.strip():
        raise ValueError("city must be a non-empty string")

    if city.strip().lower() not in {"tokyo", "东京"}:
        raise ValueError("this course example only contains Tokyo weather data")

    return {
        "city": "Tokyo",
        "temperature_c": 18.0,
        "source": "Tiny-Agent Stage 00 mock data",
    }


def celsius_to_fahrenheit(temperature_c: float) -> dict[str, float]:
    """Convert Celsius to Fahrenheit after simple Runtime-side validation."""

    if not isinstance(temperature_c, (int, float)) or isinstance(temperature_c, bool):
        raise ValueError("temperature_c must be a number")

    temperature_f = temperature_c * 9 / 5 + 32
    return {"temperature_f": round(temperature_f, 1)}


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Runtime-owned dispatch.

    The model only proposes `name` and `arguments`. This function is the first
    deterministic execution boundary: unknown Tools are rejected rather than
    guessed or dynamically imported.
    """

    if name == "get_weather":
        return get_weather(**arguments)
    if name == "celsius_to_fahrenheit":
        return celsius_to_fahrenheit(**arguments)

    raise ValueError(f"Unknown Tool: {name}")


def run_tool_loop(user_input: str, max_steps: int = 6) -> str:
    """Run a bounded model -> Tool -> observation loop."""

    client = OpenAI()

    response = client.responses.create(
        model=MODEL,
        instructions=INSTRUCTIONS,
        input=user_input,
        tools=TOOLS,
        parallel_tool_calls=False,
    )

    for step in range(1, max_steps + 1):
        function_calls = [
            item for item in response.output if item.type == "function_call"
        ]

        if not function_calls:
            final_answer = response.output_text
            print("final:", final_answer)
            return final_answer

        # parallel_tool_calls=False keeps this teaching example to one proposed
        # function call at a time so the state transition is easy to inspect.
        call = function_calls[0]
        arguments = json.loads(call.arguments)

        print(f"step {step}: model -> {call.name}({arguments})")

        # The Runtime, not the model, executes the real Python function.
        result = execute_tool(call.name, arguments)
        print(f"step {step}: tool  -> {result}")

        # The model does not automatically know local Python variables. Return
        # the real observation and preserve `call_id` correlation.
        response = client.responses.create(
            model=MODEL,
            instructions=INSTRUCTIONS,
            previous_response_id=response.id,
            tools=TOOLS,
            parallel_tool_calls=False,
            input=[
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result, ensure_ascii=False),
                }
            ],
        )

    raise RuntimeError(f"Tool loop exceeded max_steps={max_steps}")


if __name__ == "__main__":
    run_tool_loop(
        "What is the mock Tokyo weather in Celsius, and what is it in Fahrenheit?"
    )

"""Stage 01 live example: the same Runtime with a real OpenAI model.

The application owns AgentRuntime, ToolRegistry, and Tool execution. Only
OpenAIResponsesModel knows the provider-specific Responses API protocol.

Run from the repository root:

    python -m pip install -e ".[openai]"
    export OPENAI_API_KEY="..."
    python stages/01-react-runtime/code/openai_multi_tool_agent.py

The weather returned here is deterministic course data, not live weather.
"""

from __future__ import annotations

import json
import os
from typing import Any

from tiny_agent import AgentRuntime, Tool, ToolRegistry
from tiny_agent.models import OpenAIResponsesModel


# ---------------------------------------------------------------------------
# Real Python Tools. The model never executes these functions directly.
# ---------------------------------------------------------------------------


def get_mock_weather(city: str) -> str:
    """Return deterministic JSON course data, not live weather."""
    if city.lower() != "tokyo":
        raise ValueError("This course demo only defines Tokyo mock weather.")

    return json.dumps(
        {
            "city": "Tokyo",
            "temperature_c": 18.0,
            "condition": "cloudy",
            "source": "course_mock",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def celsius_to_fahrenheit(temperature_c: float) -> float:
    return round(temperature_c * 9 / 5 + 32, 1)


CITY_SCHEMA = {
    "type": "object",
    "properties": {
        "city": {
            "type": "string",
            "description": "City name in English. The course demo supports Tokyo.",
        }
    },
    "required": ["city"],
    "additionalProperties": False,
}

TEMPERATURE_SCHEMA = {
    "type": "object",
    "properties": {
        "temperature_c": {
            "type": "number",
            "description": "Temperature in degrees Celsius to convert.",
        }
    },
    "required": ["temperature_c"],
    "additionalProperties": False,
}


travel_tools = ToolRegistry(
    [
        Tool(
            name="get_mock_weather",
            description=(
                "Return the course's deterministic mock weather for one city. "
                "Use this Tool when the user explicitly asks about course/mock "
                "weather. It does not provide live weather."
            ),
            parameters=CITY_SCHEMA,
            handler=get_mock_weather,
        ),
        Tool(
            name="celsius_to_fahrenheit",
            description=(
                "Convert one Celsius temperature to Fahrenheit. Use this Tool "
                "when an exact conversion is requested."
            ),
            parameters=TEMPERATURE_SCHEMA,
            handler=celsius_to_fahrenheit,
        ),
    ]
)


# Swapping the model/provider should not require changing AgentRuntime or Tools.
model = OpenAIResponsesModel(
    model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
    reasoning_effort="none",
    strict_tools=True,
    parallel_tool_calls=True,
)

runtime = AgentRuntime(
    model=model,
    tools=travel_tools,
    system_prompt=(
        "You are a precise travel assistant for an Agent-engineering course. "
        "For this exercise, use get_mock_weather to retrieve the course mock "
        "Tokyo temperature and use celsius_to_fahrenheit for the exact conversion. "
        "Never describe the mock Tool as live weather. After the required Tool "
        "calls, explain the result concisely."
    ),
    max_steps=6,
)


def pretty_observation(raw: str) -> str:
    """Pretty-print JSON observations when possible."""
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def print_trajectory(messages: list[dict[str, Any]]) -> None:
    visible_index = 0

    for message in messages:
        if message["role"] == "system":
            continue

        visible_index += 1
        role = message["role"]

        if role == "assistant" and "tool_calls" in message:
            for call in message["tool_calls"]:
                print(
                    f"{visible_index:02d}. ACTION      "
                    f"{call['name']}({call['arguments']}) "
                    f"[id={call['id']}]"
                )
            continue

        if role == "tool":
            print(
                f"{visible_index:02d}. OBSERVATION "
                f"{message['name']} -> "
                f"{pretty_observation(message['content'])}"
            )
            continue

        label = "USER" if role == "user" else "ASSISTANT"
        print(
            f"{visible_index:02d}. {label:11s} "
            f"{message.get('content', '')}"
        )


if __name__ == "__main__":
    result = runtime.run(
        "Use the course's mock Tokyo weather. Tell me the temperature in "
        "Celsius and Fahrenheit, then briefly explain what it feels like."
    )

    print("\nAuditable trajectory")
    print("--------------------")
    print_trajectory(result.messages)

    print("\nFinal answer")
    print("------------")
    print(result.output)
    print(f"\nsteps={result.steps}")

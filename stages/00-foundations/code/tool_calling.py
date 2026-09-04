from __future__ import annotations

import json
import os
from typing import Any


TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}

WEATHER_TOOL = {
    "type": "function",
    "name": "get_teaching_weather",
    "description": (
        "Return the deterministic teaching weather record for Tokyo or Paris. "
        "Use this function whenever the user asks about those teaching records."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "enum": sorted(TEACHING_WEATHER),
                "description": "The city whose teaching record should be read.",
            }
        },
        "required": ["city"],
        "additionalProperties": False,
    },
    "strict": True,
}


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Set {name} before running this example.")
    return value.strip()


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI SDK is not installed. Run:\n"
            "python -m pip install -r "
            "stages/00-foundations/code/requirements.txt"
        ) from exc

    required_env("OPENAI_API_KEY")
    return OpenAI()


def get_teaching_weather(city: str) -> dict[str, Any]:
    try:
        record = TEACHING_WEATHER[city]
    except KeyError as exc:
        raise ValueError(f"Unsupported city: {city}") from exc
    return {"city": city, **record}


def parse_arguments(raw_arguments: str) -> dict[str, Any]:
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Tool arguments are not valid JSON: {raw_arguments!r}") from exc
    if not isinstance(arguments, dict):
        raise RuntimeError("Tool arguments must decode to a JSON object.")
    return arguments


def validate_weather_arguments(arguments: dict[str, Any]) -> str:
    if set(arguments) != {"city"}:
        raise RuntimeError("get_teaching_weather expects exactly one field: city")
    city = arguments["city"]
    if not isinstance(city, str):
        raise RuntimeError("The city argument must be a string.")
    if city not in TEACHING_WEATHER:
        raise RuntimeError(f"Unsupported city: {city}")
    return city


def main() -> None:
    client = create_client()
    model = required_env("OPENAI_MODEL")

    first = client.responses.create(
        model=model,
        instructions=(
            "Use the supplied function to read teaching weather records. A function "
            "call only requests an action; never claim a result before the function "
            "output is returned."
        ),
        input=(
            "Read Tokyo's deterministic teaching weather record and report the "
            "temperature and condition."
        ),
        tools=[WEATHER_TOOL],
        tool_choice={"type": "function", "name": "get_teaching_weather"},
        parallel_tool_calls=False,
    )

    if first.status != "completed":
        raise RuntimeError(f"The first response did not complete: {first.status}")

    calls = [item for item in first.output if item.type == "function_call"]
    if len(calls) != 1:
        raise RuntimeError(f"Expected exactly one function call, received {len(calls)}.")

    call = calls[0]
    if call.name != "get_teaching_weather":
        raise RuntimeError(f"The model requested an unknown function: {call.name}")

    arguments = parse_arguments(call.arguments)
    city = validate_weather_arguments(arguments)
    result = get_teaching_weather(city)

    print("=== model proposed ===")
    print(call.name, arguments)
    print("\n=== application executed ===")
    print(result)

    final = client.responses.create(
        model=model,
        instructions=(
            "Answer only from the returned function output. Make clear that this is "
            "a deterministic teaching record, not live weather."
        ),
        previous_response_id=first.id,
        input=[
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result, ensure_ascii=False),
            }
        ],
        tools=[WEATHER_TOOL],
        tool_choice="none",
    )

    if final.status != "completed":
        raise RuntimeError(f"The final response did not complete: {final.status}")
    if not final.output_text.strip():
        raise RuntimeError("The final response completed without text output.")

    print("\n=== final answer ===")
    print(final.output_text)


if __name__ == "__main__":
    main()

"""One model request, one checked local function call, then one model answer."""
from __future__ import annotations

import json
from typing import Any

from common import (
    create_client, parse_args, request_for, require_completed, require_text, required_env,
)


TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}

WEATHER_PARAMETERS = {
    "type": "object",
    "properties": {"city": {"type": "string", "enum": ["Tokyo", "Paris"]}},
    "required": ["city"],
    "additionalProperties": False,
}
WEATHER_TOOL = {
    "type": "function",
    "name": "get_teaching_weather",
    "description": (
        "Read a fixed teaching weather record for Tokyo or Paris. "
        "Returns temperature_c in Celsius and condition. Not live weather."
    ),
    "parameters": WEATHER_PARAMETERS,
}

FIRST_INSTRUCTIONS = (
    "Help Lin read the requested teaching weather record. Request exactly one call "
    "to get_teaching_weather for the requested city. Do not invent the record or "
    "claim success before the application returns the result."
)
FINAL_INSTRUCTIONS = (
    "Answer Lin in the user's language, using only the returned weather record. "
    "State its city, Celsius temperature and condition. Explicitly say it is a "
    "fixed teaching record, not live weather. Do not claim any other action."
)


def get_teaching_weather(city: str) -> dict[str, Any]:
    if city not in TEACHING_WEATHER:
        raise ValueError("Unsupported teaching city.")
    return {"city": city, **TEACHING_WEATHER[city], "source": "fixed teaching record"}


def parse_arguments(raw_arguments: str) -> dict[str, Any]:
    if not isinstance(raw_arguments, str):
        raise RuntimeError("Tool arguments must be a JSON string.")
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Tool arguments are not valid JSON.") from exc
    if not isinstance(arguments, dict):
        raise RuntimeError("Tool arguments must decode to an object.")
    return arguments


def validate_weather_arguments(arguments: dict[str, Any]) -> str:
    if set(arguments) != {"city"}:
        raise RuntimeError("Weather lookup expects exactly one field: city.")
    city = arguments["city"]
    if not isinstance(city, str) or city not in TEACHING_WEATHER:
        raise RuntimeError("city must be Tokyo or Paris.")
    return city


def read_weather_call(response: Any) -> Any:
    require_completed(response)
    calls = [item for item in response.output if item.type == "function_call"]
    if len(calls) != 1:
        raise RuntimeError("This example accepts exactly one function call.")
    call = calls[0]
    if call.name != "get_teaching_weather":
        raise RuntimeError("The requested function is not allowed.")
    if not isinstance(call.call_id, str) or not call.call_id.strip():
        raise RuntimeError("Function call has no usable call_id.")
    return call


def run_round_trip(client: Any, model: str, city: str, language: str) -> tuple[dict, str]:
    history: list[dict[str, Any]] = [
        {"role": "user", "content": request_for(city, language)}
    ]
    first = client.responses.create(
        model=model,
        instructions=FIRST_INSTRUCTIONS,
        input=history,
        tools=[WEATHER_TOOL],
        tool_choice={"type": "function", "name": "get_teaching_weather"},
        max_output_tokens=4096,
    )
    call = read_weather_call(first)
    arguments = parse_arguments(call.arguments)
    requested_city = validate_weather_arguments(arguments)
    if requested_city != city:
        raise RuntimeError("Tool city does not match the selected request.")
    print("=== model requested; Python function has not run ===")
    print(call.name, arguments, "call_id:", call.call_id)

    result = get_teaching_weather(requested_city)
    print("\n=== application executed the lookup ===")
    print(json.dumps(result, ensure_ascii=False))

    # Preserve the provider's output items, including any protocol-required items.
    history.extend(item.model_dump(mode="json", exclude_none=True) for item in first.output)
    history.append({
        "type": "function_call_output",
        "call_id": call.call_id,
        "output": json.dumps(result, ensure_ascii=False),
    })
    final = client.responses.create(
        model=model,
        instructions=FINAL_INSTRUCTIONS,
        input=history,
        tools=[WEATHER_TOOL],
        tool_choice="none",
        max_output_tokens=4096,
    )
    answer = require_text(final)
    print("\n=== model answer based on the returned record ===")
    print(answer)
    return result, answer


def main() -> None:
    args = parse_args()
    model = required_env("DEEPSEEK_MODEL")
    with create_client() as client:
        run_round_trip(client, model, args.city, args.language)


if __name__ == "__main__":
    main()

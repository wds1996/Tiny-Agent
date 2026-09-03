"""Stage 00: OpenAI Structured Output with a JSON Schema.

Run:
    python stages/00-foundations/code/structured_output_demo.py

Required environment:
    OPENAI_API_KEY=...

Optional:
    OPENAI_MODEL=gpt-5.6-luna
"""

from __future__ import annotations

import json
import os

from openai import OpenAI


MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

TRIP_SCHEMA = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "travel_date": {"type": "string"},
        "budget_cny": {"type": "number"},
        "needs_weather": {"type": "boolean"},
    },
    "required": [
        "city",
        "travel_date",
        "budget_cny",
        "needs_weather",
    ],
    "additionalProperties": False,
}


def main() -> None:
    client = OpenAI()

    response = client.responses.create(
        model=MODEL,
        instructions=(
            "Extract information from the user's travel description. "
            "Normalize dates to YYYY-MM-DD. Do not invent missing facts."
        ),
        input=(
            "I am going to Tokyo on October 3, 2026. My budget is about "
            "8,000 CNY and I also want weather information."
        ),
        text={
            "format": {
                "type": "json_schema",
                "name": "trip_request",
                "strict": True,
                "schema": TRIP_SCHEMA,
            }
        },
    )

    # Structured Output constrains the response shape. We still parse the JSON
    # and can apply additional application/business validation afterwards.
    trip = json.loads(response.output_text)

    print(trip)
    print("needs_weather type:", type(trip["needs_weather"]).__name__)


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    priority: Priority
    needs_external_data: bool
    reason: str = Field(min_length=1)


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


def main() -> None:
    client = create_client()
    model = required_env("OPENAI_MODEL")

    response = client.responses.parse(
        model=model,
        instructions=(
            "Turn the request into a task card. Describe only the request itself; "
            "do not guess the weather or pretend that external data was retrieved."
        ),
        input=(
            "Compare the current weather in Tokyo and Paris and tell me which city "
            "is warmer."
        ),
        text_format=TaskCard,
    )

    if response.status != "completed":
        raise RuntimeError(f"The response did not complete: {response.status}")

    task = response.output_parsed
    if task is None:
        raise RuntimeError("The response contained no parsed TaskCard.")

    print(task.model_dump_json(indent=2))
    print(
        "\nThe shape is validated. The claims still need to be checked against "
        "real data."
    )


if __name__ == "__main__":
    main()

"""Describe the same request as validated data; do not fetch the weather yet."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from common import create_client, parse_args, request_for, require_completed, required_env


class TaskCard(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    goal: str = Field(min_length=1, max_length=200)
    city: Literal["Tokyo", "Paris"]
    needs_external_data: bool
    reason: str = Field(min_length=1, max_length=300)


INSTRUCTIONS = (
    "Describe the user's request as a task card, not as a weather answer. "
    "Copy the city from the request. needs_external_data means that information "
    "outside this model input must be read, even if it is only a local teaching "
    "record. That record has not been supplied. Do not invent its temperature "
    "or condition. Write goal and a brief, user-facing reason in the user's language."
)


def validate_card_for_request(card: TaskCard, expected_city: str) -> None:
    if card.city != expected_city:
        raise RuntimeError("Task card refers to a different city than the request.")
    if not card.needs_external_data:
        raise RuntimeError("This request requires a record that was not supplied.")


def make_task_card(client: Any, model: str, city: str, language: str) -> TaskCard:
    response = client.responses.parse(
        model=model,
        instructions=INSTRUCTIONS,
        input=request_for(city, language),
        text_format=TaskCard,
        max_output_tokens=4096,
    )
    require_completed(response)
    card = response.output_parsed
    if not isinstance(card, TaskCard):
        raise RuntimeError("Response contained no validated TaskCard.")
    validate_card_for_request(card, city)
    return card


def main() -> None:
    args = parse_args()
    model = required_env("DEEPSEEK_MODEL")
    with create_client() as client:
        card = make_task_card(client, model, args.city, args.language)
    print("=== task card; still no weather lookup ===")
    print(card.model_dump_json(indent=2))
    print("\ncity:", card.city)
    print("needs_external_data:", card.needs_external_data)


if __name__ == "__main__":
    main()

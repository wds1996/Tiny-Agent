"""Ask about the record before giving the model access to its contents."""
from __future__ import annotations

from typing import Any

from common import create_client, parse_args, request_for, require_text, required_env


INSTRUCTIONS = (
    "You are helping Lin prepare a classroom weather note. You have not been given "
    "the teaching record and have no tool to read it. Briefly explain what information "
    "is missing before you can answer. Do not invent temperature or condition, and "
    "do not claim to have read a file or queried a service. Use the user's language."
)


def ask_without_record(client: Any, model: str, city: str, language: str) -> Any:
    response = client.responses.create(
        model=model,
        instructions=INSTRUCTIONS,
        input=request_for(city, language),
        max_output_tokens=4096,
    )
    require_text(response)
    return response


def main() -> None:
    args = parse_args()
    model = required_env("DEEPSEEK_MODEL")
    with create_client() as client:
        response = ask_without_record(client, model, args.city, args.language)
    print("=== request ===")
    print(request_for(args.city, args.language))
    print("\n=== model text; no weather lookup has run ===")
    print(response.output_text)
    print("\nresponse_id:", response.id)
    print("model:", response.model)
    print("status:", response.status)
    if response.usage is not None:
        print("input_tokens:", response.usage.input_tokens)
        print("output_tokens:", response.usage.output_tokens)
        print("total_tokens:", response.usage.total_tokens)
    else:
        print("token usage: not reported")


if __name__ == "__main__":
    main()

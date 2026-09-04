from __future__ import annotations

import os
from typing import Any


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

    response = client.responses.create(
        model=model,
        instructions=(
            "You are a patient programming teacher. Explain the idea accurately, "
            "use one concrete analogy, and avoid unexplained jargon."
        ),
        input=(
            "In no more than 120 words, explain why a language model response is "
            "a proposal produced by a model rather than an action performed by my "
            "Python program."
        ),
    )

    if response.status != "completed":
        raise RuntimeError(f"The response did not complete: {response.status}")
    if not response.output_text.strip():
        raise RuntimeError("The response completed without text output.")

    print("=== response metadata ===")
    print("response_id:", response.id)
    print("model:", response.model)

    print("\n=== model output ===")
    print(response.output_text)

    usage = response.usage
    if usage is not None:
        print("\n=== token usage ===")
        print("input_tokens:", usage.input_tokens)
        print("output_tokens:", usage.output_tokens)
        print("total_tokens:", usage.total_tokens)


if __name__ == "__main__":
    main()

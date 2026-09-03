"""Stage 00: the first real OpenAI Responses API call.

Run:
    python stages/00-foundations/code/first_openai_call.py

Required environment:
    OPENAI_API_KEY=...

Optional:
    OPENAI_MODEL=gpt-5.6-luna

This example deliberately stays small. Its job is to make the boundary between
Python application code and model inference visible before Agent abstractions
are introduced.
"""

from __future__ import annotations

import os

from openai import OpenAI


MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
INSTRUCTIONS = (
    "You are a patient AI engineering teacher. "
    "Explain concepts concisely but accurately."
)


def main() -> None:
    client = OpenAI()

    first = client.responses.create(
        model=MODEL,
        instructions=INSTRUCTIONS,
        input="Why should an Agent not simply be understood as an LLM?",
    )

    print("=== First turn ===")
    print(first.output_text)
    print()

    # `previous_response_id` lets this request continue from the provider-side
    # response context. It is convenient conversation continuity, not a claim
    # that the model itself gained permanent long-term memory.
    second = client.responses.create(
        model=MODEL,
        instructions=INSTRUCTIONS,
        previous_response_id=first.id,
        input="In that architecture, who actually executes a Tool?",
    )

    print("=== Second turn ===")
    print(second.output_text)
    print()

    if second.usage is not None:
        print("=== Usage for second turn ===")
        print("input_tokens:", second.usage.input_tokens)
        print("output_tokens:", second.usage.output_tokens)
        print("total_tokens:", second.usage.total_tokens)


if __name__ == "__main__":
    main()

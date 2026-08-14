from __future__ import annotations

import json
from typing import Any, Literal


class StructuredDecisionRefusal(RuntimeError):
    """The provider refused to produce the requested structured decision."""


class StructuredDecisionIncomplete(RuntimeError):
    """The provider stopped before the structured decision completed."""


class OpenAIStructuredDecisionModel:
    """OpenAI Responses adapter for schema-constrained control decisions.

    This adapter is intentionally separate from ``OpenAIResponsesModel``:

    - ``OpenAIResponsesModel`` normalizes Agent turns into ToolCall/final answer.
    - ``OpenAIStructuredDecisionModel`` asks for one JSON-Schema-constrained object.

    Routing and planning are control-plane decisions, so Stage 02 uses the second
    interface instead of parsing free-form prose.
    """

    def __init__(
        self,
        model: str = "gpt-5.6-luna",
        *,
        reasoning_effort: Literal[
            "none", "low", "medium", "high", "xhigh", "max"
        ] = "none",
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.reasoning_effort = reasoning_effort

        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - environment dependent
                raise RuntimeError(
                    "OpenAI support is optional. Install it with "
                    '`pip install -e ".[openai]"`.'
                ) from exc
            client = OpenAI()

        self.client = client

    def decide(
        self,
        *,
        prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        instructions: str | None = None,
    ) -> dict[str, Any]:
        if not schema_name:
            raise ValueError("schema_name must not be empty")

        request: dict[str, Any] = {
            "model": self.model,
            "input": prompt,
            "reasoning": {"effort": self.reasoning_effort},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
        }
        if instructions:
            request["instructions"] = instructions

        response = self.client.responses.create(**request)

        # A safety refusal is a first-class provider outcome, not malformed JSON.
        refusal = self._extract_refusal(response)
        if refusal is not None:
            raise StructuredDecisionRefusal(refusal)

        # Responses can also stop before a complete structured value is produced.
        if getattr(response, "status", None) == "incomplete":
            details = getattr(response, "incomplete_details", None)
            reason = getattr(details, "reason", None) or "unknown"
            raise StructuredDecisionIncomplete(
                f"Structured decision response was incomplete: {reason}"
            )

        raw = getattr(response, "output_text", None)
        if raw is None or not str(raw).strip():
            raise RuntimeError("Structured decision response contained no output text")

        try:
            value = json.loads(str(raw))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Structured decision was not valid JSON: {raw!r}"
            ) from exc

        if not isinstance(value, dict):
            raise RuntimeError(
                "Structured decision must decode to a JSON object, "
                f"got {type(value).__name__}"
            )

        return value

    @staticmethod
    def _extract_refusal(response: Any) -> str | None:
        for output in getattr(response, "output", []) or []:
            if getattr(output, "type", None) != "message":
                continue
            for item in getattr(output, "content", []) or []:
                if getattr(item, "type", None) == "refusal":
                    refusal = getattr(item, "refusal", None)
                    return str(refusal or "The model refused the structured request.")
        return None

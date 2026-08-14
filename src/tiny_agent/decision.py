from __future__ import annotations

from typing import Any, Protocol


class StructuredDecisionModel(Protocol):
    """Provider-neutral interface for one schema-constrained control decision.

    Stage 02 uses structured decisions for routing and planning. The model returns
    application data rather than user-facing prose.
    """

    def decide(
        self,
        *,
        prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        instructions: str | None = None,
    ) -> dict[str, Any]:
        ...

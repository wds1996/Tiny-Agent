from __future__ import annotations

import json
import os
import re
from typing import Any, cast

from decision import DecisionKind, SupportDecision


DECISION_INSTRUCTIONS = """You classify a customer-support request for a refund workflow.
Return one JSON object with exactly these keys: kind and order_id.

kind must be exactly one of:
- greeting: a greeting or casual opening with no policy or refund request.
- refund_question: asks whether a refund is possible, its status, or its policy.
- refund_action: explicitly asks to issue or perform a refund.
- policy_question: every other policy or support question.

order_id must be an order identifier from the user's request in the form ORDER-<digits>,
or null when the request contains no such identifier. Never invent an order ID.
Return JSON only. Do not answer the user or execute any action."""

_ORDER_ID_RE = re.compile(r"ORDER-\d+", flags=re.IGNORECASE)
_VALID_KINDS = frozenset({"greeting", "refund_question", "refund_action", "policy_question"})


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this example.")
    return value


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Install Stage 15 dependencies first:\n"
            "python -m pip install -r "
            "stages/15-capstone-enterprise-agent/code/requirements.txt"
        ) from exc

    return OpenAI(
        api_key=required_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )


def parse_decision(content: str) -> SupportDecision:
    """Validate the model's JSON before it enters the application runtime."""

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("DeepSeek did not return valid JSON for SupportDecision.") from exc

    if not isinstance(data, dict) or set(data) != {"kind", "order_id"}:
        raise RuntimeError("SupportDecision must contain exactly kind and order_id.")

    kind = data["kind"]
    if not isinstance(kind, str) or kind not in _VALID_KINDS:
        raise RuntimeError("SupportDecision.kind is invalid.")

    order_id = data["order_id"]
    if order_id is not None:
        if not isinstance(order_id, str) or _ORDER_ID_RE.fullmatch(order_id) is None:
            raise RuntimeError("SupportDecision.order_id must be ORDER-<digits> or null.")
        order_id = order_id.upper()

    return SupportDecision(kind=cast(DecisionKind, kind), order_id=order_id)


def validate_order_id_from_question(
    *, decision: SupportDecision, question: str
) -> SupportDecision:
    if decision.order_id is None:
        return decision
    request_order_ids = {
        match.group(0).upper() for match in _ORDER_ID_RE.finditer(question)
    }
    if decision.order_id not in request_order_ids:
        raise RuntimeError("DeepSeek returned an order ID that was not in the request.")
    return decision


class DeepSeekDecisionModel:
    """Use DeepSeek only for the SupportDecision boundary."""

    def __init__(self, *, client: Any, model: str) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")
        self._client = client
        self._model = model
        self.last_interaction: tuple[str, str, str] | None = None

    def decide(self, question: str) -> SupportDecision:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            max_tokens=120,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": DECISION_INSTRUCTIONS},
                {"role": "user", "content": question},
            ],
        )
        if not response.choices or response.choices[0].message.content is None:
            raise RuntimeError("DeepSeek did not return a SupportDecision.")

        content = response.choices[0].message.content.strip()
        decision = parse_decision(content)
        decision = validate_order_id_from_question(
            decision=decision,
            question=question,
        )
        self.last_interaction = (DECISION_INSTRUCTIONS, question, content)
        return decision


def format_conversation(*, interaction: tuple[str, str, str]) -> str:
    """Render the model exchange after the runtime trace."""

    instructions, question, content = interaction
    return "\n".join(
        [
            "=== reconstructed model conversation ===",
            "system (instructions):",
            f"  {instructions}",
            "user:",
            f"  {question}",
            "assistant (structured decision):",
            f"  {content}",
        ]
    )

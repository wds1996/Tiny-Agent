from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, Protocol


DecisionKind = Literal[
    "greeting",
    "refund_question",
    "refund_action",
    "policy_question",
]


@dataclass(frozen=True, slots=True)
class SupportDecision:
    kind: DecisionKind
    order_id: str | None = None


class DecisionModel(Protocol):
    def decide(self, question: str) -> SupportDecision: ...


_ORDER_RE = re.compile(r"\bORDER-\d+\b", flags=re.IGNORECASE)


class DeterministicDecisionModel:
    """Offline model double used by the runnable course example."""

    def decide(self, question: str) -> SupportDecision:
        lowered = question.lower()
        match = _ORDER_RE.search(question.upper())
        order_id = None if match is None else match.group(0).upper()

        if "hello" in lowered or "你好" in question:
            return SupportDecision("greeting")
        if "refund" in lowered or "退款" in question:
            wants_action = any(
                phrase in lowered
                for phrase in ("please refund", "refund order", "issue refund")
            ) or "请退款" in question or "退款订单" in question
            return SupportDecision(
                "refund_action" if wants_action else "refund_question",
                order_id=order_id,
            )
        return SupportDecision("policy_question", order_id=order_id)

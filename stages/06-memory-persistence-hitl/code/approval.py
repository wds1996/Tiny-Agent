from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal, Mapping, Any


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    run_id: str
    action: str
    arguments: Mapping[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    outcome: Literal["approve", "edit", "reject"]
    edited_arguments: Mapping[str, Any] | None = None


def resolve_refund_arguments(
    original: Mapping[str, Any],
    decision: ApprovalDecision,
) -> dict[str, Any] | None:
    if decision.outcome == "reject":
        return None

    if decision.outcome == "approve":
        candidate = dict(original)
    elif decision.outcome == "edit":
        if decision.edited_arguments is None:
            raise ValueError("edit requires edited_arguments")
        candidate = dict(decision.edited_arguments)
    else:
        raise ValueError(f"unknown approval outcome: {decision.outcome}")

    order_id = candidate.get("order_id")
    amount = candidate.get("amount")
    if not isinstance(order_id, str) or not order_id.strip():
        raise ValueError("order_id must be a non-empty string")

    try:
        amount_decimal = Decimal(str(amount))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("amount must be numeric") from exc
    if amount_decimal <= 0:
        raise ValueError("amount must be positive")

    return {"order_id": order_id.strip(), "amount": str(amount_decimal)}

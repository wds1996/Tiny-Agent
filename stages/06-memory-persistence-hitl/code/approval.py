from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping


CREATE_SUPPORT_CASE = "create_support_case"


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    run_id: str
    thread_id: str
    owner_id: str
    action: str
    arguments: Mapping[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    outcome: Literal["approve", "edit", "reject"]
    edited_arguments: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ReviewerContext:
    reviewer_id: str
    allowed_actions: frozenset[str]


def validate_case_arguments(arguments: Mapping[str, Any]) -> dict[str, str]:
    if set(arguments) != {"order_id", "reason"}:
        raise ValueError("support-case arguments must contain exactly order_id and reason")

    order_id = arguments.get("order_id")
    reason = arguments.get("reason")
    if not isinstance(order_id, str) or not order_id.strip():
        raise ValueError("order_id must be a non-empty string")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be a non-empty string")

    normalized_reason = " ".join(reason.split())
    if len(normalized_reason) > 240:
        raise ValueError("reason must be at most 240 characters")

    return {
        "order_id": order_id.strip().upper(),
        "reason": normalized_reason,
    }


def authorize_reviewer(request: ApprovalRequest, reviewer: ReviewerContext) -> None:
    if not reviewer.reviewer_id.strip():
        raise PermissionError("reviewer_id must not be blank")
    if request.action not in reviewer.allowed_actions:
        raise PermissionError(
            f"reviewer {reviewer.reviewer_id!r} is not authorized for {request.action!r}"
        )


def resolve_case_arguments(
    original: Mapping[str, Any],
    decision: ApprovalDecision,
) -> dict[str, str] | None:
    if decision.outcome == "reject":
        return None

    validated_original = validate_case_arguments(original)
    if decision.outcome == "approve":
        return validated_original

    if decision.outcome != "edit":
        raise ValueError(f"unknown approval outcome: {decision.outcome}")
    if decision.edited_arguments is None:
        raise ValueError("edit requires edited_arguments")

    edited = validate_case_arguments(decision.edited_arguments)
    if edited["order_id"] != validated_original["order_id"]:
        raise ValueError("an approval edit cannot switch to a different order")
    return edited

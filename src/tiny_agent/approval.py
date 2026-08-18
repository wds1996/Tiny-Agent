from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping


ApprovalOutcome = Literal["approve", "edit", "reject"]
ApprovalRisk = Literal["low", "medium", "high", "critical"]


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """A serializable proposal that may cross a human-review boundary."""

    action: str
    arguments: dict[str, Any]
    reason: str
    risk: ApprovalRisk = "high"

    def __post_init__(self) -> None:
        if not self.action.strip():
            raise ValueError("approval action must be non-empty")
        if not self.reason.strip():
            raise ValueError("approval reason must be non-empty")

    def to_interrupt_payload(self) -> dict[str, Any]:
        return {
            "type": "tool_approval",
            "action": self.action,
            "arguments": dict(self.arguments),
            "reason": self.reason,
            "risk": self.risk,
            "allowed_decisions": ["approve", "edit", "reject"],
        }


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    outcome: ApprovalOutcome
    edited_arguments: dict[str, Any] | None = None
    feedback: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> ApprovalDecision:
        outcome = payload.get("outcome")
        if outcome not in {"approve", "edit", "reject"}:
            raise ValueError("approval outcome must be approve, edit, or reject")

        edited = payload.get("edited_arguments")
        if edited is not None and not isinstance(edited, dict):
            raise ValueError("edited_arguments must be an object when provided")

        feedback = payload.get("feedback")
        if feedback is not None and not isinstance(feedback, str):
            raise ValueError("feedback must be a string when provided")

        return cls(
            outcome=outcome,
            edited_arguments=dict(edited) if edited is not None else None,
            feedback=feedback,
        )


@dataclass(frozen=True, slots=True)
class ApprovalResolution:
    approved: bool
    arguments: dict[str, Any] | None
    feedback: str | None = None


def resolve_approval(
    request: ApprovalRequest,
    decision: ApprovalDecision,
) -> ApprovalResolution:
    """Apply a human decision without confusing approval with authorization.

    The returned arguments still need ordinary application validation and
    permission checks before a real side effect is executed.
    """

    if decision.outcome == "approve":
        return ApprovalResolution(True, dict(request.arguments), decision.feedback)

    if decision.outcome == "edit":
        if decision.edited_arguments is None:
            raise ValueError("edit decisions require edited_arguments")
        return ApprovalResolution(True, dict(decision.edited_arguments), decision.feedback)

    return ApprovalResolution(False, None, decision.feedback)

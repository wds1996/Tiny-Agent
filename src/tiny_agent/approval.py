from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping


ApprovalOutcome = Literal["approve", "edit", "reject"]
ApprovalRisk = Literal["low", "medium", "high", "critical"]
_VALID_OUTCOMES = frozenset({"approve", "edit", "reject"})
_VALID_RISKS = frozenset({"low", "medium", "high", "critical"})


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """A serializable proposal that may cross a human-review boundary."""

    action: str
    arguments: dict[str, Any]
    reason: str
    risk: ApprovalRisk = "high"

    def __post_init__(self) -> None:
        if not isinstance(self.action, str) or not self.action.strip():
            raise ValueError("approval action must be non-empty")
        if not isinstance(self.arguments, dict):
            raise ValueError("approval arguments must be an object")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("approval reason must be non-empty")
        if self.risk not in _VALID_RISKS:
            raise ValueError("approval risk must be low, medium, high, or critical")

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

    def __post_init__(self) -> None:
        if self.outcome not in _VALID_OUTCOMES:
            raise ValueError("approval outcome must be approve, edit, or reject")
        if self.edited_arguments is not None and not isinstance(self.edited_arguments, dict):
            raise ValueError("edited_arguments must be an object when provided")
        if self.feedback is not None and not isinstance(self.feedback, str):
            raise ValueError("feedback must be a string when provided")
        if self.outcome == "edit" and self.edited_arguments is None:
            raise ValueError("edit decisions require edited_arguments")
        if self.outcome != "edit" and self.edited_arguments is not None:
            raise ValueError("edited_arguments are only valid for edit decisions")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> ApprovalDecision:
        if not isinstance(payload, Mapping):
            raise ValueError("approval decision payload must be a mapping")

        outcome = payload.get("outcome")
        edited = payload.get("edited_arguments")
        feedback = payload.get("feedback")

        return cls(
            outcome=outcome,  # type: ignore[arg-type]
            edited_arguments=dict(edited) if isinstance(edited, dict) else edited,  # type: ignore[arg-type]
            feedback=feedback,  # type: ignore[arg-type]
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
        # ApprovalDecision already validates that edited arguments are present.
        assert decision.edited_arguments is not None
        return ApprovalResolution(True, dict(decision.edited_arguments), decision.feedback)

    return ApprovalResolution(False, None, decision.feedback)

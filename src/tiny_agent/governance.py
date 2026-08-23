from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from .reliability import ToolApprovalRequired, ToolPermissionError


RiskLevel = Literal["low", "medium", "high", "critical"]
_VALID_RISKS = frozenset({"low", "medium", "high", "critical"})


@dataclass(frozen=True, slots=True)
class Principal:
    subject_id: str
    roles: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.subject_id, str) or not self.subject_id.strip():
            raise ValueError("subject_id must be a non-empty string")
        if not self.roles or any(not isinstance(role, str) or not role.strip() for role in self.roles):
            raise ValueError("roles must contain non-empty strings")


@dataclass(frozen=True, slots=True)
class ToolPermissionRule:
    tool_name: str
    allowed_roles: frozenset[str]
    requires_approval: bool = False
    risk: RiskLevel = "low"

    def __post_init__(self) -> None:
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            raise ValueError("tool_name must be a non-empty string")
        if not self.allowed_roles or any(
            not isinstance(role, str) or not role.strip() for role in self.allowed_roles
        ):
            raise ValueError("allowed_roles must contain non-empty strings")
        if self.risk not in _VALID_RISKS:
            raise ValueError("risk must be low, medium, high, or critical")


def action_fingerprint(tool_name: str, arguments: dict[str, Any]) -> str:
    """Bind an approval to the exact reviewed tool + JSON arguments."""

    if not isinstance(tool_name, str) or not tool_name.strip():
        raise ValueError("tool_name must be a non-empty string")
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    try:
        serialized = json.dumps(
            {"tool": tool_name.strip(), "arguments": arguments},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("approval arguments must be JSON-serializable") from exc
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ApprovalGrant:
    """Proof that a reviewer approved one exact proposed action payload."""

    tool_name: str
    arguments_fingerprint: str
    reviewer_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            raise ValueError("tool_name must be a non-empty string")
        if (
            not isinstance(self.arguments_fingerprint, str)
            or len(self.arguments_fingerprint) != 64
            or any(char not in "0123456789abcdef" for char in self.arguments_fingerprint)
        ):
            raise ValueError("arguments_fingerprint must be a lowercase SHA-256 hex digest")
        if not isinstance(self.reviewer_id, str) or not self.reviewer_id.strip():
            raise ValueError("reviewer_id must be a non-empty string")

    @classmethod
    def issue(
        cls,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        reviewer_id: str,
    ) -> ApprovalGrant:
        if not isinstance(reviewer_id, str) or not reviewer_id.strip():
            raise ValueError("reviewer_id must be a non-empty string")
        return cls(
            tool_name=tool_name.strip(),
            arguments_fingerprint=action_fingerprint(tool_name, arguments),
            reviewer_id=reviewer_id.strip(),
        )

    def matches(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        return (
            self.tool_name == tool_name
            and self.arguments_fingerprint == action_fingerprint(tool_name, arguments)
        )


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    allowed: bool
    requires_approval: bool
    reason: str
    risk: RiskLevel | None = None


class AllowlistPermissionPolicy:
    """Default-deny role allowlist with optional exact-action approval binding."""

    def __init__(self, rules: list[ToolPermissionRule] | None = None) -> None:
        self._rules: dict[str, ToolPermissionRule] = {}
        for rule in rules or []:
            if rule.tool_name in self._rules:
                raise ValueError(f"duplicate permission rule for tool: {rule.tool_name}")
            self._rules[rule.tool_name] = rule

    def evaluate(
        self,
        *,
        tool_name: str,
        principal: Principal,
        arguments: dict[str, Any],
        approval: ApprovalGrant | None = None,
    ) -> PermissionDecision:
        rule = self._rules.get(tool_name)
        if rule is None:
            return PermissionDecision(
                False,
                False,
                "Tool is not present in the application allowlist.",
            )

        if principal.roles.isdisjoint(rule.allowed_roles):
            # Approval cannot repair an authorization failure. Mark this as a
            # pure permission denial so callers do not route it to an approval
            # workflow and accidentally suggest that "more approval" grants a
            # role the principal does not have.
            return PermissionDecision(
                False,
                False,
                "Principal does not have an allowed role for this tool.",
                rule.risk,
            )

        if rule.requires_approval:
            if approval is None:
                return PermissionDecision(
                    False,
                    True,
                    "This tool requires human approval before execution.",
                    rule.risk,
                )
            if not approval.matches(tool_name, arguments):
                return PermissionDecision(
                    False,
                    True,
                    "Approval does not match the exact reviewed action arguments.",
                    rule.risk,
                )

        return PermissionDecision(True, rule.requires_approval, "Permission policy allowed execution.", rule.risk)

    def enforce(
        self,
        *,
        tool_name: str,
        principal: Principal,
        arguments: dict[str, Any],
        approval: ApprovalGrant | None = None,
    ) -> None:
        decision = self.evaluate(
            tool_name=tool_name,
            principal=principal,
            arguments=arguments,
            approval=approval,
        )
        if decision.allowed:
            return
        if decision.requires_approval:
            raise ToolApprovalRequired(decision.reason)
        raise ToolPermissionError(decision.reason)

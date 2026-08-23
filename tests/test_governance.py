import pytest

from tiny_agent import (
    AllowlistPermissionPolicy,
    ApprovalGrant,
    Principal,
    ToolApprovalRequired,
    ToolPermissionError,
    ToolPermissionRule,
    action_fingerprint,
)


def make_policy() -> AllowlistPermissionPolicy:
    return AllowlistPermissionPolicy(
        [
            ToolPermissionRule(
                tool_name="read_report",
                allowed_roles=frozenset({"analyst", "admin"}),
                risk="low",
            ),
            ToolPermissionRule(
                tool_name="delete_report",
                allowed_roles=frozenset({"admin"}),
                requires_approval=True,
                risk="high",
            ),
        ]
    )


def test_permission_policy_is_default_deny():
    decision = make_policy().evaluate(
        tool_name="mystery_tool",
        principal=Principal("user-1", frozenset({"admin"})),
        arguments={},
    )

    assert decision.allowed is False
    assert "allowlist" in decision.reason


def test_role_allowlist_allows_matching_principal():
    decision = make_policy().evaluate(
        tool_name="read_report",
        principal=Principal("user-1", frozenset({"analyst"})),
        arguments={"report_id": "r-7"},
    )

    assert decision.allowed is True


def test_approval_does_not_replace_role_authorization():
    args = {"report_id": "r-7"}
    grant = ApprovalGrant.issue(
        tool_name="delete_report",
        arguments=args,
        reviewer_id="reviewer-9",
    )

    decision = make_policy().evaluate(
        tool_name="delete_report",
        principal=Principal("intern-1", frozenset({"analyst"})),
        arguments=args,
        approval=grant,
    )

    assert decision.allowed is False
    assert decision.requires_approval is False
    assert "allowed role" in decision.reason

    with pytest.raises(ToolPermissionError):
        make_policy().enforce(
            tool_name="delete_report",
            principal=Principal("intern-1", frozenset({"analyst"})),
            arguments=args,
            approval=grant,
        )


def test_high_risk_tool_requires_approval():
    decision = make_policy().evaluate(
        tool_name="delete_report",
        principal=Principal("admin-1", frozenset({"admin"})),
        arguments={"report_id": "r-7"},
    )

    assert decision.allowed is False
    assert decision.requires_approval is True

    with pytest.raises(ToolApprovalRequired):
        make_policy().enforce(
            tool_name="delete_report",
            principal=Principal("admin-1", frozenset({"admin"})),
            arguments={"report_id": "r-7"},
        )


def test_approval_is_bound_to_exact_reviewed_arguments():
    reviewed = {"environment": "staging"}
    grant = ApprovalGrant.issue(
        tool_name="delete_report",
        arguments=reviewed,
        reviewer_id="reviewer-9",
    )

    assert grant.matches("delete_report", reviewed) is True
    assert grant.matches("delete_report", {"environment": "production"}) is False


def test_approval_grant_validates_direct_construction_too():
    with pytest.raises(ValueError, match="SHA-256"):
        ApprovalGrant(
            tool_name="delete_report",
            arguments_fingerprint="not-a-digest",
            reviewer_id="reviewer-9",
        )
    with pytest.raises(ValueError, match="reviewer_id"):
        ApprovalGrant(
            tool_name="delete_report",
            arguments_fingerprint="a" * 64,
            reviewer_id=" ",
        )


def test_fingerprint_is_stable_across_argument_key_order():
    assert action_fingerprint("tool", {"a": 1, "b": 2}) == action_fingerprint(
        "tool", {"b": 2, "a": 1}
    )

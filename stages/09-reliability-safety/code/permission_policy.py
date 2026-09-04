"""Stage 09 example 5: default-deny roles and exact-action approval binding."""

from tiny_agent import (
    AllowlistPermissionPolicy,
    ApprovalGrant,
    Principal,
    ToolPermissionRule,
)


policy = AllowlistPermissionPolicy(
    [
        ToolPermissionRule(
            tool_name="read_report",
            allowed_roles=frozenset({"analyst", "admin"}),
            risk="low",
        ),
        ToolPermissionRule(
            tool_name="deploy",
            allowed_roles=frozenset({"operator", "admin"}),
            requires_approval=True,
            risk="high",
        ),
    ]
)

operator = Principal("operator-7", frozenset({"operator"}))
arguments = {"environment": "staging", "release": "v0.7.0"}

before_review = policy.evaluate(
    tool_name="deploy",
    principal=operator,
    arguments=arguments,
)
print("Before approval:", before_review)

grant = ApprovalGrant.issue(
    tool_name="deploy",
    arguments=arguments,
    reviewer_id="reviewer-2",
)

after_review = policy.evaluate(
    tool_name="deploy",
    principal=operator,
    arguments=arguments,
    approval=grant,
)
print("After exact-action approval:", after_review)

changed = policy.evaluate(
    tool_name="deploy",
    principal=operator,
    arguments={"environment": "production", "release": "v0.7.0"},
    approval=grant,
)
print("Reusing staging approval for production:", changed)

# Human approval is not a wildcard capability token.
# It is bound to the exact action that was reviewed.

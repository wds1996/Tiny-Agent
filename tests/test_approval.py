import pytest

from tiny_agent import (
    ApprovalDecision,
    ApprovalRequest,
    resolve_approval,
)


def make_request() -> ApprovalRequest:
    return ApprovalRequest(
        action="send_email",
        arguments={"to": "alice@example.com", "subject": "Release"},
        reason="External communication has a real side effect.",
        risk="high",
    )


def test_approval_request_payload_is_serializable_policy_data():
    payload = make_request().to_interrupt_payload()

    assert payload["type"] == "tool_approval"
    assert payload["action"] == "send_email"
    assert payload["allowed_decisions"] == ["approve", "edit", "reject"]


def test_approve_preserves_original_arguments():
    request = make_request()
    resolution = resolve_approval(request, ApprovalDecision(outcome="approve"))

    assert resolution.approved is True
    assert resolution.arguments == request.arguments
    assert resolution.arguments is not request.arguments


def test_edit_uses_human_supplied_arguments():
    request = make_request()
    decision = ApprovalDecision(
        outcome="edit",
        edited_arguments={"to": "bob@example.com", "subject": "Release"},
        feedback="Use the release owner instead.",
    )

    resolution = resolve_approval(request, decision)

    assert resolution.approved is True
    assert resolution.arguments == {
        "to": "bob@example.com",
        "subject": "Release",
    }
    assert resolution.feedback == "Use the release owner instead."


def test_edit_requires_edited_arguments():
    with pytest.raises(ValueError):
        resolve_approval(make_request(), ApprovalDecision(outcome="edit"))


def test_reject_does_not_return_executable_arguments():
    resolution = resolve_approval(
        make_request(),
        ApprovalDecision(outcome="reject", feedback="Do not send this message."),
    )

    assert resolution.approved is False
    assert resolution.arguments is None


def test_decision_payload_is_validated():
    with pytest.raises(ValueError):
        ApprovalDecision.from_payload({"outcome": "maybe"})
    with pytest.raises(ValueError):
        ApprovalDecision.from_payload(
            {"outcome": "edit", "edited_arguments": "not-an-object"}
        )

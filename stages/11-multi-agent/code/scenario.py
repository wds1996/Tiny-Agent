"""One pilot assessment, shared by the single-worker and team experiments."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from team import AgentMessage, AgentSpec, Finding, Principal, TeamLimits, TeamPolicy, TeamRuntime


ASSIGNMENTS = {
    "operations": "Establish the proposed pilot size and whether measured outcomes exist. Do not approve rollout.",
    "risk": "Establish the refund boundary and whether real conversation data needs privacy review.",
    "privacy": "Take over the privacy clarification. Ask what consent and redaction controls exist; do not approve data use.",
}
CONTEXT_KEYS = {
    "operations": ("brief", "operations_note"),
    "risk": ("brief", "policy_note"),
    "privacy": ("brief",),
}


def make_context(*, real_data: bool = False) -> dict[str, Any]:
    return {
        "brief": {"goal": "Assess a proposed support-assistant pilot.",
                  "use_real_conversations": real_data},
        "operations_note": {"source_id": "ops-01", "staff": 20,
                            "measured_results": False, "refunds_allowed": False},
        "policy_note": {"source_id": "policy-01", "refunds_allowed": False,
                        "real_data_requires_review": True},
        "private_note": "SYNTHETIC-PRIVATE-NOTE: never forward this field",
    }


def operations(assignment: str, context: dict[str, Any]) -> Finding:
    del assignment
    note = context.get("operations_note")
    if note is None:
        return Finding("needs_input", "The pilot plan is missing.")
    if type(note.get("staff")) is not int or note["staff"] <= 0:
        return Finding("needs_input", "A positive pilot staff count is required.")
    if type(note.get("measured_results")) is not bool or type(note.get("refunds_allowed")) is not bool:
        return Finding("needs_input", "The pilot record is incomplete.")
    facts = {key: note[key] for key in ("staff", "measured_results", "refunds_allowed")}
    return Finding("ok", "Pilot scope extracted; this is not evidence of effectiveness.",
                   facts, (note["source_id"],))


def risk(assignment: str, context: dict[str, Any]) -> Finding:
    del assignment
    note = context.get("policy_note")
    if note is None:
        return Finding("needs_input", "The applicable policy is missing.")
    brief = context.get("brief", {})
    if (type(note.get("refunds_allowed")) is not bool
            or type(note.get("real_data_requires_review")) is not bool
            or type(brief.get("use_real_conversations")) is not bool):
        return Finding("needs_input", "Policy or intended data use is incomplete.")
    return Finding("ok", "Reply suggestions and refund execution are different permissions.",
                   {"refunds_allowed": note["refunds_allowed"],
                    "privacy_review_required": brief["use_real_conversations"] and note["real_data_requires_review"]},
                   (note["source_id"],))


def privacy(assignment: str, context: dict[str, Any]) -> Finding:
    del assignment
    findings = context.get("handoff", {}).get("findings", [])
    sources = tuple(dict.fromkeys(source for item in findings for source in item["evidence_ids"]))
    return Finding("needs_input", "Before using real conversations, provide consent and redaction controls.",
                   {"question": "What consent and redaction controls cover the proposed data?"}, sources)


@dataclass(frozen=True)
class Assessment:
    status: str
    summary: str
    evidence_ids: tuple[str, ...]


def combine(findings: dict[str, Finding]) -> Assessment:
    """Conservative domain merge, not majority voting or free-form summarization."""
    required = ("operations", "risk")
    if any(name not in findings for name in required):
        return Assessment("needs_input", "Both the pilot plan and policy must be examined.", ())
    items = [findings[name] for name in required]
    sources = tuple(dict.fromkeys(s for item in items for s in item.evidence_ids))
    if any(item.status == "failed" for item in items):
        return Assessment("failed", "Assessment incomplete: a specialist failed, not a policy rejection.", sources)
    if any(item.status != "ok" for item in items):
        return Assessment("needs_input", "Assessment incomplete: required information is missing.", sources)
    op, rule = (item.facts for item in items)
    if (type(op.get("staff")) is not int or op["staff"] <= 0
            or type(op.get("measured_results")) is not bool
            or type(op.get("refunds_allowed")) is not bool
            or type(rule.get("refunds_allowed")) is not bool
            or type(rule.get("privacy_review_required")) is not bool
            or not all(item.evidence_ids for item in items)):
        return Assessment("needs_input", "Accepted envelopes still need valid domain facts and sources.", sources)
    if op["refunds_allowed"] != rule["refunds_allowed"]:
        return Assessment("conflict", "Plan and policy disagree about refund authority; reconcile them before proceeding.", sources)
    if rule["privacy_review_required"]:
        return Assessment("needs_review", "Real conversation data requires privacy clarification before proceeding.", sources)
    results = "Measured outcomes are available for separate review." if op["measured_results"] else "No pilot results exist yet."
    permission = "Refund authority is indicated in both supplied records." if rule["refunds_allowed"] else "The assistant may suggest replies, not execute refunds."
    return Assessment("ready_for_draft", f"Prepare an assessment for {op['staff']} staff. {results} {permission} This does not authorize deployment.", sources)


def from_messages(messages: tuple[AgentMessage, ...]) -> Assessment:
    if len({message.run_id for message in messages}) > 1:
        raise ValueError("cannot combine findings from different runs")
    if len({message.agent for message in messages}) != len(messages):
        raise ValueError("select one result per specialist explicitly")
    return combine({message.agent: message.finding for message in messages})


def build_team(context: dict[str, Any], *, run_id: str = "pilot-001",
               limits: TeamLimits = TeamLimits(),
               handlers: dict[str, Callable] | None = None,
               principal: Principal | None = None) -> TeamRuntime:
    functions = {"operations": operations, "risk": risk, "privacy": privacy}
    functions.update(handlers or {})
    specs = [AgentSpec(name, ASSIGNMENTS[name], CONTEXT_KEYS[name], functions[name],
                       ("risk",) if name == "privacy" else ()) for name in functions]
    grants = {
        ("delegate", "coordinator", "operations"): frozenset({"analyst"}),
        ("delegate", "coordinator", "risk"): frozenset({"analyst"}),
        ("handoff", "coordinator", "privacy"): frozenset({"analyst"}),
    }
    return TeamRuntime(specs, run_id=run_id,
                       principal=principal or Principal("lin", frozenset({"analyst"})),
                       context=context, policy=TeamPolicy(grants), limits=limits)

from __future__ import annotations

import argparse
from pathlib import Path

from approval import CREATE_SUPPORT_CASE, ApprovalDecision, ReviewerContext
from durable_workflow import SQLiteWorkflowStore, SupportCaseWorkflow
from memory import (
    ConservativeMemoryWritePolicy,
    MemoryCandidate,
    SQLiteMemoryStore,
    store_if_allowed,
)


DEFAULT_RUN_ID = "acme-case-run-001"
DEFAULT_THREAD_ID = "acme-refund-thread-001"
DEFAULT_OWNER_ID = "user-7"
DEFAULT_ORDER_ID = "ACME-1007"
DEFAULT_REASON = "Customer requests review of a day-38 original-payment refund."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage 06 durable HITL teaching demo")
    parser.add_argument("--db", default="stage06-demo.db", help="SQLite file shared by separate runs")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="save memory + pause a support-case action for approval")
    start.add_argument("--run-id", default=DEFAULT_RUN_ID)
    start.add_argument("--thread-id", default=DEFAULT_THREAD_ID)
    start.add_argument("--owner-id", default=DEFAULT_OWNER_ID)
    start.add_argument("--order-id", default=DEFAULT_ORDER_ID)
    start.add_argument("--reason", default=DEFAULT_REASON)

    show = sub.add_parser("show", help="open the same database in a new process and inspect durable data")
    show.add_argument("--run-id", default=DEFAULT_RUN_ID)
    show.add_argument("--owner-id", default=DEFAULT_OWNER_ID)

    resume = sub.add_parser("resume", help="apply an authorized human review decision")
    resume.add_argument("--run-id", default=DEFAULT_RUN_ID)
    resume.add_argument("--decision", choices=("approve", "edit", "reject"), required=True)
    resume.add_argument("--edited-reason")
    resume.add_argument("--reviewer-id", default="reviewer-1")
    return parser


def command_start(args: argparse.Namespace) -> int:
    path = Path(args.db)
    workflow = SupportCaseWorkflow(SQLiteWorkflowStore(path))
    request = workflow.start(
        run_id=args.run_id,
        thread_id=args.thread_id,
        owner_id=args.owner_id,
        order_id=args.order_id,
        reason=args.reason,
    )

    candidate = MemoryCandidate(
        owner_id=args.owner_id,
        key="answer-style",
        value={"language": "Chinese", "style": "concise"},
        kind="semantic",
        explicit_user_request=True,
        source_thread_id=args.thread_id,
    )
    memory_decision = store_if_allowed(
        store=SQLiteMemoryStore(path),
        policy=ConservativeMemoryWritePolicy(),
        candidate=candidate,
    )

    print("checkpoint:", request)
    print("memory decision:", memory_decision)
    print("process may exit now; durable data is stored in:", path)
    return 0


def command_show(args: argparse.Namespace) -> int:
    path = Path(args.db)
    state = SQLiteWorkflowStore(path).load(args.run_id)
    memory = SQLiteMemoryStore(path).get(args.owner_id, "answer-style")
    print("restored state:", state)
    print("restored memory:", memory)
    return 0


def command_resume(args: argparse.Namespace) -> int:
    path = Path(args.db)
    workflow = SupportCaseWorkflow(SQLiteWorkflowStore(path))
    request = workflow.approval_request(args.run_id)

    if args.decision == "edit":
        if not args.edited_reason:
            raise SystemExit("--edited-reason is required for --decision edit")
        edited_arguments = {
            "order_id": request.arguments["order_id"],
            "reason": args.edited_reason,
        }
    else:
        edited_arguments = None

    decision = ApprovalDecision(args.decision, edited_arguments)
    reviewer = ReviewerContext(
        reviewer_id=args.reviewer_id,
        allowed_actions=frozenset({CREATE_SUPPORT_CASE}),
    )
    final = workflow.resume(args.run_id, decision, reviewer=reviewer)
    print("final state:", final)
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "start":
        return command_start(args)
    if args.command == "show":
        return command_show(args)
    if args.command == "resume":
        return command_resume(args)
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())

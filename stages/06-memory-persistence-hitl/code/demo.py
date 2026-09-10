from __future__ import annotations

from pathlib import Path
import tempfile

from approval import ApprovalDecision
from durable_workflow import RefundWorkflow, SQLiteCheckpointStore
from memory import ConservativeMemoryWritePolicy, MemoryCandidate, SQLiteMemoryStore


def read_approval_decision() -> ApprovalDecision:
    while True:
        outcome = input("Review outcome [approve/edit/reject]: ").strip().lower()
        if outcome == "approve":
            return ApprovalDecision(outcome="approve")
        if outcome == "reject":
            return ApprovalDecision(outcome="reject")
        if outcome == "edit":
            order_id = input("Edited order ID: ").strip()
            amount = input("Edited refund amount: ").strip()
            return ApprovalDecision(
                outcome="edit",
                edited_arguments={"order_id": order_id, "amount": amount},
            )
        print("Enter approve, edit, or reject.")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "agent.db"

        runtime_a = RefundWorkflow(SQLiteCheckpointStore(db))
        request = runtime_a.start(
            run_id="run-001",
            order_id="ORDER-42",
            amount="18.50",
        )
        print("paused:", request)

        # Pretend the original process disappeared here.
        print("\nProcess disappeared. A new runtime opens the same checkpoint file.")
        runtime_b = RefundWorkflow(SQLiteCheckpointStore(db))

        while True:
            decision = read_approval_decision()
            try:
                final = runtime_b.resume("run-001", decision)
            except ValueError as exc:
                print(f"Review input was rejected: {exc}\n")
                continue
            break

        print("resumed:", final.phase, final.result)

        memory_store = SQLiteMemoryStore(db)
        candidate = MemoryCandidate(
            owner_id="user-7",
            key="answer-style",
            value={"language": "Chinese", "style": "concise"},
            kind="semantic",
            explicit_user_request=True,
        )
        policy = ConservativeMemoryWritePolicy()
        decision = policy.evaluate(candidate)
        if decision.store:
            memory_store.put(candidate)
        print("memory:", memory_store.get("user-7", "answer-style"))


if __name__ == "__main__":
    main()

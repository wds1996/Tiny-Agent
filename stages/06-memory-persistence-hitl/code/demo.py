from __future__ import annotations

from pathlib import Path
import tempfile

from approval import ApprovalDecision
from durable_workflow import RefundWorkflow, SQLiteCheckpointStore
from memory import ConservativeMemoryWritePolicy, MemoryCandidate, SQLiteMemoryStore


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
        runtime_b = RefundWorkflow(SQLiteCheckpointStore(db))
        final = runtime_b.resume(
            "run-001",
            ApprovalDecision(outcome="approve"),
        )
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

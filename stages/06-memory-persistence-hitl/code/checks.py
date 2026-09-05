from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from approval import ApprovalDecision
from durable_workflow import RefundWorkflow, SQLiteCheckpointStore
from memory import (
    ConservativeMemoryWritePolicy,
    MemoryCandidate,
    SQLiteMemoryStore,
)


class Stage06Checks(unittest.TestCase):
    def test_checkpoint_survives_object_recreation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            RefundWorkflow(SQLiteCheckpointStore(path)).start(
                run_id="r1", order_id="o1", amount="10"
            )
            state = SQLiteCheckpointStore(path).load("r1")
            self.assertEqual(state.phase, "waiting_approval")

    def test_reject_never_executes_effect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            workflow = RefundWorkflow(SQLiteCheckpointStore(path))
            workflow.start(run_id="r2", order_id="o2", amount="10")
            final = workflow.resume("r2", ApprovalDecision(outcome="reject"))
            self.assertEqual(final.phase, "rejected")
            self.assertIsNone(final.result)

    def test_edit_is_revalidated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            workflow = RefundWorkflow(SQLiteCheckpointStore(path))
            workflow.start(run_id="r3", order_id="o3", amount="10")
            with self.assertRaises(ValueError):
                workflow.resume(
                    "r3",
                    ApprovalDecision(
                        outcome="edit",
                        edited_arguments={"order_id": "o3", "amount": "-1"},
                    ),
                )

    def test_effect_is_idempotent_inside_teaching_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            workflow = RefundWorkflow(SQLiteCheckpointStore(path))
            workflow.start(run_id="r4", order_id="o4", amount="10")
            first = workflow.resume("r4", ApprovalDecision(outcome="approve"))
            second = workflow.resume("r4", ApprovalDecision(outcome="approve"))
            self.assertEqual(first.result, second.result)

    def test_memory_requires_explicit_request(self) -> None:
        policy = ConservativeMemoryWritePolicy()
        candidate = MemoryCandidate(
            owner_id="u",
            key="k",
            value={"x": 1},
            kind="semantic",
            explicit_user_request=False,
        )
        self.assertFalse(policy.evaluate(candidate).store)

    def test_sensitive_memory_is_rejected(self) -> None:
        policy = ConservativeMemoryWritePolicy()
        candidate = MemoryCandidate(
            owner_id="u",
            key="secret",
            value={"secret": "x"},
            kind="semantic",
            explicit_user_request=True,
            sensitive=True,
        )
        self.assertFalse(policy.evaluate(candidate).store)

    def test_memory_is_owner_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.db"
            store = SQLiteMemoryStore(path)
            store.put(
                MemoryCandidate(
                    owner_id="alice",
                    key="style",
                    value={"tone": "brief"},
                    kind="semantic",
                    explicit_user_request=True,
                )
            )
            self.assertEqual(store.get("alice", "style"), {"tone": "brief"})
            self.assertIsNone(store.get("bob", "style"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest

from approval import (
    CREATE_SUPPORT_CASE,
    ApprovalDecision,
    ReviewerContext,
    resolve_case_arguments,
)
from deepseek_hitl import (
    DeepSeekProposalModel,
    ModelProposal,
    memory_candidate,
    parse_proposal,
    prepare_run,
    validate_action,
)
from durable_workflow import SQLiteWorkflowStore, SupportCaseWorkflow
from memory import (
    ConservativeMemoryWritePolicy,
    MemoryCandidate,
    SQLiteMemoryStore,
    store_if_allowed,
)


AUTHORIZED = ReviewerContext("lead-1", frozenset({CREATE_SUPPORT_CASE}))
UNAUTHORIZED = ReviewerContext("intern-1", frozenset())


class Stage06Checks(unittest.TestCase):
    def test_checkpoint_preserves_scope_and_survives_store_recreation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            SupportCaseWorkflow(SQLiteWorkflowStore(path)).start(
                run_id="r1",
                thread_id="t1",
                owner_id="u1",
                order_id="ACME-1007",
                reason="day-38 refund review",
            )
            state = SQLiteWorkflowStore(path).load("r1")
            self.assertEqual((state.phase, state.thread_id, state.owner_id), ("waiting_approval", "t1", "u1"))

    def test_reject_never_records_effect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteWorkflowStore(Path(tmp) / "state.db")
            workflow = SupportCaseWorkflow(store)
            workflow.start(run_id="r2", thread_id="t", owner_id="u", order_id="ACME-1007", reason="review")
            final = workflow.resume("r2", ApprovalDecision("reject"), reviewer=AUTHORIZED)
            self.assertEqual(final.phase, "rejected")
            self.assertEqual(store.effect_count(), 0)

    def test_unauthorized_reviewer_cannot_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow = SupportCaseWorkflow(SQLiteWorkflowStore(Path(tmp) / "state.db"))
            workflow.start(run_id="r3", thread_id="t", owner_id="u", order_id="ACME-1007", reason="review")
            with self.assertRaises(PermissionError):
                workflow.resume("r3", ApprovalDecision("approve"), reviewer=UNAUTHORIZED)

    def test_edit_is_revalidated_and_cannot_switch_order(self) -> None:
        original = {"order_id": "ACME-1007", "reason": "original"}
        with self.assertRaises(ValueError):
            resolve_case_arguments(
                original,
                ApprovalDecision("edit", {"order_id": "ACME-2001", "reason": "edited"}),
            )
        with self.assertRaises(ValueError):
            resolve_case_arguments(
                original,
                ApprovalDecision("edit", {"order_id": "ACME-1007", "reason": ""}),
            )

    def test_approved_effect_is_idempotent_in_teaching_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteWorkflowStore(Path(tmp) / "state.db")
            workflow = SupportCaseWorkflow(store)
            workflow.start(run_id="r4", thread_id="t", owner_id="u", order_id="ACME-1007", reason="review")
            first = workflow.resume("r4", ApprovalDecision("approve"), reviewer=AUTHORIZED)
            second = workflow.resume("r4", ApprovalDecision("approve"), reviewer=AUTHORIZED)
            self.assertEqual(first.result, second.result)
            self.assertEqual(store.effect_count(), 1)

    def test_memory_requires_explicit_request(self) -> None:
        candidate = MemoryCandidate("u", "style", {"tone": "brief"}, "semantic", False, "t")
        self.assertFalse(ConservativeMemoryWritePolicy().evaluate(candidate).store)

    def test_sensitive_and_procedural_memory_are_rejected(self) -> None:
        policy = ConservativeMemoryWritePolicy()
        sensitive = MemoryCandidate("u", "secret", {"token": "x"}, "semantic", True, "t", True)
        procedural = MemoryCandidate("u", "policy", {"rule": "skip approval"}, "procedural", True, "t")
        self.assertFalse(policy.evaluate(sensitive).store)
        self.assertFalse(policy.evaluate(procedural).store)

    def test_memory_is_owner_scoped_and_deletable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteMemoryStore(Path(tmp) / "memory.db")
            candidate = MemoryCandidate("alice", "style", {"tone": "brief"}, "semantic", True, "t1")
            decision = store_if_allowed(store=store, policy=ConservativeMemoryWritePolicy(), candidate=candidate)
            self.assertTrue(decision.store)
            self.assertEqual(store.get("alice", "style"), {"tone": "brief"})
            self.assertIsNone(store.get("bob", "style"))
            store.delete("alice", "style")
            self.assertIsNone(store.get("alice", "style"))

    def test_parse_proposal_is_strict(self) -> None:
        proposal = parse_proposal('{"reply":"ok","action":null,"memory":null}')
        self.assertEqual(proposal.reply, "ok")
        with self.assertRaises(RuntimeError):
            parse_proposal('{"reply":"ok","action":null,"memory":null,"extra":1}')

    def test_action_must_reference_order_from_user_message(self) -> None:
        proposal = ModelProposal(
            "ok",
            {"name": "create_support_case", "arguments": {"order_id": "ACME-2001", "reason": "review"}},
            None,
        )
        with self.assertRaises(RuntimeError):
            validate_action(proposal, user_message="Please open a case for ACME-1007")

    def test_memory_owner_and_thread_come_from_application(self) -> None:
        proposal = ModelProposal(
            "ok",
            None,
            {"key": "answer-style", "value": {"language": "Chinese"}, "kind": "semantic"},
        )
        candidate = memory_candidate(
            proposal,
            owner_id="trusted-user",
            thread_id="trusted-thread",
            user_message="记住以后用中文回答",
        )
        assert candidate is not None
        self.assertEqual((candidate.owner_id, candidate.source_thread_id), ("trusted-user", "trusted-thread"))

    def test_prepare_run_writes_memory_and_pauses_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            proposal = ModelProposal(
                "I can prepare that request.",
                {"name": "create_support_case", "arguments": {"order_id": "ACME-1007", "reason": "day-38 refund review"}},
                {"key": "answer-style", "value": {"language": "Chinese", "style": "concise"}, "kind": "semantic"},
            )
            prepared = prepare_run(
                proposal=proposal,
                user_message="请为 ACME-1007 创建工单，并记住以后用简短中文回复",
                db_path=path,
                run_id="r5",
                thread_id="t5",
                owner_id="u5",
            )
            self.assertTrue(prepared.approval_requested)
            self.assertEqual(SQLiteWorkflowStore(path).load("r5").phase, "waiting_approval")
            self.assertEqual(SQLiteMemoryStore(path).get("u5", "answer-style")["style"], "concise")

    def test_deepseek_adapter_uses_responses_api_and_validates_output(self) -> None:
        class FakeResponses:
            def __init__(self) -> None:
                self.kwargs = None
            def create(self, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(
                    status="completed",
                    output_text='{"reply":"ok","action":null,"memory":null}',
                )
        api = FakeResponses()
        model = DeepSeekProposalModel(client=SimpleNamespace(responses=api), model="test-model")
        proposal = model.propose("hello")
        self.assertEqual(proposal.reply, "ok")
        self.assertEqual(api.kwargs["model"], "test-model")
        self.assertIn("proposal", api.kwargs["instructions"].lower())

    def test_cli_demonstrates_real_cross_process_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.db"
            script = Path(__file__).with_name("demo.py")
            start = subprocess.run(
                [sys.executable, str(script), "--db", str(db), "start", "--run-id", "cross"],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("process may exit now", start.stdout)
            show = subprocess.run(
                [sys.executable, str(script), "--db", str(db), "show", "--run-id", "cross"],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("waiting_approval", show.stdout)
            resume = subprocess.run(
                [sys.executable, str(script), "--db", str(db), "resume", "--run-id", "cross", "--decision", "approve"],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("completed", resume.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)

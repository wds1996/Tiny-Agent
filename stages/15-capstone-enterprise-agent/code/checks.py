from pathlib import Path
import tempfile
import unittest

from agent import ApprovalDecision, SupportAgent
from domain import TrustedIdentity
from store import SupportStore


class Stage15Checks(unittest.TestCase):
    def make(self, tmp):
        store = SupportStore(Path(tmp) / "support.db")
        return store, SupportAgent(store)

    def identity(self):
        return TrustedIdentity("acme", "alice")

    def test_policy_answer_contains_evidence_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, agent = self.make(tmp)
            result = agent.run(
                identity=self.identity(),
                question="What is the refund policy?",
            )
            self.assertTrue(result.evidence_ids)
            self.assertIn("[refund-within-30-days]", result.answer)

    def test_unknown_policy_abstains(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, agent = self.make(tmp)
            result = agent.run(
                identity=self.identity(),
                question="What is the lunar teleportation warranty?",
            )
            self.assertFalse(result.evidence_ids)
            self.assertIn("not have enough policy evidence", result.answer)
            self.assertIn("answer:abstain", result.trace)

    def test_order_access_is_identity_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, agent = self.make(tmp)
            result = agent.run(
                identity=TrustedIdentity("acme", "bob"),
                question="Can ORDER-42 be refunded?",
            )
            self.assertIn("cannot find an accessible order", result.answer)

    def test_refund_proposal_uses_order_amount_not_user_amount(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, agent = self.make(tmp)
            result = agent.run(
                identity=self.identity(),
                question="Please refund ORDER-42 for 9999.",
            )
            self.assertEqual(result.status, "waiting_approval")
            self.assertEqual(result.approval.amount, "49.00")

    def test_late_order_does_not_create_refund_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, agent = self.make(tmp)
            result = agent.run(
                identity=self.identity(),
                question="Please refund ORDER-99.",
            )
            self.assertEqual(result.status, "completed")
            self.assertIsNone(result.approval)
            self.assertIn("store credit", result.answer)

    def test_reject_executes_no_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, agent = self.make(tmp)
            proposal = agent.run(
                identity=self.identity(),
                question="Please refund ORDER-42.",
            )
            result = agent.resume_refund(
                identity=self.identity(),
                run_id=proposal.run_id,
                decision=ApprovalDecision(outcome="reject"),
            )
            self.assertEqual(result.status, "rejected")
            self.assertEqual(store.effect_count(), 0)

    def test_edit_cannot_increase_refund(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, agent = self.make(tmp)
            proposal = agent.run(
                identity=self.identity(),
                question="Please refund ORDER-42.",
            )
            with self.assertRaises(ValueError):
                agent.resume_refund(
                    identity=self.identity(),
                    run_id=proposal.run_id,
                    decision=ApprovalDecision(outcome="edit", amount="50.00"),
                )

    def test_refund_effect_is_idempotent_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, agent = self.make(tmp)
            proposal = agent.run(
                identity=self.identity(),
                question="Please refund ORDER-42.",
            )
            first = agent.resume_refund(
                identity=self.identity(),
                run_id=proposal.run_id,
                decision=ApprovalDecision(outcome="approve"),
            )
            second = agent.resume_refund(
                identity=self.identity(),
                run_id=proposal.run_id,
                decision=ApprovalDecision(outcome="approve"),
            )
            self.assertEqual(first.answer, second.answer)
            self.assertEqual(store.effect_count(), 1)

    def test_run_is_not_visible_to_another_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, agent = self.make(tmp)
            result = agent.run(identity=self.identity(), question="Hello")
            with self.assertRaises(KeyError):
                store.get_run(
                    result.run_id,
                    tenant_id="acme",
                    user_id="bob",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)

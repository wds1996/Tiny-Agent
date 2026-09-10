import unittest

from context import (
    ContextBudget,
    ContextBuilder,
    ContextItem,
    ContextOverflowError,
)
from compaction import Message, compact_history, split_history
from deepseek_context import apply_priority_suggestions, parse_context_proposal


class Stage07Checks(unittest.TestCase):
    def test_required_items_always_survive(self) -> None:
        items = [
            ContextItem("rules", "r" * 20, "instructions", 100, True),
            ContextItem("question", "q" * 20, "user", 100, True),
            ContextItem("nice", "x" * 200, "optional", 99),
        ]
        result = ContextBuilder().build(items, ContextBudget(30))
        self.assertEqual({i.key for i in result.items}, {"rules", "question"})

    def test_required_overflow_fails_closed(self) -> None:
        items = [ContextItem("rules", "x" * 100, "instructions", 100, True)]
        with self.assertRaises(ContextOverflowError):
            ContextBuilder().build(items, ContextBudget(5))

    def test_priority_beats_input_order(self) -> None:
        items = [
            ContextItem("low", "x" * 40, "memory", 1),
            ContextItem("high", "y" * 40, "evidence", 10),
        ]
        result = ContextBuilder().build(items, ContextBudget(11))
        self.assertEqual([item.key for item in result.items], ["high"])

    def test_output_reservation_reduces_input_budget(self) -> None:
        budget = ContextBudget(max_input_tokens=100, reserved_output_tokens=25)
        self.assertEqual(budget.usable_input_tokens, 75)

    def test_duplicate_keys_are_rejected(self) -> None:
        items = [
            ContextItem("same", "a", "x", 1),
            ContextItem("same", "b", "x", 2),
        ]
        with self.assertRaises(ValueError):
            ContextBuilder().build(items, ContextBudget(100))

    def test_compaction_records_provenance(self) -> None:
        messages = [
            Message("1", "user", "first"),
            Message("2", "assistant", "second"),
            Message("3", "user", "latest"),
        ]
        compacted = compact_history(messages, keep_last=1)
        self.assertEqual(compacted.source_message_ids, ("1", "2"))
        self.assertIn("first", compacted.summary)

    def test_compaction_is_lossy_not_a_checkpoint(self) -> None:
        messages = [Message("1", "user", "x" * 300), Message("2", "user", "now")]
        compacted = compact_history(messages, keep_last=1)
        self.assertLess(len(compacted.summary), 300)

    def test_recent_history_is_retained_outside_the_summary(self) -> None:
        messages = [
            Message("1", "user", "older"),
            Message("2", "assistant", "also older"),
            Message("3", "tool", "recent observation"),
            Message("4", "user", "latest question detail"),
        ]
        older, recent = split_history(messages, keep_last=2)
        self.assertEqual([message.id for message in older], ["1", "2"])
        self.assertEqual([message.id for message in recent], ["3", "4"])
        compacted = compact_history(messages, keep_last=2)
        self.assertEqual(compacted.source_message_ids, ("1", "2"))

    def test_model_priority_proposal_is_checked_before_application_use(self) -> None:
        proposal = parse_context_proposal(
            """{
                "history_summary": "The user is planning a refund.",
                "priority_suggestions": [
                    {"key": "policy", "priority": 90, "reason": "It answers the question."},
                    {"key": "memory", "priority": 20, "reason": "It only controls style."}
                ]
            }""",
            optional_keys=("policy", "memory"),
        )
        self.assertEqual(proposal.source_message_ids, ())
        with self.assertRaises(RuntimeError):
            parse_context_proposal(
                """{
                    "history_summary": "The user is planning a refund.",
                    "source_message_ids": ["m1"],
                    "priority_suggestions": [
                        {"key": "policy", "priority": 90, "reason": "Relevant."},
                        {"key": "memory", "priority": 20, "reason": "Secondary."}
                    ]
                }""",
                optional_keys=("policy", "memory"),
            )
        items = [
            ContextItem("policy", "refund policy", "evidence", 0),
            ContextItem("memory", "concise Chinese", "memory", 0),
        ]
        ranked = apply_priority_suggestions(items, proposal)
        self.assertEqual([item.priority for item in ranked], [90, 20])
        self.assertEqual([item.provenance for item in ranked], ["application", "application"])
        with self.assertRaises(ValueError):
            apply_priority_suggestions(
                [ContextItem("policy", "refund policy", "evidence", 0, True)],
                proposal,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)

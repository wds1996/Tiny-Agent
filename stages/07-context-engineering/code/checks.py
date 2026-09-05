import unittest

from context import (
    ContextBudget,
    ContextBuilder,
    ContextItem,
    ContextOverflowError,
)
from compaction import Message, compact_history


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


if __name__ == "__main__":
    unittest.main(verbosity=2)

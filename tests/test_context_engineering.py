import pytest

from tiny_agent.context_engineering import (
    ContextBudget,
    ContextBudgetError,
    ContextBuilder,
    ContextItem,
    compact_items,
)


def test_context_builder_keeps_required_and_high_priority_items() -> None:
    budget = ContextBudget(max_context_tokens=100, reserve_output_tokens=20)
    items = [
        ContextItem("system", "system", "s" * 40, required=True),
        ContextItem("low", "history", "l" * 160, priority=1),
        ContextItem("high", "evidence", "h" * 160, priority=10),
    ]
    snapshot = ContextBuilder(budget).build(items)
    assert [item.key for item in snapshot.selected] == ["system", "high"]
    assert [item.key for item in snapshot.dropped] == ["low"]


def test_required_context_fails_closed_when_it_cannot_fit() -> None:
    builder = ContextBuilder(ContextBudget(max_context_tokens=10))
    with pytest.raises(ContextBudgetError):
        builder.build([ContextItem("system", "system", "x" * 100, required=True)])


def test_compaction_records_provenance_and_savings() -> None:
    items = [
        ContextItem("h1", "history", "alpha " * 40),
        ContextItem("h2", "history", "beta " * 40),
    ]
    record = compact_items(
        items,
        key="summary",
        summarizer=lambda values: "alpha and beta summary",
    )
    assert record.source_keys == ("h1", "h2")
    assert record.summary.provenance == "derived:compaction"
    assert record.saved_estimated_tokens > 0

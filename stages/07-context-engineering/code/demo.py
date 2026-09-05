from context import ContextBudget, ContextBuilder, ContextItem, render_context
from compaction import Message, compact_history


def main() -> None:
    history = [
        Message("m1", "user", "I am planning a refund for order ORDER-42."),
        Message("m2", "assistant", "I will check the policy before proposing an action."),
        Message("m3", "tool", "Policy: refunds within 30 days use the original payment method."),
        Message("m4", "user", "The order is 12 days old."),
    ]
    compacted = compact_history(history, keep_last=2)

    items = [
        ContextItem(
            key="instructions",
            content="Answer from supplied evidence. Do not invent missing policy.",
            kind="instructions",
            priority=100,
            required=True,
        ),
        ContextItem(
            key="current-question",
            content="Can ORDER-42 be refunded to the original payment method?",
            kind="user",
            priority=100,
            required=True,
        ),
        ContextItem(
            key="retrieved-policy",
            content="Refunds within 30 days use the original payment method.",
            kind="evidence",
            priority=90,
            provenance="policy-handbook",
        ),
        ContextItem(
            key="memory",
            content="User prefers concise Chinese answers.",
            kind="memory",
            priority=30,
            provenance="user-memory",
        ),
        ContextItem(
            key="old-summary",
            content=compacted.summary,
            kind="history-summary",
            priority=40,
            provenance="compactor",
        ),
    ]

    selection = ContextBuilder().build(
        items,
        ContextBudget(max_input_tokens=120, reserved_output_tokens=30),
    )
    print("used_tokens:", selection.used_tokens)
    print("omitted:", selection.omitted_keys)
    print(render_context(selection))


if __name__ == "__main__":
    main()

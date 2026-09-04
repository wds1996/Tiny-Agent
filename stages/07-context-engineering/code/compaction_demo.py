from tiny_agent.context_engineering import ContextItem, compact_items


old_history = [
    ContextItem("turn-1", "history", "User wants a production-minded Agent tutorial with runnable examples. " * 20),
    ContextItem("turn-2", "history", "Important exception: do not hide authorization inside prompts. " * 20),
]

record = compact_items(
    old_history,
    key="history-summary-1",
    summarizer=lambda items: (
        "The user wants runnable production-minded Agent examples. "
        "Authorization must remain deterministic application policy, not prompt text."
    ),
)

print("source keys:", record.source_keys)
print("summary provenance:", record.summary.provenance)
print("saved estimated tokens:", record.saved_estimated_tokens)
print(record.summary.content)

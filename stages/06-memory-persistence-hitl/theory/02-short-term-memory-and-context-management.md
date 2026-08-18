# Short-Term Memory and Context Management

Short-term memory sounds easy:

> Keep the conversation history.

Then the conversation becomes 800 messages long and your prompt starts looking like someone tried to move house by stuffing the entire apartment into one suitcase.

The real problem is not only remembering.

It is remembering **within a bounded model context**.

---

# 1. Short-term memory is thread-scoped state

With LangGraph:

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

config = {
    "configurable": {
        "thread_id": "conversation-123"
    }
}
```

Reuse the same `thread_id` to continue the same logical conversation/execution history.

Use another ID for another thread.

Current LangGraph documentation describes short-term memory as state persisted at thread scope through a checkpointer.

---

# 2. The checkpointer stores more than what the LLM should see

Suppose checkpointed state contains:

```python
{
    "messages": 300_messages,
    "retrieved_documents": [...],
    "approval": {...},
    "internal_retry_count": 3,
}
```

Do not automatically construct:

```python
prompt = str(all_state)
```

Persistence and context selection are separate steps.

A robust flow is:

```text
checkpointed thread state
        ↓
context management policy
        ↓
selected / summarized messages
        ↓
LLM context
```

---

# 3. Context windows are finite

Even when a model advertises a large context window, sending everything forever has costs:

- more input tokens;
- higher latency;
- higher cost;
- stale information competing with current information;
- increased prompt-injection surface;
- more opportunities for contradictory history;
- lower signal-to-noise ratio.

So:

```text
more history != more useful memory
```

---

# 4. Common context-management strategies

## A. Keep the last N messages

Simple:

```python
recent = messages[-20:]
```

Advantages:

- deterministic;
- cheap;
- easy to debug.

Disadvantages:

- important old facts may disappear;
- message length varies enormously.

A 20-message window can still be huge.

---

## B. Token-aware trimming

Better:

```text
newest messages first
        ↓
add until token budget reached
```

This respects actual context cost more directly.

But trimming is still forgetting by recency rather than meaning.

---

## C. Summarize older conversation

Conceptually:

```text
old messages
    ↓
summary

recent messages stay verbatim
```

Then model context becomes:

```text
system instructions
conversation summary
recent messages
relevant long-term memories
current evidence
```

This is often much more useful than shipping a giant transcript.

---

# 5. Summary is lossy compression

A summary is not the original history.

If the original conversation says:

```text
User prefers Python for examples,
except when interviewing for a C++ role.
```

A poor summary might become:

```text
User prefers Python.
```

The exception disappeared.

Therefore summaries should be treated as derived state with provenance, not as infallible truth.

---

# 6. Short-term memory should not silently become long-term memory

A statement appearing in a thread does not automatically deserve cross-session retention.

Example:

```text
User: Today I am staying in Osaka.
```

That could be useful for the current thread.

It does not mean:

```text
Long-term memory:
"User permanently lives in Osaka."
```

This is precisely why Stage 06 separates:

```text
thread state
        from
long-term memory writes
```

---

# 7. State cleanup is part of memory design

Long-running threads accumulate:

- messages;
- tool results;
- retrieved documents;
- intermediate plans;
- temporary artifacts.

Not all of them should live forever.

Think in lifecycle categories:

```text
ephemeral
  -> needed for one node/step

thread-lived
  -> needed while this conversation continues

cross-thread durable
  -> selected long-term memory

external archival
  -> logs/audit/history systems
```

This classification prevents "just put it all in state" architecture.

---

# 8. Thread deletion and retention

Production systems need a policy for:

```text
How long does a thread live?
Who can delete it?
Can a user request deletion?
What happens to old checkpoints?
Do backups obey the same retention policy?
```

Persistence without retention policy eventually becomes accidental archival.

And accidental archival is an expensive way to discover privacy law.

---

# 9. Stage 06 example

See:

```text
code/thread_short_term_memory.py
```

It uses one `InMemorySaver` and two thread IDs:

```text
thread-a
  -> interaction 1
  -> interaction 2
  -> accumulated state

thread-b
  -> empty independent state
```

The lesson is scope, not `InMemorySaver` itself.

`InMemorySaver` disappears when the process exits.

Durability comes in the next chapter.

---

# 10. Practical prompt assembly

A production-style context builder might conceptually do:

```python
def build_context(state, memories, evidence):
    return [
        system_message(),
        conversation_summary(state),
        *recent_messages(state),
        memory_message(memories),
        evidence_message(evidence),
    ]
```

Notice what is missing:

```text
serialize_the_entire_database()
```

The model should receive the minimum useful context, not every byte your application owns.

---

## Completion check

You should be able to explain:

1. Why checkpointer persistence and model context are different concerns.
2. Why `thread_id` defines short-term memory scope.
3. Why huge history can hurt even if it technically fits.
4. Recency trimming vs token trimming vs summarization.
5. Why summaries are lossy derived state.
6. Why a thread fact should not automatically become long-term memory.
7. Why retention/deletion belongs in memory architecture.

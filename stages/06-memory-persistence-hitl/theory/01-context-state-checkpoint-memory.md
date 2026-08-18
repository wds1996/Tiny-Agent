# Context, State, Checkpoint, and Memory

The word **memory** is dangerously overloaded in Agent tutorials.

People often point at anything that survives for more than one line of Python and call it memory:

```text
chat history?       memory!
LangGraph state?    memory!
Redis?              memory!
vector database?    memory!
checkpoint?         memory!
```

That is convenient for marketing and terrible for architecture.

Stage 06 begins by separating the concepts.

---

# 1. The five boxes

Use this mental model:

```text
LLM context
    = what the model can see in this call

runtime state
    = what the application needs to continue execution

checkpoint
    = a persisted snapshot/version of runtime state

short-term memory
    = thread-scoped state retained across interactions

long-term memory
    = selected information intentionally available across threads/sessions
```

A sixth concept sits next to them:

```text
external knowledge / RAG corpus
    = documents or evidence the system retrieves
```

RAG knowledge and Agent memory can use similar storage technology, but they have different semantics.

---

# 2. Context is what the model sees now

Suppose the runtime owns:

```python
state = {
    "messages": [...],
    "customer_id": "cust-17",
    "approval_status": "pending",
    "internal_retry_count": 2,
}
```

The LLM does **not** need to see every key.

You might construct a model context containing only:

```python
model_messages = [
    {"role": "system", "content": "You are a support Agent."},
    *relevant_messages,
    {"role": "system", "content": "Approval is pending."},
]
```

So:

```text
state != context
```

State is application data.

Context is the selected representation exposed to the model.

This distinction becomes critical for secrets, internal counters, authorization data, and large histories.

---

# 3. State is the Agent's working notebook

State contains data required by later execution steps.

Examples:

- current plan;
- tool observations;
- retrieved evidence;
- approval request;
- selected route;
- draft output;
- retry metadata;
- conversation messages.

A useful rule from Stage 03 still applies:

> Store raw facts/state when possible; format prompts when needed.

Poor state:

```python
{
    "giant_prompt": "SYSTEM: ... USER: ... EVIDENCE: ..."
}
```

Better state:

```python
{
    "messages": [...],
    "evidence": [...],
    "approval": {...},
}
```

Prompt formatting is then a view over state rather than the state itself.

---

# 4. A checkpoint is a recovery artifact

A checkpoint answers:

> If execution disappears right now, what do I need to continue this thread?

Conceptually:

```text
thread-42
  |
  +-- checkpoint A
  +-- checkpoint B
  +-- checkpoint C
```

It is not merely a transcript.

It may include:

```text
messages
current state values
next graph tasks
checkpoint metadata
pending writes
execution position
```

That is why checkpointing is an orchestration concern.

---

# 5. Short-term memory is thread-scoped

Current LangGraph terminology describes short-term memory as thread-level state persisted through a checkpointer.

Conceptually:

```text
user-7
  |
  +-- thread-A
  |     +-- conversation state
  |
  +-- thread-B
        +-- independent conversation state
```

The same person can have many threads.

Therefore:

```text
thread_id != user_id
```

This mistake causes surprisingly many bugs.

If you use `user_id` as every thread ID, all of a user's unrelated conversations can collapse into one execution history.

---

# 6. Long-term memory crosses thread boundaries

Long-term memory answers a different question:

> What selected information should still be available in a future conversation?

Example:

```text
thread-A:
User: Please remember that I prefer concise Chinese explanations.

        ↓ write approved memory

namespace = ("user-7", "memories")
key       = "explanation-style"
value     = {...}

        ↓ later

thread-B:
Agent retrieves that preference
```

The memory is scoped to the user/application namespace, not to thread-A.

---

# 7. Memory is not 'save the whole chat forever'

A beginner implementation often does this:

```python
memory = every_message_ever
```

That is not a memory strategy.

That is a storage bill with nostalgia.

Long-term memory should normally be **selected**.

For example:

```text
conversation:
"I had ramen for lunch."
```

Maybe irrelevant tomorrow.

But:

```text
"Please remember that I am allergic to peanuts."
```

might be highly important—while also being sensitive health-related information that needs stronger policy.

The hard problem is not only storage.

It is:

```text
what to write
what not to write
who owns it
how to retrieve it
when to update it
when to delete it
```

---

# 8. RAG knowledge is not automatically long-term memory

Stage 04 gave us external evidence:

```text
Company handbook
API documentation
research papers
```

These are knowledge sources.

Long-term memory is more likely to contain:

```text
user preferences
past task outcomes
learned examples
application-specific facts
selected instructions
```

A vector database can technically store both.

That does not mean you should mix them into one namespace with no semantics.

A database is infrastructure.

Memory/knowledge is application meaning.

---

# 9. A practical decision table

| Information | Best first home |
|---|---|
| current tool call | runtime state |
| current conversation history | short-term/thread state |
| execution recovery position | checkpoint |
| user preference across chats | long-term memory |
| company policy document | RAG / knowledge base |
| API key | secret manager, not Agent memory |
| authorization decision | application policy/state |
| debug trace | observability system |

The last rows matter.

Not every persistent fact belongs in "Agent memory."

---

# 10. Tiny-Agent's Stage 06 rule

We will use this pipeline:

```text
information appears
       ↓
MemoryCandidate
       ↓
MemoryWritePolicy
       ↓
   allow / deny
       ↓
Store (if allowed)
```

The model may **propose** a memory.

The application owns the durable write boundary.

This is the same design principle we used for tools, routes, plans, and MCP capabilities.

---

## Completion check

You should be able to explain:

1. State vs LLM context.
2. Checkpoint vs chat transcript.
3. Short-term memory vs long-term memory.
4. `thread_id` vs `user_id`.
5. Long-term memory vs RAG knowledge.
6. Why a database technology does not define the semantic type of stored data.
7. Why "store every message forever" is not a memory policy.

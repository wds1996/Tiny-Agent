# Durable Persistence, Resume, and Recovery

Stage 03 taught the first persistence idea with `InMemorySaver`:

```text
pause
  -> checkpoint in process memory
  -> resume
```

Stage 06 asks a harder question:

> What if the process disappears between pause and resume?

If the answer is "then the approval workflow forgets everything," you built a dramatic pause button, not durable execution.

---

# 1. Persistence is a runtime property, not Agent memory

Keep the distinction:

```text
checkpointer
    -> persists thread execution state

Store
    -> persists selected cross-thread memory/data
```

They can both use PostgreSQL.

They still do different jobs.

```text
same database technology != same application semantics
```

---

# 2. What does a durable checkpoint buy us?

A durable checkpointer can support:

- resume after human review hours later;
- recover after process restart;
- inspect thread history;
- fault recovery;
- time-travel/replay workflows;
- horizontal service deployments where a later request hits another worker.

The core lifecycle becomes:

```text
runtime A
   ↓
execute step
   ↓
write checkpoint
   ↓
process dies / deployment happens / user goes home

... time passes ...

runtime B
   ↓
load same thread_id
   ↓
recover checkpoint
   ↓
continue
```

That is qualitatively different from an in-memory Python dictionary.

---

# 3. InMemorySaver vs SQLite vs Postgres

## InMemorySaver

```text
scope: one Python process
best for: unit tests, tutorials, local exploration
survives process restart: no
```

It is excellent for learning semantics.

It is terrible as a disaster-recovery plan.

## SQLiteSaver

```text
scope: local database file
best for: local apps, experimentation, lightweight durable workflows
survives process restart: yes
shared multi-worker production backend: usually not the first choice
```

SQLite is especially useful pedagogically because you can literally close one saver object, open another one, and prove the state lived in the file.

## PostgresSaver

```text
scope: shared database service
best for: production-oriented durable workflows
survives process restart: yes
shared across workers: yes
```

Production suitability still depends on your actual deployment, HA, backups, connection pooling, migrations, retention, and operational design.

A class named `PostgresSaver` does not automatically configure your SRE organization.

---

# 4. SQLite restart example

See:

```text
code/sqlite_durable_checkpoint.py
```

The essential pattern is:

```python
with SqliteSaver.from_conn_string(path) as first_saver:
    graph = build_graph(first_saver)
    graph.invoke({"count": 0}, config=config)

# first graph/saver objects are gone

with SqliteSaver.from_conn_string(path) as second_saver:
    graph = build_graph(second_saver)
    recovered = graph.get_state(config)
```

The checkpoint belongs to durable storage, not the original graph object.

---

# 5. Postgres setup is schema initialization

Current LangGraph Postgres persistence packages require `setup()` on first use:

```python
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()
```

Similarly for the Postgres Store:

```python
with PostgresStore.from_conn_string(DB_URI) as store:
    store.setup()
```

In a tutorial this is convenient.

In production, schema creation/migration should normally be part of deployment operations rather than a surprise side effect in every request handler.

A web request that says "hello" should not secretly discover it has been promoted to database administrator.

---

# 6. Thread identity becomes infrastructure

Once checkpoints are durable, `thread_id` is not a throwaway demo string.

It affects:

- recovery;
- user routing;
- privacy boundaries;
- deletion;
- retention;
- support/debug tooling;
- idempotency and duplicate requests.

A good thread identifier should be:

- stable for the logical execution;
- unique enough to avoid collisions;
- not trusted as authorization on its own.

Knowing a thread ID should not grant access to its state.

---

# 7. Recovery is not the same as retry

Suppose an Agent calls:

```text
charge_credit_card()
```

and then the process crashes before the next checkpoint is committed.

On recovery, the runtime might reach that operation again.

Therefore durable systems need to reason about:

```text
at-most-once?
at-least-once?
exactly-once illusion?
idempotency key?
external transaction status?
```

Persistence lets you recover state.

It does **not** magically make external side effects transactional with your checkpoint database.

---

# 8. Idempotency keys

For externally visible operations, a common pattern is:

```python
idempotency_key = f"{thread_id}:{operation_id}"

payment_api.charge(
    amount=100,
    idempotency_key=idempotency_key,
)
```

If the operation is retried, the external system can recognize the duplicate logical request.

Other strategies:

- query external status before repeating;
- use an outbox/transactional messaging pattern;
- separate prepare and commit steps;
- make the operation naturally idempotent when possible.

Stage 09 will go deeper into reliability controls.

---

# 9. Checkpoint history and time travel

Because checkpoints form execution history, a runtime can inspect earlier states.

This is useful for:

- debugging why a route was chosen;
- comparing before/after state;
- replaying from an earlier point;
- reproducing a failure.

But time travel is not a time machine for the external world.

If checkpoint 4 says:

```text
email_sent = False
```

and you replay from there after an email was actually sent in reality, the inbox does not politely unsend itself.

State replay and external side-effect replay must be designed separately.

---

# 10. Serialization is part of the persistence boundary

Checkpoint state must cross a serialization boundary.

That encourages state values such as:

```text
strings
numbers
booleans
lists
dictionaries
well-supported framework primitives
```

and discourages casually persisting arbitrary live objects:

```text
open socket
DB cursor
thread lock
mystery vendor client
```

If an object cannot be meaningfully reconstructed, it probably does not belong in durable execution state.

---

# 11. Deserialization is a security boundary

Persistence backends do not only write data; they later deserialize it.

That means compromise of checkpoint storage can become more dangerous if permissive serializers can instantiate arbitrary objects.

Tiny-Agent's Stage 06 CI sets:

```bash
LANGGRAPH_STRICT_MSGPACK=true
```

for its Postgres persistence tests.

The broader lesson is framework-independent:

> Treat persisted workflow state as data crossing a trust boundary, not as harmless bytes.

Avoid pickle-style fallbacks unless you understand and accept the trust model.

---

# 12. Retention and cleanup

A checkpointer can accumulate many checkpoint versions per thread.

Production questions include:

```text
How long should completed threads remain?
How many checkpoint versions should be kept?
Do users have deletion rights?
How do backups age out?
What does legal hold mean?
What gets archived for audit vs deleted for privacy?
```

"We have a database" is not a retention strategy.

---

# 13. Checkpoint migrations

Your state schema will evolve.

Today:

```python
{"status": "pending"}
```

Next month:

```python
{
    "status": "pending_review",
    "approval_policy_version": 2,
}
```

Durable old checkpoints may still contain the old shape.

Therefore mature systems consider:

- backward-compatible state readers;
- schema/version fields;
- migration strategy;
- code deployments that can resume older threads.

Durability means your old data gets a vote in future software design.

---

# 14. Durable HITL is the main Stage 06 demonstration

See:

```text
code/durable_hitl_resume.py
```

The flow is deliberately stronger than Stage 03:

```text
runtime A
  -> prepare risky action
  -> interrupt
  -> checkpoint in SQLite
  -> close runtime A completely

runtime B
  -> recreate graph + saver
  -> same thread_id
  -> Command(resume=...)
  -> continue
```

The human does not need to click approve before your next deploy.

That is the operational meaning of durable interruption.

---

## Completion check

You should be able to explain:

1. Checkpointer vs Store even when both use PostgreSQL.
2. InMemorySaver vs SQLiteSaver vs PostgresSaver.
3. Why durable persistence enables restart recovery.
4. Why recovery does not guarantee exactly-once side effects.
5. Why idempotency matters.
6. Checkpoint replay vs replaying the external world.
7. Why serialization/deserialization is a security boundary.
8. Why retention and schema migration belong in persistence design.
9. What makes HITL truly durable rather than process-local.

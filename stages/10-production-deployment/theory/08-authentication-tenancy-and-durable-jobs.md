# 08 — Authentication, Multi-Tenancy, Durable Jobs, and Leases

Two production gaps remain surprisingly common after an Agent gets an HTTP endpoint:

1. identity is trusted from request body fields;
2. long-running work still depends on one web worker staying alive.

Both are demo conveniences, not durable production contracts.

---

## 1. Authentication vs authorization

```text
authentication
    = who/what made this request?

authorization
    = may that principal perform this action on this resource?
```

Tiny-Agent's service path:

```text
credential
-> trusted authenticator
-> AuthenticatedIdentity(subject, tenant, roles)
-> normalized service/domain request
-> resource/Tool authorization
```

The request body does not get to rewrite authenticated identity.

---

## 2. Reject identity smuggling

`bind_trusted_identity()` reserves server-owned fields:

```python
_RESERVED_IDENTITY_KEYS = {
    "subject_id",
    "tenant_id",
    "roles",
    "user_id",
}
```

Conceptual use:

```python
metadata = bind_trusted_identity(
    {"thread_id": body.thread_id},
    authenticated_identity,
)
```

If client metadata tries to supply `tenant_id`, Tiny-Agent raises `IdentityBindingError`.

This is easier to reason about than "body tenant_id is okay unless it looks suspicious."

---

## 3. Tenant scope belongs in resource identity

Two tenants can both contain:

```text
user-17
thread-1
run-42
```

Therefore resource ownership often includes:

```text
subject_id
tenant_id
workspace/project scope when relevant
```

Tiny-Agent's `require_owner()` checks subject **and** tenant.

This avoids cross-tenant namespace collisions where identical user IDs become accidental roommates.

---

## 4. Long work needs durable ownership

A long Agent may outlive:

- client connection;
- proxy timeout;
- deployment;
- web worker;
- sandbox/container.

Therefore:

```text
POST /runs
-> durable job record
-> return run_id

worker claims run
-> executes
-> persists terminal result
```

The web process is an admission/API layer, not the storage medium for the promise.

---

## 5. Lease state machine

Tiny-Agent's local `SQLiteRunQueue` demonstrates:

```text
queued
  -> running(worker_id, lease_expiry)
      -> completed
      -> failed

running + expired lease
  -> claimable by another worker
```

A lease means:

> This worker owns execution until time T unless it renews/finishes according to the system contract.

It is not eternal ownership.

---

## 6. Atomic claim

`SQLiteRunQueue.claim()` uses a transaction:

```text
BEGIN IMMEDIATE
SELECT one queued/expired run
UPDATE -> running + owner + expiry
COMMIT
```

This teaching implementation prevents two local workers from intentionally claiming the same queued row at once.

Production databases/queues provide their own atomic-claim primitives/locking patterns. Preserve the semantics even if implementation changes.

---

## 7. Stale workers must not complete new ownership

Scenario:

```text
worker A claims run
A stalls
lease expires
worker B claims run
A wakes up and tries to complete
```

Tiny-Agent terminal update includes:

```text
WHERE run_id=?
  AND status='running'
  AND lease_owner=?
```

If A no longer owns the lease, completion fails.

This prevents a zombie worker from overwriting B's ownership merely because it remembers the run ID.

---

## 8. Exactly-once warning

Leases provide ownership coordination, not exactly-once side effects.

```text
worker A sends email
-> crashes before marking job complete
-> lease expires
-> worker B retries
-> email may be sent twice
```

Use operation-specific protection:

```text
idempotency key
transaction/outbox
external API idempotency support
deduplication record
human approval for risky repeat
```

A durable queue cannot travel back in time to discover whether the outside world received the side effect.

---

## 9. Run queue vs checkpoint vs TaskLedger

Do not collapse these layers:

```text
Run queue
    = which service worker owns the logical job?

Agent checkpoint
    = where can orchestration resume?

TaskLedger
    = what sub-work/progress remains inside a long-horizon run?
```

One production Agent may use all three:

```text
run-42 claimed by worker B
thread checkpoint at graph node "review"
TaskLedger: 7/10 research subtasks complete
```

They answer different questions.

---

## 10. Cancellation has layers too

A user cancels run-42.

Potential work:

```text
mark durable run cancellation requested
-> worker observes and stops new sub-work
-> cancel downstream MCP task if supported
-> terminate/stop sandbox safely
-> preserve useful artifacts
-> update checkpoint/ledger
-> publish cancelled terminal status
```

A closed browser tab is not a durable cancellation protocol.

---

## 11. Worked tenant-safe resume

```text
request: GET /runs/run-42
credential -> tenant-B/user-17
DB record  -> tenant-A/user-17 owns run-42
```

Even though subject IDs match:

```text
require_owner -> deny
```

Correctly.

Now same tenant/subject resumes:

```text
load durable run
-> claim/lease worker
-> load thread checkpoint
-> recover TaskLedger if needed
-> continue
```

---

## 12. Completion checklist

You should be able to explain:

- authentication vs authorization;
- why body identity is untrusted;
- tenant-scoped ownership;
- durable run state vs web connection;
- lease claim/reclaim/stale-worker behavior;
- exactly-once limitation;
- run queue vs checkpoint vs TaskLedger;
- cancellation across downstream layers.

The invariant:

> **Identity comes from a trusted server-side authentication boundary; durable jobs externalize ownership and progress; leases coordinate workers but do not make side effects exactly once.**

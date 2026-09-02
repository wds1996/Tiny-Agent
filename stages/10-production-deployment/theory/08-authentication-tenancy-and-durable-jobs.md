# 08 — Authentication, tenancy, and durable jobs

Two production gaps commonly remain after an Agent gets an HTTP endpoint:

1. the service trusts identity supplied by the request body;
2. long work is still tied to one web-process lifetime.

Neither is acceptable as a production contract.

## Authentication vs authorization

Authentication answers:

> Who/what made this request?

Authorization answers:

> May that principal perform this action on this resource?

Tiny-Agent Stage 07 already has `Principal` and Tool permission policy. Stage 10 adds service-boundary identity binding.

```text
request
-> trusted auth layer validates credential
-> AuthenticatedIdentity(subject, roles, tenant)
-> domain/service request
-> resource/tool authorization
```

The request body does not get to replace the authenticated subject or tenant.

## Multi-tenant ownership

Knowing a `thread_id`, `run_id`, or document ID is not proof of ownership.

Persisted resources should carry owner scope:

```text
subject_id
tenant_id
workspace/project when relevant
```

Every read/resume/update must compare the authenticated identity with resource ownership or a broader authorized role/policy.

## Why HTTP connections are poor durable task stores

A long Agent may outlive:

- client connection;
- reverse-proxy timeout;
- deploy rollout;
- web worker;
- sandbox/container.

Therefore durable work should externalize its lifecycle.

## Queue state machine

Tiny-Agent's local example:

```text
queued
  -> running(lease owner + expiry)
      -> completed
      -> failed

running + expired lease
  -> claimable by another worker
```

A lease prevents two healthy workers from intentionally owning the same run at once while allowing recovery after worker death.

## Exactly-once warning

A durable queue does not magically create exactly-once side effects.

A worker can:

```text
send external payment/email/write
-> crash before marking completed
-> lease expires
-> another worker retries
```

External side effects still need idempotency keys, transactions, or downstream deduplication appropriate to the operation.

## Durable job vs Agent checkpoint

Do not collapse these:

```text
Run queue
    = which service worker owns the logical job?

Agent checkpoint
    = where inside the Agent state machine can execution resume?

Task ledger
    = what sub-work remains inside a long-horizon run?
```

One production Agent may use all three.

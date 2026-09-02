# 04 — Credentials, network, snapshots, and recovery

An Agent sandbox becomes much more dangerous when it simultaneously has:

```text
untrusted instructions
+ broad filesystem reads
+ powerful credentials
+ unrestricted network egress
```

Break that chain deliberately.

## Credentials stay with the harness where possible

Prefer mediated capabilities:

```text
sandbox asks harness: search repository X
harness checks policy/identity
harness performs scoped API call
returns bounded result
```

instead of injecting a cloud-admin token into the sandbox environment.

## Egress is an authorization boundary

A firewall/proxy can enforce destination allowlists, request size limits, logging, or protocol restrictions. Prompt instructions cannot.

## Disposable compute, durable state

A useful long-horizon design is:

```text
durable run/checkpoint/task ledger
+ durable artifact/workspace snapshot
+ disposable sandbox
```

If the sandbox expires:

1. provision another;
2. restore allowed workspace state;
3. resume from durable harness state;
4. revalidate pending side effects.

## Snapshot trust

Do not blindly promote every sandbox byte into a trusted future context. Snapshots can contain malicious dependencies, poisoned notes, secrets, or corrupted state.

Treat restoration/promotion as a governed boundary with provenance and retention rules.

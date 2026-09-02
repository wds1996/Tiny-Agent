# 01 — Harness, workspace, compute, and sandbox

Several words get collapsed into “the Agent environment.” Keep them separate.

## Harness

The harness owns the Agent loop and control plumbing:

```text
model calls
context assembly
tool dispatch
approval
checkpoints
budgets
tracing
resume bookkeeping
```

## Workspace

The workspace is task-owned data:

```text
input files
working files
source tree
notes
artifacts
```

It may survive multiple model calls or even multiple compute instances.

## Compute

Compute is where commands/code actually execute. It can be:

- the host process;
- a child process;
- a container;
- a VM/microVM;
- a managed sandbox provider.

## Sandbox

A security sandbox is a containment goal, not a Python class name. It tries to reduce what untrusted execution can observe, modify, consume, or exfiltrate.

Threat dimensions include:

```text
filesystem
network
processes/syscalls
CPU/memory/PIDs
time
credentials
kernel boundary
cross-tenant isolation
artifact promotion
```

## Why harness and compute should be separable

If the compute environment dies but the durable harness state lives elsewhere:

```text
new sandbox
-> restore workspace/snapshot
-> load task ledger/checkpoint
-> continue
```

If your only copy of run state lives inside the disposable container, container failure becomes task amnesia.

Keeping orchestration credentials outside the environment where model-generated code runs also reduces exfiltration risk.

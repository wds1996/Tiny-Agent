# 01 — Harness, Workspace, Compute, and Sandbox

Modern Agents increasingly do more than call narrow APIs. They inspect repositories, edit files, execute commands, install dependencies, create artifacts, and continue work across many steps.

That introduces several abstractions that sound similar but are not interchangeable:

```text
Agent harness
    = orchestration/control layer around model work

workspace
    = application-owned files/artifacts for a run/project

process
    = one OS execution unit

container / VM
    = stronger compute/isolation boundary

sandbox
    = governed execution environment with an explicit threat model
```

Calling `subprocess.run()` a sandbox does not make it one. Calling a cardboard box a bank vault also has limited effect on the insurance policy.

---

## 1. The harness owns orchestration, not arbitrary code execution

The harness may own:

```text
objective
Tool/Skill exposure
context assembly
budgets
approval state
progress/task ledger
artifact references
tracing/evaluation
```

It decides **what work should happen next**.

Risky/model-generated code should execute behind a separate compute boundary when appropriate.

```text
model proposal
    ↓
harness policy
    ↓
execution request
    ↓
sandbox/compute
    ↓
artifact/result
    ↓
harness evaluates and continues
```

This separation keeps orchestration credentials and durable state away from disposable compute.

---

## 2. Workspace is externalized working memory

A workspace can hold:

```text
source files
notes
intermediate datasets
generated reports
test logs
patches
artifacts
```

These do not need to live inside the model context.

The model reads relevant slices when needed.

```text
workspace: potentially GBs
model context: selected KB/MBs
```

This is context engineering applied to files.

---

## 3. Tiny-Agent `AgentWorkspace`

```python
from tiny_agent import AgentWorkspace

workspace = AgentWorkspace("./work/run-42")
workspace.write_text("notes/plan.md", "# Plan\n1. inspect tests")
print(workspace.read_text("notes/plan.md"))
```

By default `write_text()` uses exclusive creation, so accidentally overwriting an existing artifact fails unless `overwrite=True` is explicit.

That is a small but useful safety property: silent destructive writes are rarely educational.

---

## 4. Why ordinary subprocess is not a security sandbox

```python
subprocess.run(["python", "generated.py"])
```

A child process normally inherits substantial host authority:

- same kernel;
- caller's filesystem permissions;
- environment variables unless removed;
- network access;
- ability to spawn processes;
- access to reachable local services.

A timeout controls duration. It does not suddenly revoke filesystem/network authority.

```text
timeout != isolation
```

---

## 5. Containers add useful isolation controls

A container can reduce privilege through namespaces/cgroups and runtime restrictions.

Tiny-Agent's Docker baseline uses:

```text
read-only root filesystem
network disabled by default
all Linux capabilities dropped
no-new-privileges
PID limit
memory limit
CPU limit
non-root user
bounded writable workspace mount
tmpfs /tmp
```

That is materially safer than executing arbitrary model-generated code directly in the web/Agent process.

It is still a baseline, not a proof that ordinary Docker is sufficient for hostile multi-tenant workloads.

---

## 6. Harness state should survive compute loss

Imagine:

```text
Agent task ledger
    ↓
container analyzes dataset
    ↓
container dies
```

If the task ledger existed only inside the container, the orchestration state died too.

Better:

```text
durable harness/workspace metadata
        ↓
disposable compute instance
        ↓
artifacts copied/written to governed workspace
```

Stage 14 builds long-horizon recovery on this separation.

---

## 7. Worked example: coding Agent

Task:

```text
"Fix the failing unit test."
```

A useful architecture:

```text
1. harness selects coding/review Skill
2. workspace contains repository snapshot
3. model reads failing test + relevant source
4. model proposes patch
5. patch applied inside governed workspace
6. sandbox runs pytest with no network
7. result returned to harness
8. evaluator checks tests + diff constraints
9. harness accepts, repairs, or requests review
```

The model does not need host SSH keys or production database credentials to fix a local unit test.

Least privilege often starts with asking the embarrassingly simple question:

> Why can this test process see the internet at all?

---

## 8. When a narrow Tool is better than a shell

Do not hand every Agent a general-purpose computer.

If the only required action is:

```text
get_invoice(invoice_id)
```

then a typed API Tool is easier to validate, authorize, observe, and evaluate than:

```text
shell + database credentials + curl + hope
```

Use sandboxed computer environments when the task truly requires open-ended filesystem/process interaction.

---

## 9. Threat-model ladder

Possible execution boundaries, roughly increasing isolation/operational cost:

```text
same Python process
child process
container
hardened container runtime (e.g. gVisor/Kata-style boundary)
microVM / VM
separate worker/host/account/project
```

There is no universal "best sandbox." Choose based on:

- code trust;
- tenant isolation needs;
- secrets/data sensitivity;
- network requirements;
- performance/startup constraints;
- operational maturity.

---

## Completion principle

> **The harness is durable control; the workspace is governed working state; compute is where risky execution happens; sandboxing is a threat-model decision, not a synonym for `subprocess`.**

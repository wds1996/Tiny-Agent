# Stage 12 — Sandboxed Agent Workspaces & Computer Environments

Many modern Agents no longer work only through narrow API Tools. They inspect files, run commands, edit code, create artifacts, install dependencies, and maintain a working directory across many steps.

That changes the architecture:

```text
Agent harness
    |
    | proposals / tool requests
    v
execution policy
    |
    v
sandbox / compute environment
    |
    +--> filesystem
    +--> shell/processes
    +--> packages
    +--> artifacts
```

The central lesson is:

> A workspace is application state. A subprocess is a process boundary. A container is a stronger isolation boundary. None of those names should be casually upgraded to “perfect sandbox.”

## Why this stage appears after Safety and Multi-Agent

Before giving a model a computer-like environment you should already understand:

- least privilege;
- approval vs authorization;
- timeouts and retry safety;
- prompt injection;
- multi-Agent context/authority boundaries.

Otherwise “give the Agent shell access” is not an architecture; it is a blast-radius experiment.

## Learning objectives

After this stage you should be able to:

1. distinguish harness, workspace, process, container, VM, and sandbox;
2. confine Agent file reads/writes to an application-owned root;
3. make durable artifacts explicit instead of hiding them in model context;
4. explain why `subprocess` is not a security sandbox;
5. run a command without `shell=True` and without string interpolation;
6. apply network, capability, PID, CPU, memory, user, and filesystem restrictions to a container baseline;
7. keep application credentials outside model-generated execution environments;
8. explain egress policy and data-exfiltration risk;
9. separate disposable compute from durable harness/run state;
10. evaluate/snapshot workspace outputs before promoting them.

## Learning order

1. `theory/01-harness-workspace-compute-and-sandbox.md`
2. `theory/02-files-artifacts-and-workspace-policy.md`
3. `code/workspace_demo.py`
4. `theory/03-container-isolation-and-threat-model.md`
5. `code/docker_sandbox_demo.py`
6. `theory/04-credentials-network-snapshots-and-recovery.md`
7. `src/tiny_agent/workspace.py`
8. `tests/test_workspace.py`
9. `exercises/review-questions.md`

## Current industry direction

OpenAI's April 2026 Agents SDK update explicitly separates a model-native harness from controlled sandbox compute and adds filesystem/shell-oriented workspaces for long-horizon tasks. The broader lesson is provider-independent: capable Agents need an execution environment, but orchestration credentials/policy should remain outside that environment.

Reference: https://openai.com/index/the-next-evolution-of-the-agents-sdk/

## Tiny-Agent baseline

`AgentWorkspace` confines filesystem paths using resolved-root checks.

`DockerSandboxRunner` builds a default-deny-ish container command with:

```text
network none
read-only root filesystem
writable mounted workspace
cap-drop ALL
no-new-privileges
PID limit
memory limit
CPU limit
non-root user
tmpfs /tmp
no shell interpolation
```

That is materially safer than executing arbitrary model text in the host process. It is still not a claim that ordinary Docker configuration is sufficient for every hostile multi-tenant workload.

## Milestone

You are done when you can explain exactly where model-generated code runs, which files it can touch, which network destinations it can reach, which credentials it can see, what survives container loss, and which deterministic component can still deny execution.

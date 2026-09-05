# Stage 12: Give the Agent a Workbench, Not the Keys to the Whole Computer — Workspace and Sandbox Boundaries

> Language: **English** | [简体中文](README.zh-CN.md)

Stage 11 gave Agents task boundaries. Real work soon needs files, artifacts, tests, and scripts.

That raises a question we deliberately postponed:

> **If an Agent can manipulate files and run programs, how much of the machine can it touch?**

Stage 12 builds a Workspace and a bounded subprocess runner to make the important boundaries visible.

One statement must remain explicit:

> **The standard-library runner in this chapter is not a security sandbox.**

It teaches the pieces a real sandbox must control.

---

## 1. Why a Workspace exists

Longer Agent tasks produce input files, scratch files, generated code, test output, and final artifacts.

If everything lands in the service process's current directory, ownership and cleanup become ambiguous.

A Workspace turns one run's files into an explicit boundary.

---

## 2. Start with one root per run

The teaching layout looks like:

```text
run-001/
├── input.txt
├── work/
│   └── check.py
└── artifacts/
    └── result.txt
```

A production Workspace may map to remote storage or a managed sandbox. The abstraction still matters: the Agent works inside its Workspace, not against arbitrary host paths.

---

## 3. Path traversal is a small string with sharp teeth

Allowing `../../secret.txt` would make the Workspace root meaningless.

The implementation resolves the canonical target and verifies that it stays under the root. Absolute paths are rejected as well.

---

## 4. Symlinks are why string checks are not enough

Blocking the literal substring `..` does not stop a symlink inside the Workspace from pointing elsewhere.

Resolve the real path first, then enforce containment. Filesystem policy should reason about canonical targets.

---

## 5. Work files and Artifacts serve different purposes

Scratch code, downloaded data, and debug output are not necessarily user-facing deliverables.

Separating `work/` and `artifacts/` makes lifecycle and export policy clearer. Stage 14 will build on this idea when work survives individual compute sessions.

---

## 6. Only now do we add a Command Runner

The runner accepts an argument list:

```python
runner.run(
    [python, "work/check.py"],
    timeout_seconds=2,
)
```

and uses `shell=False`.

Removing a shell parsing layer reduces one class of injection. It does not make arbitrary commands safe by itself.

---

## 7. Executable allowlists bound the capability surface

The runner is constructed with an executable allowlist.

A program being installed on the machine does not mean the Agent is allowed to run it. This is the Stage 09 permission idea applied to compute capabilities.

Allowing Python is still powerful, so this remains only one layer.

---

## 8. Working directory should be explicit

The subprocess always starts with:

```python
cwd=workspace.root
```

Relative paths become deterministic and naturally map to the current run.

---

## 9. Do not inherit every environment variable by default

The parent service may contain database URLs, API keys, cloud credentials, and tokens.

Passing the entire environment to generated code silently expands its authority.

The teaching runner starts from a small environment and adds only explicitly provided values.

Credentials should be capabilities, not ambient decoration.

---

## 10. Process timeout is stronger than thread timeout, but not perfect isolation

`subprocess.run(..., timeout=...)` can terminate the direct child after timeout.

That is a clearer boundary than simply stopping a wait on a worker thread.

Complex process trees and external side effects still require stronger lifecycle management.

---

## 11. Output needs a budget too

A subprocess can print megabytes.

Feeding all of stdout back into model context creates another unbounded data path.

The runner truncates output after `max_output_chars`.

Anything that enters context, logs, or persistence deserves a limit.

---

## 12. This is not a security sandbox

The wrapper controls paths it exposes, executable names, CWD, environment, timeout, and output.

But allowed Python code can still use the operating system capabilities available to the process.

A stronger sandbox may require separate users, namespaces, containers or VMs, mount policy, network controls, syscall restrictions, resource limits, and credential isolation.

Do not call a subprocess wrapper a sandbox merely because it has a timeout.

---

## 13. Containers are tools, not automatic security proofs

Containers can provide useful filesystem, process, resource, and network boundaries.

Their effective isolation depends on configuration, mounts, Linux capabilities, runtime, and credentials.

“Runs in a container” is not enough information to evaluate the security boundary.

---

## 14. Network access should be explicit policy

Some tasks need the network. Many do not.

A real sandbox can disable networking or restrict destinations.

The standard-library runner cannot reliably enforce OS-level network isolation, so this chapter does not invent a fake `network=False` flag.

Unimplemented isolation should not be represented as a decorative option.

---

## 15. Skill scripts finally have an execution location

Stage 08 deliberately refused to run arbitrary Skill scripts.

Now the chain can be explicit:

```text
Skill procedure
    ↓
Host policy
    ↓
Workspace
    ↓
Runner / Sandbox
    ↓
Artifact
```

The Skill still does not own execution authority.

---

## 16. Workspace is not durable state

A Workspace may disappear with compute.

A checkpoint should survive compute loss.

Artifacts worth retaining should be exported to durable storage.

These semantics can share infrastructure, but they should remain distinct.

---

## 17. Cleanup is part of the lifecycle

A complete Workspace lifecycle is:

```text
create
use
export artifacts
cleanup
```

Temporary downloads, caches, generated code, and logs otherwise accumulate until disk space becomes the monitoring system.

---

## 18. Run the chapter

```bash
python stages/12-agent-workspace-sandbox/code/demo.py
python stages/12-agent-workspace-sandbox/code/checks.py
```

The checks cover path confinement, absolute paths, executable allowlists, CWD, timeout, output truncation, and environment minimization.

---

## 19. Why production service design comes next

The Agent now has durable state, external capabilities, memory, guardrails, evaluation, team coordination, and a workspace.

Deployment introduces ordinary but unavoidable systems questions: concurrent users, request/run/thread/tenant identity, long jobs, backpressure, restarts, readiness, and durable status.

Stage 13 turns the Agent program into a service.

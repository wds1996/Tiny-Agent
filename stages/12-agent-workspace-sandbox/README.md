# Stage 12: Give the Agent a Workbench, Not the Keys to the Whole Computer — Workspace and Sandbox Boundaries

> Language: **English** | [简体中文](README.zh-CN.md)

Stage 11 assigned responsibility across Agents. The next practical question is where an Agent may create files and execute its work. A task that writes reports, downloads inputs, runs tests, or generates scripts needs a place to work, but it must not quietly inherit the whole host computer.

This chapter builds a small per-run Workspace and a bounded command runner. It also draws the line that matters for production work:

> **The standard-library runner in this chapter is not a security sandbox.**

It makes several useful limits explicit; an OS-level or virtualized sandbox must enforce the stronger limits that remain.

---

## 1. From “who does the task” to “where does the task run?”

Stage 11 gave a coordinator and workers separate responsibilities. A worker often needs files: user input, scratch code, downloaded material, test output, and a final report. Leaving all of these in the service process's current directory makes ownership, cleanup, and export ambiguous.

A **Workspace** is a directory allocated to one run. It gives the run a visible file boundary:

```text
run-001/
├── input.txt
├── work/
│   └── check.py
└── artifacts/
    └── result.txt
```

The teaching implementation creates that directory and provides paths through `AgentWorkspace`:

```python
from pathlib import Path
import tempfile

from workspace import AgentWorkspace

with tempfile.TemporaryDirectory() as tmp:
    workspace = AgentWorkspace.create(Path(tmp) / "run-001")
    workspace.write_text("input.txt", "draft release notes")
    workspace.write_text("work/check.py", "print('checked')\n")
    workspace.write_text("artifacts/result.txt", "approved summary\n")

    print(workspace.list_files())
```

The current run may write inside this root. `TemporaryDirectory` removes this teaching Workspace when its block ends. An application can later export a selected item from `artifacts/`; it should not treat every temporary file as a deliverable.

## 2. A file boundary must handle real paths, not only strings

An API that accepts a relative path must reject path traversal:

```text
../../secret.txt
```

It must also reject absolute paths. The key detail is that the implementation calls `resolve()` first, then verifies the canonical target remains under the Workspace root:

```python
def resolve(self, relative_path: str | Path) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise WorkspaceEscapeError("absolute paths are not allowed")

    target = (self.root / candidate).resolve()
    try:
        target.relative_to(self.root)
    except ValueError as exc:
        raise WorkspaceEscapeError("path escapes workspace") from exc
    return target
```

Why not simply reject a string containing `..`? A **symbolic link (symlink)** can make an ordinary-looking path point outside the Workspace:

```text
workspace/outside-link  ->  /somewhere/private.txt
```

`outside-link` contains no `..`, but its real target is external. Checking the resolved path catches this case. The checks test it when the operating system permits symlink creation; on Windows machines without that permission, the test is skipped rather than reporting a false pass.

This local path-confinement helper is useful against ordinary escapes. It is not a complete defense against a malicious process on the same host, which can potentially change filesystem state between the check and the file operation. Untrusted code needs the OS or virtualization isolation discussed later in this chapter.

## 3. Workspace, Artifact, Checkpoint, and Cleanup are four different things

These terms all involve saved data, but they answer different questions:

| Object | What it holds | Typical lifetime |
| --- | --- | --- |
| Workspace | Input, intermediate files, and temporary scripts for this computation | Cleaned up after the run |
| Artifact | A report, patch, or test result worth delivering | Explicitly exported and retained |
| Checkpoint | State needed to continue work | Stage 06 durable store |
| Task ledger | Run status, retries, and audit events | Long-lived service record |

A Workspace can be backed by persistent storage, but the meanings should stay distinct. If a Worker disappears, a Checkpoint tells the system how to resume. An Artifact is the result a user or downstream workflow receives. Temporary work files usually need cleanup.

The lifecycle is therefore:

```text
create workspace
    → write / execute / inspect
    → export selected artifacts
    → cleanup temporary workspace
```

Without that final step, downloaded inputs, caches, generated scripts, and large logs accumulate until disk space reveals the design gap.

---

## 4. When executing a command, return “what may run” to the Host

After controlling file locations, we can ask what programs may run. Do not pass a command string assembled by a model or script straight to a shell:

```python
# Do not do this with untrusted input: the shell parses the whole string again.
import subprocess

untrusted_argument = "work/check.py && echo unexpected-shell-command"
subprocess.run(f"python {untrusted_argument}", shell=True, check=False)
```

With `shell=True`, the shell interprets quotes, redirects, `&&`, and other syntax. Any unvalidated input mixed into that string becomes difficult to reason about. The chapter runner takes an argument list and fixes `shell=False`:

```python
from pathlib import Path
import sys
import tempfile

from runner import CommandRunner
from workspace import AgentWorkspace

with tempfile.TemporaryDirectory() as tmp:
    workspace = AgentWorkspace.create(Path(tmp) / "demo-run")
    workspace.write_text("work/check.py", "print('checked')\n")

    runner = CommandRunner(
        workspace,
        allowed_executables={"python": sys.executable},
    )
    result = runner.run(["python", "work/check.py"], timeout_seconds=2)
    print(result.stdout)
```

Here `"python"` is not an arbitrary program that the model may find through `PATH`. It is a **command alias** registered by the Host when it starts. The runner replaces it with the known `sys.executable` path. A file named `python` inside the Workspace, or a request for `./python`, does not match the alias.

This is a small capability boundary: the Host decides which aliases exist, and the caller can request only those programs. Command arguments cannot quietly replace the executable itself.

The runner also fixes `cwd=workspace.root`. Thus `work/check.py` is relative to this run's working directory, not to the service project's root. Outputs stay grouped with the run and scripts are less likely to read an accidental host-relative path.

## 5. A started command still needs resource limits

Allowing a known interpreter does not mean handing it the whole host environment. The runner starts with just `PATH` and `PYTHONIOENCODING`, then lets the Host add explicitly selected variables through `extra_env`. Database passwords, cloud credentials, and deployment tokens must not be inherited merely because a child process might find them convenient.

Three runtime limits solve three different problems:

| Limit | What this runner does | What it protects against |
| --- | --- | --- |
| Timeout | Terminates the direct child after `timeout_seconds` | A stuck command occupying a Worker forever |
| Output budget | Continuously drains stdout and stderr while retaining only the first `max_output_chars` characters per stream | Huge logs exhausting the parent process's memory |
| Input | Connects stdin to `DEVNULL` | A script waiting for human input and hanging the run |

Continuous draining matters. If a program first buffers all output and only then applies `output[:4000]`, its displayed result is short but the Python process may already have stored hundreds of megabytes. This runner reads stdout and stderr on separate threads; once a budget is reached it keeps discarding data so pipes cannot fill, and it appends `...[truncated]` to the returned result.

The limits have edges. A timeout stops the directly launched process; it does not guarantee cleanup of every descendant, undo a file already written, or cancel a network request already sent. Process-tree control and resource quotas belong to the stronger isolation environment described next.

Run the complete local demonstration now:

```bash
python stages/12-agent-workspace-sandbox/code/demo.py
```

It writes a fixed teaching script, runs it through the `python` alias, and explicitly exports one result. It does not let a model generate arbitrary code for the local machine; the focus is how a Host runs an already allowed command.

---

## 6. A Workspace and Runner are not a security Sandbox

We now have path checks, command aliases, a limited environment, a timeout, and an output budget. These are defense layers, but they do not make hostile code safe to run on the host.

| Boundary | What the Workspace / Runner does here | What a real Sandbox also needs |
| --- | --- | --- |
| Files | Constrains paths resolved through this API | Separate filesystem or mounts, read-only input, least privilege |
| Processes | Fixes the entry point and limits the direct child | Container/VM, process groups, CPU and memory quotas |
| Network | Provides no network policy | Default-deny egress or an explicit destination allowlist |
| System calls and identity | Cannot stop Python code using the current user's permissions | Low-privilege identity and OS-level restrictions such as seccomp |
| Cleanup | Removes Workspace files | Destruction and audited recovery of the isolated instance |

Containers can add useful boundaries, but “it runs in Docker” is not enough. Mounting the Docker socket or a writable host directory can reintroduce broad host control. Similarly, network policy must be enforced by the container, VM, or infrastructure. `CommandRunner` has no such implementation, so it must not pretend to offer a decorative `network=False` switch.

Run the offline checks to inspect the limits that are actually implemented:

```bash
python stages/12-agent-workspace-sandbox/code/checks.py
```

They cover path traversal, absolute paths, symlinks, unregistered executables, environment minimization, timeouts, and streamed output truncation. The symlink check skips on systems where the test cannot create a symlink.

## 7. How Skills, models, and an execution environment fit together

A Stage 08 Skill can describe which checks and outputs a task needs. It does not grant execution authority. A production code-task flow should be:

```text
Skill procedure
    → Host validates requested action
    → isolated workspace / sandbox executes approved command
    → Host validates and exports selected artifact
```

For that reason, this chapter does not include an example that sends arbitrary Python generated by DeepSeek directly to this machine's Runner. That would bypass the isolation boundary just described and turn Stage 09 policy checks into ceremony. In a real LLM integration, the Host selects tools, validates parameters, and obtains approval outside the Sandbox. Only an explicitly allowed command enters an **already isolated** execution environment. The model proposes; the Host decides whether to execute, where to execute, and which artifacts may leave the Workspace.

## 8. Next: place these boundaries in a running service

We now have file, process, and artifact boundaries for one run. The next question is how work continues when this Worker or its process disappears: [Stage 13: Long-Horizon Harness](../13-long-horizon-harness/README.md).

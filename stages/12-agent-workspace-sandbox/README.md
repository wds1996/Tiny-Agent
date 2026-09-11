# Stage 12: The Report Is Written. How Do We Check and Deliver It? — Workspaces and Execution Boundaries

> Language: **English** | [简体中文](README.zh-CN.md)

[Stage 11](../11-multi-agent/README.md) let us assign work to different Agents without handing every specialist all our data and permissions. Now Lin, a product colleague, asks for something tangible: “Prepare a report on a support-assistant pilot, check its format, and give me the file.” Text that previously travelled in messages is about to become a real file. “I checked it” also needs to become an observable action, not merely a confident sentence.

The brief is small: the proposed pilot involves 20 support staff; the assistant suggests replies but cannot execute refunds; no pilot results are available yet. The report needs background, risks, and a recommendation. We will complete this work in one session: receive the brief, write a draft, discover a missing risks section, fix it, check again, and deliver a Markdown file. Whether one Agent writes it or several collaborate does not change the central questions: **where do the files live, which program may process them, and which result may leave the workspace?**

For now, fixed drafts make the behavior reproducible; there is no online model call. A model could later write the prose without gaining the right to run arbitrary programs. We will call the application that allocates files, checks requests, and starts processes the Host. This is the control program you write, not another mysterious Agent.

## 1. Give this report its own workbench

The easiest implementation writes `report.md` into the application's current directory. That may work for the first user. When a second report starts, the filename collides. Worse, the same directory may contain configuration, previous users' material, and credentials. We asked an assistant to write a report, not reorganize the whole computer.

The Host therefore allocates a separate directory for this execution. That is a **Workspace**: an explicit place for this run's inputs and working files, with a lifecycle the application controls. It helps us say what belongs to the run and what may be cleaned up. A directory by itself, however, is an organizational boundary, not operating-system isolation.

[`AgentWorkspace`](code/workspace.py) creates this layout:

```text
run/
├── inputs/       The original brief and source material
├── work/         Drafts being edited
└── artifacts/    Optional staging for candidate outputs, not approval to deliver
```

These names express our convention. A broken document does not become approved merely because someone saves it under `artifacts/`. The report still needs an explicit check and export. Our example exports the checked working draft directly; it does not copy it through every folder just to give each folder a job.

Here is the allocation and setup portion:

```python
with AgentWorkspace.temporary() as workspace:
    workspace.import_input("inputs/brief.txt", BRIEF)
    workspace.write_text("work/report.md", FIRST_DRAFT)
```

`temporary()` creates a fresh workbench under the system's temporary directory and removes it when execution leaves the context normally. `import_input()` is a Host setup operation; `write_text()` is the restricted interface that could be wrapped as an Agent file tool. `BRIEF` and `FIRST_DRAFT` are text, not paths or code to execute.

When the Host chooses a directory explicitly, `create()` refuses an existing directory rather than mixing old work into a new run. A random name also helps avoid collisions, but a hard-to-guess path is not a substitute for user authentication or access authorization in a service.

We now know where the report belongs. The next question is what happens when a caller asks for `../something.txt` instead.

## 2. A relative path is not permission to visit any directory

`work/report.md` names a draft under this workspace. `../other-run/report.md` first walks to the parent directory and then visits someone else's run. This is path traversal. An absolute path such as `/somewhere/private.txt` or `C:/private.txt` bypasses the workspace even more directly.

The file API accepts relative paths with `/` separators, including when the example runs on Windows. It rejects absolute paths, drive prefixes, backslashes, and malformed input before checking where the requested path actually ends up. The key part is a structural containment check:

```python
target = (self.root / relative).resolve()
try:
    local = target.relative_to(self.root)
except ValueError as exc:
    raise WorkspaceEscapeError("path escapes workspace") from exc
```

`resolve()` normalizes the path and resolves existing symbolic links. `relative_to()` asks whether the resulting target can be expressed under the workspace root. Do not replace this with a string prefix test: `/tmp/run-copy` starts with `/tmp/run`, but it is not inside that directory. The [Python pathlib documentation](https://docs.python.org/3.10/library/pathlib.html) describes these path operations.

A symbolic link introduces another trap. A harmless-looking `work/reference.md` might point to an external file even though its name contains no `..`. The helper takes a conservative approach and rejects symlinks anywhere in a requested path, including links pointing inside the workspace. The inventory operation also avoids following links out of the directory tree.

This protects file operations that actually use the helper. It does not prevent a hostile local process from replacing filesystem entries between checking and opening them, nor does it solve every hard-link, mount, or OS-permission problem. Our current premise is a private directory controlled by the Host and an audited checker. Once we want to run unfamiliar code, we need a stronger boundary. We will demonstrate why later instead of relying on the word “sandbox.”

Even within the correct directory, though, some files deserve different treatment. Should editing the report also allow editing the brief?

## 3. Let the assistant change the answer, not the assignment

The first draft omits risks. The right fix is to add the risks section, not delete “include risks” from the input brief. Editing the question is an excellent way to improve confidence and a terrible way to improve the answer.

The Host can initialize `inputs/`, but the ordinary write interface cannot modify it. After path normalization, `write_text()` checks the actual destination area:

```python
if target.relative_to(self.root).parts[0] not in {"work", "artifacts"}:
    raise PermissionError("Agent writes cannot modify inputs/")
```

Checking the normalized destination matters. `work/../inputs/brief.txt` still targets the brief, regardless of its reassuring first component. `import_input()` also uses exclusive creation, so an existing input cannot quietly be replaced. It belongs to trusted setup code and should not be exposed as another freely callable model tool.

“Read-only input” here is an API policy. We have not changed every local process's operating-system permissions. Similarly, putting the brief on disk does not make it visible to a model. The Host must still read selected content and supply it to the current model call, as in Stage 07.

There is also a size question. If a small report unexpectedly becomes hundreds of megabytes, reading the whole file and then truncating the string has already spent the memory. This API bounds the read itself:

```python
with target.open("rb") as stream:
    payload = stream.read(self.max_file_bytes + 1)
if len(payload) > self.max_file_bytes:
    raise FileBudgetError("file exceeds the read budget")
```

The extra byte distinguishes “exactly the limit” from “more remains.” The default limit is 65,536 bytes, and writes are measured after UTF-8 encoding as well. That is not necessarily 65,536 characters. It is also not a total disk quota: it constrains a file operation through this interface, not an independent process that writes around it.

Our original material and draft now have sensible locations and handling rules. It is time to turn “checked” into something the program actually does.

## 4. Offer a report check, not a general command line

Lin's format requirement is deliberately narrow: three level-two headings named `Background`, `Risks`, and `Recommendation`, each with content. The Host already has a trusted command-line checker, [`report_check.py`](code/report_check.py). It reads Markdown as text. It does not execute Python embedded in the document, render HTML, or access the network.

We could call this small check as an ordinary function. Running it as a separate program lets us examine the boundary encountered when an Agent uses a test runner, linter, or file converter. The application that launches it is the parent process; the checker is a child process. A child process is not automatically another Agent, and it does not automatically share the parent's Python objects.

The model-facing request can be this small:

```json
{"action": "check_report", "path": "work/report.md"}
```

There is no shell command, interpreter flag, script path, or environment map. The Host already knows how to check a report; the model does not need control over all the machinery. [`ReportTools.execute()`](code/report_tools.py) begins by narrowing the request:

```python
if not isinstance(proposal, dict) or set(proposal) != {"action", "path"}:
    raise ValueError("expected exactly action and path")
if proposal["action"] != "check_report":
    raise PermissionError("only check_report is available")
```

It then requires a `.md` file under `work/` and checks file type and read budget before building the command:

```python
command = ["python", "-I", "-S", "-B", str(self.checker), str(target)]
result = self.runner.run(command, timeout_seconds=5.0)
```

`python` is a Host-registered alias, replaced by the absolute `sys.executable` path. The checker also comes from the application's own code directory, not from the Agent-writable workspace. Otherwise the assistant could change the checker to always pass and truthfully report that the new checker passed. We would have successfully tested the wrong thing.

`-I` reduces module-loading influence from working directories, user packages, and `PYTHON*` environment settings. `-S` disables `site` initialization, while `-B` avoids bytecode cache writes. Our checker needs only the standard library, so these restrictions fit it. They are interpreter startup controls, **not filesystem isolation**; their exact meanings are in the [Python command-line reference](https://docs.python.org/3.10/using/cmdline.html).

An executable allowlist alone would not be narrow enough. If a caller may choose `python -c` and the following text, it can ask the interpreter to execute arbitrary code without replacing the executable. Consequently, the generic `CommandRunner` is Host-only plumbing. The Agent receives the `check_report` operation, not the entire runner interface. A service must still apply the Stage 09 identity and business policy checks at its tool boundary; this single-user example does not invent another identity system.

## 5. Avoiding a Shell does not eliminate argument policy

A program can be launched through a Shell command string or directly with an executable and argument list. A Shell interprets quoting, redirection, `&&`, and other syntax. When untrusted text is mixed into that string, data can become another command.

Our runner uses an argument list with `shell=False`. Text such as `hello && echo not-a-command` reaches the selected program as one argument rather than being split into two Shell commands. The target program still interprets its own options, however. Python's `-c` or a converter's overwrite option does not need a Shell to have consequences. Avoiding Shell injection is not equivalent to authorizing the operation. Windows batch files also have special Shell behavior, so this runner rejects `.bat` and `.cmd` registrations. See the [subprocess security considerations](https://docs.python.org/3/library/subprocess.html#security-considerations) for that distinction.

Once the Host has selected the arguments, `Popen()` starts the process. These are the relevant environment settings:

```python
process = subprocess.Popen(
    [str(executable), *command[1:]],
    cwd=self.workspace.root,
    env=env,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    shell=False,
    bufsize=0,
    start_new_session=(os.name == "posix"),
)
```

`cwd` is the child's working directory. It changes where relative paths begin; it does not stop absolute-path access. `env` is an explicit map rather than a copy of `os.environ`. The runner sets basic Python text preferences and preserves `SystemRoot` where needed on Windows, but does not automatically forward API keys, `HOME`, the inherited `PATH`, or proxy settings. Python started with `-I` ignores Python environment preferences, so the checker explicitly reads UTF-8 and emits ASCII-escaped JSON instead of relying on those variables for its protocol encoding.

`stdin=DEVNULL` means no user is waiting to answer an interactive prompt. A program reading standard input sees end-of-file rather than waiting forever for confirmation. `stdout` carries ordinary output and `stderr` carries diagnostics. The two pipes let the parent read them, but pipes have finite capacity: connecting them is not the same as collecting their data. `start_new_session` prepares a process group for cleanup on POSIX systems; we will use that in the next section.

The checker has no reason to receive a model API key. A model call that drafts the report can happen outside this boundary, with its returned text written to the workspace. Checking three headings is not a reason to lend the child all the Host's credentials.

## 6. Who deals with a stuck or excessively noisy checker?

A normal small report is checked quickly. External programs can still hang or produce huge logs. If the parent only waits for the child to exit without reading its pipes, the child may block once a pipe fills. The parent waits for the child, the child waits for the parent, and neither side's admirable patience gets the report delivered.

[`runner.py`](code/runner.py) drains stdout and stderr on separate threads while the program runs. It retains only the first `max_output_bytes` bytes per stream. It continues reading and discarding the rest so that reaching the display budget does not stop the pipe from draining. The buffer's essential update is:

```python
remaining = self.limit - len(self.data)
self.data.extend(chunk[:remaining])
self.truncated |= len(chunk) > remaining
```

This bounds the output data retained by the parent, not the child's memory, CPU usage, or disk writes. Invalid UTF-8 in diagnostic output is decoded with replacement characters; the report itself must be valid UTF-8. Truncation has a separate flag rather than masquerading as a complete JSON response. The report tool rejects a truncated, incomplete, or unparseable checker result.

Time needs a boundary too. After launching, the runner computes a deadline using a monotonic clock. Waiting for the direct process and finishing pipe reads share this budget. Why include the pipes? A child could launch another process, then exit while its descendant still holds a pipe's write end. An unconditional `thread.join()` could then keep the parent waiting even though the direct child has finished. Our report checker does not spawn children, but generic process plumbing should not confuse “main program exited” with “all output ended.”

When the budget expires, the POSIX implementation signals the process group it created. On Windows it terminates only the direct child. Cleanup and reader-thread waits also have a bounded grace period. The result reports whether the direct process exit and reader shutdown were confirmed, rather than waiting without a limit. Process creation and operating-system scheduling can themselves take time, so this is not a hard real-time guarantee.

A process group is still not a security sandbox: descendants can leave the group. The Windows path does not implement a Job Object for full process-tree control either. `cleanup_complete` refers only to this runner's direct process and pipe-reading threads; it does not prove that every possible descendant has disappeared. Stronger isolation environments need to own reclamation of the entire execution instance.

Finally, termination is not rollback. A file written before a timeout remains written; a network request already sent does not travel backwards. Keeping the checker read-only reduces this problem. Decisions about retries and side effects still belong to the reliability and idempotency rules established earlier.

## 7. “The report failed” and “the check did not finish” are different results

The first draft omits `Risks`. Our checker returns a structured negative result and exit code `2`: the check finished, but the report did not meet its contract. After risks are added, it returns `passed=true` with code `0`. A missing file, invalid encoding, or document outside the checker's supported format produces diagnostics and code `3`.

These are this checker's conventions, not universal meanings assigned to those numbers. The Host checks that the exit code agrees with the parsed result. Seeing zero is not enough to conclude that a report is correct. The result binds a verdict to the bytes that were examined:

```python
return {
    "passed": not missing,
    "missing_sections": missing,
    "sha256": hashlib.sha256(payload).hexdigest(),
}
```

`missing` comes from checking the required headings and nonempty content. The checker supports an explicit Markdown subset: it ignores apparent headings inside code fences and rejects duplicate headings or an unclosed fence. It is not a full CommonMark parser. More importantly, it is not a fact checker. A report claiming 200 staff instead of 20 could still pass this structural test. Evidence, privacy, and business quality require their own validation and evaluation.

The demonstration responds to the missing section with actual risk statements: suggested replies may be wrong and require human review, customer information should not be unnecessarily exposed, and refunds remain outside the assistant's authority. It then checks again. The revision is fixed teaching data, not an undisclosed online generation.

Now the report passes. Before copying it to Lin, however, we need one more question: could it have changed since the check?

## 8. Bind the verdict to content, not just a filename

Suppose `work/report.md` contains a valid report during checking, then another step replaces it with the old draft before export. The name remains the same, but the old “passed” receipt no longer describes the current file. Remembering only `passed=True` misses this error.

The `sha256` field is a digest computed from the file's bytes. Before export, the Host performs another bounded read and compares those bytes with the review receipt:

```python
payload = workspace.read_bytes(review.relative_path)
digest = hashlib.sha256(payload).hexdigest()
if digest != review.sha256 or not analyze_report(payload)["passed"]:
    raise ArtifactError("report changed after review; run check_report again")
```

Changed bytes require a new check. Since this structural validation is inexpensive, the Host also checks the bytes about to be exported itself. An expensive external test need not always be rerun, but its result should still be bound to an immutable input version rather than merely a path.

Export then writes this same in-memory `payload`. It does not validate one file and reopen the path to copy another. This narrows the check-to-copy gap. SHA-256 is not an approval signature or an authorization mechanism, though. A bad report with a correct digest is still a bad report. Who may export, and to which recipient, remain application decisions. The receipt in this example is created by Host code; the model cannot simply submit its own `passed=True` and turn that into evidence of execution.

The document is finally ready. We still need to move it from a temporary workbench to somewhere Lin can actually retrieve it.

## 9. Deliver the file before clearing the desk

Printing `workspace.read_text("work/report.md")` proves only that the application could read the file at that instant. It does not retain it for the user. Leaving a temporary-directory context immediately afterwards still removes the draft. An expired path is a story about a report that used to exist, not a deliverable.

An **Artifact** is a result the application selects and retains for a user or later operation. Our example copies the checked report outside the workspace. The Host chooses the destination; an Agent does not supply an arbitrary absolute export path. Creation is exclusive:

```python
with destination.open("xb") as stream:
    stream.write(payload)
return Artifact(destination, digest, len(payload))
```

`x` refuses an existing destination instead of silently replacing an earlier report. `b` preserves the checked bytes. The returned record includes location, byte size, and digest. Input material, scratch scripts, and unrelated files are not exported just because they happened to share the directory. A destination inside the workspace is rejected too: delivery must outlive workspace cleanup.

Run the whole report task from the repository root with Python 3.10 or later:

```bash
python stages/12-agent-workspace-sandbox/code/demo.py --output-dir stage12-output
```

The program prints its workspace and file inventory, followed by the two checks and export details. These are the important lines; random paths and digests are omitted here:

```text
first check: False missing: ('Risks',)
second check: True
workspace removed: True
export survives: True
```

Open the file printed after `exported:` to see the three-section report. Running the demo again chooses another output filename instead of overwriting the first. This delivery directory is intentionally retained. Tests put it inside their own temporary directory to avoid polluting the working directory.

`TemporaryDirectory` cleans up the fresh directory it allocated. It does not traverse the repository or delete pre-existing user directories. An exception that unwinds the context normally still triggers cleanup; force-killing the process or losing power cannot be expected to run Python cleanup code. An external lifecycle manager is needed for such abandoned directories. See the [tempfile documentation](https://docs.python.org/3.10/library/tempfile.html) for the context-manager behavior.

Retaining a file also does not create a complete durable service. This export does not promise power-loss-atomic publication, backup, multi-user download authorization, or safe web rendering. Markdown containing HTML, links, or other active content must be handled according to its eventual use. A `.md` extension is not permission to render it as trusted HTML in a privileged page.

## 10. Why controlling tool requests is not yet a security sandbox

After seeing the result, Lin may ask: “Since Python can run here, could the model write its own checker next time?” We cannot safely answer by replacing the trusted checker with freshly generated code. Everything so far relied on an audited program and controlled file interfaces. New code can call Python's `open()` directly and never visit `AgentWorkspace.read_text()` at all.

A harmless demonstration makes the distinction visible without reading any real private files:

```bash
python stages/12-agent-workspace-sandbox/code/boundary_demo.py
```

The program creates a file containing `SYNTHETIC CANARY` in its own temporary parent directory, next to the workspace. Asking the workspace API for `../host-canary.txt` is rejected. A Host-written diagnostic that reads the same absolute path directly in the child succeeds. Both the canary and workspace are removed at the end.

The file helper therefore does its job, but `cwd`, `shell=False`, `-I`, and output budgets have not removed the child's OS-level file access. The child ordinarily runs with the current user's identity. It may still be able to read credentials stored on disk; omitting an environment variable does not isolate every credential source.

A **security sandbox** needs to enforce restrictions even when code bypasses application helpers. For this report, the execution environment should see only the selected input and checker, not the Host's whole directory tree. Writable locations, networking, identity, system calls, CPU, memory, and process counts need real controls as well. A prompt saying “do not leave this directory” implements none of them.

Containers provide some of these mechanisms, but not safety by name. Ordinary Linux containers share a kernel. Broad writable Host mounts, a Docker socket, or privileged settings can reopen the boundary. A multi-tenant service accepting arbitrary hostile code must assess whether a stronger runtime or virtual-machine boundary is needed. The [Docker security documentation](https://docs.docker.com/engine/security/) and [gVisor's isolation model](https://gvisor.dev/docs/) help distinguish these layers. Running in another process is not enough to choose a security label.

## 11. Run the same checker in a constrained container

With the mechanism understood, we can map it to an execution environment. [`sandbox_demo.py`](code/sandbox_demo.py) still runs the same audited report checker, not arbitrary model-generated code. It mounts the checker and the report as separate read-only files. The verdict returns through stdout, while the Host retains responsibility for checking results and exporting reports.

The default command prints the configuration without starting a container:

```bash
python stages/12-agent-workspace-sandbox/code/sandbox_demo.py
```

Its first line says `PROFILE ONLY`. The printed mount paths are temporary and are removed afterwards; the printed argument list is not a command to copy and execute later. To run the integration, prepare a local Docker Engine in Linux-container mode and a trusted Python image. For a simple experiment:

```bash
docker pull python:3.12-slim
python stages/12-agent-workspace-sandbox/code/sandbox_demo.py --run
```

Pulling requires network access. Execution uses `--pull=never`, so a missing image or unavailable Docker installation causes an error rather than an implicit download or fallback to local Python. `python:3.12-slim` is a convenient mutable tag, not an immutable deployment specification. An operator requiring version pinning should select an audited image digest through `--image`. Image selection is not part of the model-facing tool request.

These options map the earlier requirements into environmental controls:

```text
--network=none
--read-only
--user=65534:65534
--cap-drop=ALL
--security-opt=no-new-privileges
--memory=128m
--memory-swap=128m
--cpus=0.5
--pids-limit=32
```

A network mode without external connectivity matches “checking this report needs no egress.” A read-only root filesystem and two read-only file mounts restrict what is exposed and writable. A non-root identity, dropped capabilities, and disabled privilege escalation reduce unnecessary authority. A size-limited writable `/tmp` provides scratch space without giving the container write access to the Host's entire workspace. These are [Docker run](https://docs.docker.com/engine/containers/run/) semantics, not options invented by our Python wrapper.

CPU, memory, and process limits are separate from the parent's output-retention budget. Equal memory and memory-swap values avoid additional swap allowance. Enforcement still depends on the Host kernel and Docker configuration; containers do not receive suitable resource quotas merely by existing. Consult the [resource constraints documentation](https://docs.docker.com/engine/containers/resource_constraints/). Removing constraints to make a command run also changes the guarantees you can make about it.

There is an important lifecycle difference here: killing the local Docker CLI does not stop a container managed by the daemon. The example requests `docker rm --force` in `finally`, using only the random name allocated for this execution, and checks the cleanup result. It does not clean up other containers. A killed Host process or disconnected daemon still requires external instance reclamation. This example is not a complete sandbox service.

The returned verdict also remains subject to validation. Exit code zero with incomplete output, a mismatched report digest, or unconfirmed cleanup is not accepted as a successful check. The standard-library tests exercise profile construction, rejection behavior, and local mechanisms; they do not claim that Docker isolation has been tested on your machine. Actual `--run` execution is a separate integration operation.

## 12. Check the boundaries, then carry the next question forward

Run the offline checks from the repository root:

```bash
python stages/12-agent-workspace-sandbox/code/checks.py
```

They require neither model credentials nor Docker. In addition to successful delivery, the checks request escaping paths, attempt to rewrite inputs, supply extra interpreter arguments, omit the risks section, and change a reviewed draft. Runner checks generate large output on both pipes, write a marker before timing out, and on POSIX exercise a descendant that keeps a pipe open after its parent exits. A test requiring unavailable symlink or platform support is explicitly skipped, not counted as evidence that the feature worked.

Try predicting two changes before editing the demo. If you append just one sentence after the second check, does the old receipt still establish that the current bytes were checked? If you select `artifacts/report.md` inside the workspace as the destination, why is the directory's reassuring name insufficient for retained delivery? Then consider a report with every required heading but invented pilot results: why can't the structural check establish factual correctness? Explaining these outcomes is more useful than memorizing method names.

Lin receives the document because the Host allocated a workspace, validated the request, ran the selected program, checked the corresponding bytes, and retained one selected artifact—not because a model announced completion. A Stage 08 Skill may describe the procedure, and Stage 11 specialists may participate in writing and review, but neither changes file or execution authority automatically. A file inventory is also not the Stage 06 checkpoint: one tells us which files exist; the other must explain how execution continues.

We can now finish a report in one work session. The next question is what happens when the process disappears halfway through and another process must decide where to resume. That is the problem of [Stage 13: long-horizon execution and recovery](../13-long-horizon-harness/README.md).

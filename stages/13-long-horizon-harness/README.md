# Stage 13: Let a Task Survive a Worker Failure — Long-Horizon Agent Harnesses

> Language: **English** | [简体中文](README.zh-CN.md)

[Stage 12](../12-agent-workspace-sandbox/README.md) made one Agent work session safer: it gave that session a Workspace and an execution boundary. A useful product also has tasks that cannot be finished in one session. For example, an Agent may draft a report, wait for verification, repair it, and publish an artifact over several minutes or hours.

Now imagine the Worker running that task crashes after the draft. The next Worker must not rely on the previous Python variables, model Context, or Workspace still existing. It needs a durable record of what has already happened and what is allowed to happen next.

A **long-horizon harness** provides that record and the rules for resuming from it. This chapter follows one report task through a draft, verification, one repair, and finalization. The offline version is deterministic so that you can observe the state transitions; the last part puts real DeepSeek calls inside the same durable structure.

---

## 1. Why an ordinary loop cannot recover a long task

For a short task, an in-memory loop is often enough:

```python
def draft(progress: dict) -> dict:
    return {"draft": "first draft"}


def verify(progress: dict) -> dict:
    return {"verified": True}


def finalize(progress: dict) -> dict:
    return {"artifact": f"report built from {progress['draft']}"}


def run_task() -> dict:
    progress: dict = {}
    for step in (draft, verify, finalize):
        progress.update(step(progress))
    return progress


print(run_task()["artifact"])
```

`progress` lives only in this Python process. If the process stops after `draft()`, the replacement process has no reliable answer to three basic questions:

```text
Which task was in progress?
Which step finished successfully?
What should the next step receive?
```

Trying to answer those questions from a chat summary or a log line creates guesses. Long-running work needs its execution state stored outside the Worker.

## 2. Turn the task into small hand-off units

This chapter uses four names consistently:

| Name | Meaning |
| --- | --- |
| **Task** | One durable unit of user-visible work, such as “prepare this report.” |
| **Work Unit** | One bounded operation within that task, such as draft or verify. |
| **Worker** | A process that temporarily performs one Work Unit. It may disappear afterwards. |
| **Ledger** | The durable record that tells every Worker the task’s current state. |

The `TaskLedger` is implemented with SQLite. Its `TaskRecord` stores the task’s `status`, the next `step_index`, a small `progress` dictionary, the repair budget, and temporary lease information. The essential lifecycle is:

```text
create task
    → a Worker claims one Work Unit
    → it persists the unit's output
    → it queues the next unit, queues a repair, or completes the task
    → any eligible Worker can claim the next unit
```

Run the complete local demonstration from the repository root:

```bash
python stages/13-long-horizon-harness/code/demo.py
```

It deliberately asks for one repair. Read its trace as a single task being handed off, not as one Worker keeping a loop alive:

| Work Unit | Output | Durable task after the unit |
| --- | --- | --- |
| draft, attempt 0 | `draft-v0` | `queued`, next `step_index=1` |
| verify, attempt 0 | repair from step 0 | `queued`, `step_index=0`, `repair_count=1` |
| draft, attempt 1 | `draft-v1` | `queued`, next `step_index=1` |
| verify, attempt 1 | verified | `queued`, next `step_index=2` |
| finalize, attempt 1 | artifact | `completed`, `step_index=3` |

The task can survive a Worker failure between any two rows because the Ledger has already persisted the hand-off information.

## 3. One Worker claims and persists exactly one unit

`LongHorizonHarness` receives a Ledger and an ordered list of step functions when it is constructed. Its complete `work_once` operation below shows the boundary: claim one task, run one step, persist its output, then advance or request a repair.

```python
def work_once(ledger, steps, *, worker_id: str):
    task = ledger.claim(worker_id=worker_id, lease_seconds=10)
    if task is None:
        return None

    output = steps[task.step_index](dict(task.progress))
    ledger.record_step_output(
        task.task_id,
        worker_id=worker_id,
        step_index=task.step_index,
        output=output,
    )

    if output.get("needs_repair"):
        progress = {**task.progress, **output}
        progress.pop("needs_repair", None)
        progress.pop("restart_step", None)
        return ledger.request_repair(
            task.task_id,
            worker_id=worker_id,
            restart_step=int(output.get("restart_step", 0)),
            progress=progress,
        )

    return ledger.advance(
        task.task_id,
        worker_id=worker_id,
        progress={**task.progress, **output},
    )
```

The real method in [`code/harness.py`](code/harness.py) has the same logic and wraps the returned task and output in `WorkResult`. Notice what this operation does **not** do: it does not keep ownership until the whole task is finished. Once the state change is persisted, the next eligible Worker can continue.

`needs_repair` and `restart_step` are Host control directives for this transition. They stay in the saved output history, but are removed from later `progress`; a later model call should receive durable task facts, not an old instruction to repair again.

## 4. A Lease gives temporary ownership

Marking a task as `running` is insufficient. If its Worker dies, it could remain `running` forever. A **Lease** records both an owner and an expiry time:

```text
lease_owner = worker-a
lease_until = 105
```

At time 104, another Worker cannot claim this task. Once the Lease expires at time 106, it can take over:

```python
from pathlib import Path
import tempfile

from ledger import TaskLedger

with tempfile.TemporaryDirectory() as tmp:
    ledger = TaskLedger(Path(tmp) / "ledger.db")
    ledger.create_task(total_steps=1)

    first = ledger.claim(worker_id="worker-a", lease_seconds=5, now=100)
    assert ledger.claim(worker_id="worker-b", lease_seconds=5, now=104) is None

    replacement = ledger.claim(worker_id="worker-b", lease_seconds=5, now=106)
    print(first.lease_owner, replacement.lease_owner)  # worker-a worker-b
```

For a Work Unit that may exceed its Lease duration, its owner calls `heartbeat()`. The Ledger accepts a heartbeat, output write, advance, or repair request only from the current owner with an unexpired Lease. A Worker whose Lease has expired cannot write a stale result after a replacement has taken over.

This protects the Ledger; it does not guarantee that an external action happens exactly once. A Worker could send an email and crash before recording success, so a replacement might repeat it. As in Stages 06 and 09, external work still needs an idempotency key, a completion check, or a compensation strategy:

```text
recovery != exactly once
```

## 5. Preserve recovery state, output history, and repair limits

The Ledger deliberately keeps different kinds of information separate:

```text
Task progress   → small facts the next Work Unit needs
Step outputs    → what every attempt actually returned
Artifact        → a large or user-facing result that must outlive the session
Model Context   → the information supplied to this one model call
```

Step output history uses `(task_id, attempt, step_index)` as its key. When a repair reruns step 0, `draft-v1` must not overwrite `draft-v0`: both are evidence of how the task changed. `ledger.step_outputs(task_id)` returns that complete history, while `step_output(task_id, step_index)` returns the newest output for convenience.

If verification finds a problem, it returns data such as:

```python
{
    "needs_repair": True,
    "restart_step": 0,
    "revision": 1,
    "feedback": "add one repair pass",
}
```

The Host, not the verifier, applies the transition: it persists the output, increments `repair_count`, releases the Lease, and queues step 0. If the task has already used `max_repairs`, it becomes `failed`. The same explicit limits are needed for time, cost, permissions, Tool scope, and approval waits. A long-running task is recoverable; it is not allowed unlimited autonomy.

Stage 12's Workspace remains the active workbench. If the next Worker needs source files, input data, dependencies, or large results, the application stores artifact references and rebuilds a Workspace. A continuation prompt can use the task ID, progress, output history, and those references. A prose summary alone is useful context, but not sufficient recovery state.

Run the offline checks after studying the state transitions:

```bash
python stages/13-long-horizon-harness/code/checks.py
```

They cover lease expiry and ownership, stale Worker writes, output history across repairs, one-unit hand-off, repair exhaustion, progress recovery, and completed-task behavior.

## 6. Put real DeepSeek calls inside the same boundary

The offline demo uses deterministic functions so that its trace and checks stay stable. A real Agent can call a model in selected Work Units without giving the model control of recovery. [`code/deepseek_long_horizon.py`](code/deepseek_long_horizon.py) uses DeepSeek to draft and review the report while leaving `TaskLedger` and `LongHorizonHarness` unchanged.

```text
DeepSeek draft/review function
    → returns a normal step-output dictionary
    → Host validates it and changes durable task state
    → another Worker can resume from the Ledger
```

The model may propose `REVISE: ...`; it cannot extend a Lease, mark a task completed, or remove a repair limit. The Host parses and validates the proposal before changing state.

Install the optional dependency and use a model ID available to your account:

```bash
python -m pip install -r stages/13-long-horizon-harness/code/requirements.txt
set "DEEPSEEK_API_KEY=your_key_here"
set "DEEPSEEK_MODEL=your_model_id"
python stages/13-long-horizon-harness/code/deepseek_long_horizon.py
```

In PowerShell, set `$env:DEEPSEEK_API_KEY="your_key_here"` and `$env:DEEPSEEK_MODEL="your_model_id"` before the final command. The example alternates Worker IDs and prints both the durable task trace and output history. Its temporary SQLite file is removed after the demonstration; a production system uses managed durable and artifact storage.

## 7. Carry this boundary into the capstone

The harness combines earlier ideas; it does not replace them:

```text
submit a durable task
    → Stage 13 Ledger grants a temporary Lease
    → bounded Agent Runtime uses the mechanisms from Stages 03–10
    → Stage 12 Workspace serves one work session
    → outputs and artifacts are persisted
    → another Worker can rehydrate and continue
```

The boundary remains consistent across the course: the model proposes a Work Unit result; the Host validates ownership, budgets, permissions, state transitions, and externally visible artifacts.

[Stage 14: Capstone Enterprise Agent](../14-capstone-enterprise-agent/README.md) now combines only the mechanisms that a support Agent actually needs.

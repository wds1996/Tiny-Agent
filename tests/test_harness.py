import asyncio
from pathlib import Path

from tiny_agent.harness import HarnessStepResult, LongHorizonHarness, TaskLedger
from tiny_agent.workspace import AgentWorkspace


def worker(task, workspace, summary):
    path = f"artifacts/{task.id}-{task.attempts}.txt"
    workspace.write_text(path, task.description)
    return HarnessStepResult(True, f"finished {task.description}", (path,))


def test_long_horizon_harness_resumes_from_externalized_ledger(tmp_path: Path) -> None:
    workspace = AgentWorkspace(tmp_path / "workspace")
    ledger = TaskLedger(workspace)
    ledger.initialize("Build a report", ["draft", "review"])

    first = LongHorizonHarness(workspace, worker)
    state_after_one = asyncio.run(first.run(max_steps=1))
    assert [task.status for task in state_after_one.tasks] == ["completed", "pending"]

    # New runtime object, same durable workspace/ledger.
    second = LongHorizonHarness(AgentWorkspace(workspace.root), worker)
    final = asyncio.run(second.run(max_steps=5))
    assert all(task.status == "completed" for task in final.tasks)
    assert len(AgentWorkspace(workspace.root).list_files()) >= 3


def test_new_runtime_recovers_task_left_running_by_crashed_worker(tmp_path: Path) -> None:
    workspace = AgentWorkspace(tmp_path / "workspace")
    ledger = TaskLedger(workspace)
    state = ledger.initialize("Recover a crash", ["fragile task"])

    # Simulate a process dying after the durable transition to running.
    state.tasks[0].status = "running"
    state.tasks[0].attempts = 1
    ledger.save(state)

    recovered = asyncio.run(LongHorizonHarness(AgentWorkspace(workspace.root), worker).run(max_steps=1))
    task = recovered.tasks[0]
    assert task.status == "completed"
    assert task.attempts == 2
    assert any("recovered_interrupted_task" in note for note in recovered.notes)

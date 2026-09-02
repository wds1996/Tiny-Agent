import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from tiny_agent.harness import HarnessStepResult, LongHorizonHarness, TaskLedger
from tiny_agent.workspace import AgentWorkspace


with TemporaryDirectory() as tmp:
    root = Path(tmp) / "workspace"
    workspace_a = AgentWorkspace(root)
    TaskLedger(workspace_a).initialize("Two-session task", ["session one", "session two"])

    def worker(task, workspace, summary):
        return HarnessStepResult(True, f"done: {task.description}")

    asyncio.run(LongHorizonHarness(workspace_a, worker).run(max_steps=1))
    del workspace_a

    # New runtime objects; continuity comes from the ledger, not Python memory.
    workspace_b = AgentWorkspace(root)
    final = asyncio.run(LongHorizonHarness(workspace_b, worker).run(max_steps=10))
    print([(task.description, task.status, task.attempts) for task in final.tasks])

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from tiny_agent.harness import HarnessStepResult, LongHorizonHarness, TaskLedger
from tiny_agent.workspace import AgentWorkspace


async def main() -> None:
    with TemporaryDirectory() as tmp:
        workspace = AgentWorkspace(Path(tmp) / "workspace")
        TaskLedger(workspace).initialize(
            "Prepare and verify a small research brief",
            ["collect evidence", "draft brief", "verify citations"],
        )

        def worker(task, workspace, summary):
            path = f"artifacts/{task.id}.md"
            workspace.write_text(path, f"# {task.description}\n\n{summary}")
            return HarnessStepResult(True, f"completed {task.description}", (path,))

        state = await LongHorizonHarness(workspace, worker).run(max_steps=10)
        print([(task.description, task.status) for task in state.tasks])
        print("artifacts:", workspace.list_files())


if __name__ == "__main__":
    asyncio.run(main())

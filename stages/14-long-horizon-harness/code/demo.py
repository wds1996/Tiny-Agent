from pathlib import Path
import tempfile

from harness import LongHorizonHarness
from ledger import TaskLedger


def draft(progress):
    revision = int(progress.get("revision", 0))
    return {"draft": f"draft-v{revision}", "revision": revision}


def verify(progress):
    if progress.get("draft") == "draft-v0":
        return {"needs_repair": True, "restart_step": 0, "revision": 1, "feedback": "add one repair pass"}
    return {"verified": True}


def finalize(progress):
    return {"artifact": f"report built from {progress['draft']}"}


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.db"
        ledger = TaskLedger(path)
        task = ledger.create_task(total_steps=3, max_repairs=1)
        print("task:", task.task_id)
        harness = LongHorizonHarness(ledger, [draft, verify, finalize])
        while True:
            result = harness.work_once(worker_id="worker-a")
            if result is None:
                break
            print(result.task.status, result.task.step_index, result.output)
            if result.task.status == "completed":
                break
        ledger_b = TaskLedger(path)
        print("final:", ledger_b.get(task.task_id))
        print("artifact:", ledger_b.step_output(task.task_id, 2))


if __name__ == "__main__":
    main()

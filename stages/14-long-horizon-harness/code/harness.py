from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from ledger import TaskLedger, TaskRecord


Step = Callable[[dict], dict]


@dataclass(frozen=True, slots=True)
class WorkResult:
    task: TaskRecord
    output: dict | None


class LongHorizonHarness:
    def __init__(self, ledger: TaskLedger, steps: Sequence[Step]) -> None:
        if not steps:
            raise ValueError("steps must not be empty")
        self.ledger = ledger
        self.steps = list(steps)

    def work_once(self, *, worker_id: str, lease_seconds: float = 10, now: float | None = None) -> WorkResult | None:
        task = self.ledger.claim(worker_id=worker_id, lease_seconds=lease_seconds, now=now)
        if task is None:
            return None
        step = self.steps[task.step_index]
        output = step(dict(task.progress))
        self.ledger.record_step_output(
            task.task_id, worker_id=worker_id, step_index=task.step_index, output=output
        )
        if output.get("needs_repair"):
            restarted = self.ledger.request_repair(
                task.task_id,
                worker_id=worker_id,
                restart_step=int(output.get("restart_step", 0)),
                progress={**task.progress, **output},
            )
            return WorkResult(restarted, output)
        advanced = self.ledger.advance(
            task.task_id, worker_id=worker_id, progress={**task.progress, **output}
        )
        return WorkResult(advanced, output)

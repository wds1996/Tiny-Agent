"""Execute one bounded step, renewing only its current lease."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import threading
import time
from typing import Any, Callable, Sequence

from ledger import LeaseError, StepResult, TaskLedger, TaskRecord, positive_seconds


Step = Callable[[dict[str, Any], dict[str, Any]], StepResult]


class UnitDeadlineExceeded(RuntimeError):
    pass


class LeaseKeeper:
    """Cooperative guard, not a mechanism for killing arbitrary Python code."""

    def __init__(self, ledger: TaskLedger, claim: TaskRecord, *, lease_seconds: float,
                 max_unit_seconds: float, monotonic: Callable[[], float] = time.monotonic):
        positive_seconds(lease_seconds)
        positive_seconds(max_unit_seconds)
        self.ledger, self.claim = ledger, claim
        self.lease_seconds = lease_seconds
        self.monotonic = monotonic
        self.deadline = monotonic() + max_unit_seconds
        self.stop = threading.Event()
        self.error: Exception | None = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def check(self) -> None:
        if isinstance(self.error, UnitDeadlineExceeded):
            raise self.error
        if self.error is not None:
            raise LeaseError("lease renewal failed; result must not be committed") from self.error
        if self.monotonic() >= self.deadline:
            raise UnitDeadlineExceeded("work unit deadline exceeded")

    def _run(self) -> None:
        while not self.stop.wait(self.lease_seconds / 3):
            try:
                self.check()
                self.ledger.heartbeat(self.claim, lease_seconds=self.lease_seconds)
            except Exception as exc:
                self.error = exc
                return

    def __enter__(self) -> LeaseKeeper:
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.stop.set()
        self.thread.join()  # Each heartbeat has its own short-lived DB connection.
        if exc_type is None:
            self.check()


@dataclass(frozen=True)
class WorkResult:
    task: TaskRecord
    output: StepResult
    executed_step: int


class LongHorizonHarness:
    def __init__(self, ledger: TaskLedger, steps: Sequence[Step], *, workflow: str,
                 lease_seconds: float = 10, max_unit_seconds: float = 120):
        if not steps or not workflow.strip():
            raise ValueError("steps and workflow version are required")
        positive_seconds(lease_seconds)
        positive_seconds(max_unit_seconds)
        self.ledger, self.steps, self.workflow = ledger, tuple(steps), workflow
        self.lease_seconds, self.max_unit_seconds = lease_seconds, max_unit_seconds

    def work_once(self, task_id: str, *, worker_id: str) -> WorkResult | None:
        if self.ledger.get(task_id).total_steps != len(self.steps):
            raise ValueError("step count does not match the saved task")
        claim = self.ledger.claim(task_id, worker_id=worker_id,
                                  workflow=self.workflow, lease_seconds=self.lease_seconds)
        if claim is None:
            return None
        # The model/function runs OUTSIDE the database transaction.
        with LeaseKeeper(self.ledger, claim, lease_seconds=self.lease_seconds,
                         max_unit_seconds=self.max_unit_seconds):
            output = self.steps[claim.step_index](
                deepcopy(claim.inputs), deepcopy(claim.progress)
            )
        advanced = self.ledger.commit_step(claim, output)
        return WorkResult(advanced, output, claim.step_index)

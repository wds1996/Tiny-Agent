from __future__ import annotations

import inspect
import json
from dataclasses import asdict, dataclass, field
from typing import Awaitable, Callable, Literal, Sequence
from uuid import uuid4

from .workspace import AgentWorkspace


TaskStatus = Literal["pending", "running", "completed", "failed"]


@dataclass(slots=True)
class TaskRecord:
    id: str
    description: str
    status: TaskStatus = "pending"
    attempts: int = 0
    note: str = ""
    artifacts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HarnessState:
    objective: str
    tasks: list[TaskRecord]
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class HarnessStepResult:
    success: bool
    note: str
    artifacts: tuple[str, ...] = ()
    new_tasks: tuple[str, ...] = ()


HarnessWorker = Callable[
    [TaskRecord, AgentWorkspace, str],
    HarnessStepResult | Awaitable[HarnessStepResult],
]


class TaskLedger:
    """Durable, human-readable task/progress state stored outside model context."""

    def __init__(self, workspace: AgentWorkspace, relative_path: str = ".tiny-agent/task-ledger.json") -> None:
        self.workspace = workspace
        self.path = workspace.resolve(relative_path)

    def initialize(self, objective: str, tasks: Sequence[str]) -> HarnessState:
        if not objective.strip() or not tasks:
            raise ValueError("objective and at least one task are required")
        state = HarnessState(
            objective=objective.strip(),
            tasks=[TaskRecord(id=f"task-{index}", description=text.strip()) for index, text in enumerate(tasks, 1)],
        )
        if any(not task.description for task in state.tasks):
            raise ValueError("task descriptions must be non-empty")
        self.save(state)
        return state

    def load(self) -> HarnessState:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return HarnessState(
            objective=str(data["objective"]),
            tasks=[TaskRecord(**item) for item in data.get("tasks", [])],
            notes=[str(item) for item in data.get("notes", [])],
        )

    def recover_interrupted(self, state: HarnessState) -> bool:
        """Turn persisted `running` tasks into explicit retry candidates.

        A process can die after marking a task running but before recording its
        terminal result. We cannot know whether external side effects happened,
        so recovery is visible in notes and replay safety remains the task/tool
        designer's responsibility.
        """

        changed = False
        for task in state.tasks:
            if task.status != "running":
                continue
            task.status = "pending"
            task.note = "recovered_interrupted_task"
            state.notes.append(f"{task.id}:recovered_interrupted_task")
            changed = True
        if changed:
            self.save(state)
        return changed

    def save(self, state: HarnessState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def exists(self) -> bool:
        return self.path.is_file()


class LongHorizonHarness:
    """Small session-independent harness for incremental, resumable work."""

    def __init__(self, workspace: AgentWorkspace, worker: HarnessWorker, *, ledger: TaskLedger | None = None) -> None:
        self.workspace = workspace
        self.worker = worker
        self.ledger = ledger or TaskLedger(workspace)

    async def run(self, *, max_steps: int = 10) -> HarnessState:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        state = self.ledger.load()
        self.ledger.recover_interrupted(state)

        for _ in range(max_steps):
            task = next((item for item in state.tasks if item.status == "pending"), None)
            if task is None:
                break
            task.status = "running"
            task.attempts += 1
            self.ledger.save(state)
            try:
                value = self.worker(task, self.workspace, self.handoff_summary(state))
                result = await value if inspect.isawaitable(value) else value
            except Exception as exc:
                task.status = "failed"
                task.note = f"worker_failed:{type(exc).__name__}"
                state.notes.append(task.note)
                self.ledger.save(state)
                continue

            task.note = result.note
            task.artifacts.extend(result.artifacts)
            task.status = "completed" if result.success else "failed"
            state.notes.append(f"{task.id}:{task.note}")
            for description in result.new_tasks:
                state.tasks.append(TaskRecord(id=f"task-{uuid4().hex[:8]}", description=description))
            self.ledger.save(state)
        return state

    @staticmethod
    def handoff_summary(state: HarnessState, *, max_notes: int = 6) -> str:
        counts = {status: 0 for status in ("pending", "running", "completed", "failed")}
        for task in state.tasks:
            counts[task.status] += 1
        recent = state.notes[-max_notes:]
        return (
            f"Objective: {state.objective}\n"
            f"Progress: {counts}\n"
            f"Recent notes: {recent}\n"
            "Use the workspace and ledger as externalized state; do not assume hidden prior context."
        )

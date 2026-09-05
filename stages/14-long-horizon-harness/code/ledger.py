from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
import time
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class TaskRecord:
    task_id: str
    status: str
    step_index: int
    total_steps: int
    lease_owner: str | None
    lease_until: float | None
    repair_count: int
    max_repairs: int
    progress: dict[str, Any]


class LeaseError(RuntimeError):
    pass


class TaskLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _session(self):
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._session() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    total_steps INTEGER NOT NULL,
                    lease_owner TEXT,
                    lease_until REAL,
                    repair_count INTEGER NOT NULL,
                    max_repairs INTEGER NOT NULL,
                    progress_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS step_outputs (
                    task_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    output_json TEXT NOT NULL,
                    PRIMARY KEY (task_id, step_index)
                )
                """
            )

    def create_task(self, *, total_steps: int, max_repairs: int = 1) -> TaskRecord:
        if total_steps <= 0:
            raise ValueError("total_steps must be positive")
        task_id = str(uuid4())
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO tasks(
                    task_id, status, step_index, total_steps,
                    lease_owner, lease_until, repair_count, max_repairs, progress_json
                ) VALUES (?, 'queued', 0, ?, NULL, NULL, 0, ?, '{}')
                """,
                (task_id, total_steps, max_repairs),
            )
        return self.get(task_id)

    def get(self, task_id: str) -> TaskRecord:
        with self._session() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return self._record(row)

    def claim(self, *, worker_id: str, lease_seconds: float, now: float | None = None) -> TaskRecord | None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        now = time.time() if now is None else now
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status='queued'
                   OR (status='running' AND lease_until IS NOT NULL AND lease_until < ?)
                ORDER BY task_id
                LIMIT 1
                """,
                (now,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE tasks SET status='running', lease_owner=?, lease_until=? WHERE task_id=?",
                (worker_id, now + lease_seconds, row["task_id"]),
            )
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (row["task_id"],)).fetchone()
        return self._record(row)

    def heartbeat(self, task_id: str, *, worker_id: str, lease_seconds: float, now: float | None = None) -> TaskRecord:
        now = time.time() if now is None else now
        with self._session() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            if row["status"] != "running" or row["lease_owner"] != worker_id:
                raise LeaseError("worker does not own the task lease")
            conn.execute("UPDATE tasks SET lease_until=? WHERE task_id=?", (now + lease_seconds, task_id))
        return self.get(task_id)

    def record_step_output(self, task_id: str, *, worker_id: str, step_index: int, output: dict[str, Any]) -> None:
        task = self.get(task_id)
        if task.status != "running" or task.lease_owner != worker_id:
            raise LeaseError("worker does not own the task lease")
        encoded = json.dumps(output, ensure_ascii=False, sort_keys=True)
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO step_outputs(task_id, step_index, output_json)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id, step_index)
                DO UPDATE SET output_json=excluded.output_json
                """,
                (task_id, step_index, encoded),
            )

    def advance(self, task_id: str, *, worker_id: str, progress: dict[str, Any]) -> TaskRecord:
        task = self.get(task_id)
        if task.status != "running" or task.lease_owner != worker_id:
            raise LeaseError("worker does not own the task lease")
        next_step = task.step_index + 1
        status = "completed" if next_step >= task.total_steps else "queued"
        with self._session() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status=?, step_index=?, lease_owner=NULL, lease_until=NULL, progress_json=?
                WHERE task_id=?
                """,
                (status, next_step, json.dumps(progress, ensure_ascii=False, sort_keys=True), task_id),
            )
        return self.get(task_id)

    def request_repair(self, task_id: str, *, worker_id: str, restart_step: int, progress: dict[str, Any]) -> TaskRecord:
        task = self.get(task_id)
        if task.status != "running" or task.lease_owner != worker_id:
            raise LeaseError("worker does not own the task lease")
        if task.repair_count >= task.max_repairs:
            raise RuntimeError("repair budget exhausted")
        if not 0 <= restart_step < task.total_steps:
            raise ValueError("invalid restart_step")
        with self._session() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status='queued', step_index=?, lease_owner=NULL, lease_until=NULL,
                    repair_count=repair_count+1, progress_json=?
                WHERE task_id=?
                """,
                (restart_step, json.dumps(progress, ensure_ascii=False, sort_keys=True), task_id),
            )
        return self.get(task_id)

    def step_output(self, task_id: str, step_index: int) -> dict[str, Any] | None:
        with self._session() as conn:
            row = conn.execute(
                "SELECT output_json FROM step_outputs WHERE task_id=? AND step_index=?",
                (task_id, step_index),
            ).fetchone()
        return None if row is None else json.loads(row["output_json"])

    @staticmethod
    def _record(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            task_id=row["task_id"], status=row["status"], step_index=int(row["step_index"]),
            total_steps=int(row["total_steps"]), lease_owner=row["lease_owner"],
            lease_until=row["lease_until"], repair_count=int(row["repair_count"]),
            max_repairs=int(row["max_repairs"]), progress=json.loads(row["progress_json"]),
        )

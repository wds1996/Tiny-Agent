"""A local, transaction-backed task ledger for trusted workers on one host."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable, Iterator
from uuid import uuid4


SCHEMA_VERSION = 2


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def positive_seconds(value: float) -> None:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError("duration must be finite and positive")


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    workflow: str
    status: str
    step_index: int
    total_steps: int
    inputs: dict[str, Any]
    progress: dict[str, Any]
    repair_count: int
    max_repairs: int
    claim_count: int
    max_claims: int
    lease_owner: str | None
    lease_token: str | None
    lease_until: float | None
    failure: str | None


@dataclass(frozen=True)
class StepResult:
    data: dict[str, Any]
    restart_step: int | None = None
    artifact: str | None = None


class LeaseError(RuntimeError):
    pass


class TaskLedger:
    def __init__(self, path: str | Path, *, clock: Callable[[], float] = time.time):
        if str(path) == ":memory:":
            raise ValueError("use a database file that survives a worker process")
        self.path = str(path)
        self.clock = clock
        with self._session(write=True) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            if version != SCHEMA_VERSION and (version != 0 or tables):
                raise RuntimeError("incompatible ledger schema; choose a new database path")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY, workflow TEXT NOT NULL,
                    status TEXT NOT NULL, step_index INTEGER NOT NULL,
                    total_steps INTEGER NOT NULL, inputs_json TEXT NOT NULL,
                    progress_json TEXT NOT NULL, repair_count INTEGER NOT NULL,
                    max_repairs INTEGER NOT NULL, claim_count INTEGER NOT NULL,
                    max_claims INTEGER NOT NULL, lease_owner TEXT,
                    lease_token TEXT, lease_until REAL, failure TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS step_outputs (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    lease_token TEXT NOT NULL UNIQUE, worker_id TEXT NOT NULL,
                    repair_count INTEGER NOT NULL, step_index INTEGER NOT NULL,
                    output_json TEXT NOT NULL, restart_step INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    task_id TEXT PRIMARY KEY REFERENCES tasks(task_id),
                    content TEXT NOT NULL, sha256 TEXT NOT NULL
                )
            """)
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @contextmanager
    def _session(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, isolation_level=None, timeout=1.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _read(conn: sqlite3.Connection, task_id: str) -> TaskRecord:
        row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown task: {task_id}")
        fields = dict(row)
        fields["inputs"] = json.loads(fields.pop("inputs_json"))
        fields["progress"] = json.loads(fields.pop("progress_json"))
        return TaskRecord(**fields)

    def create_task(self, *, task_id: str, workflow: str, inputs: dict[str, Any],
                    total_steps: int = 3, max_repairs: int = 1,
                    max_claims: int = 12) -> TaskRecord:
        if not task_id.strip() or not workflow.strip() or not isinstance(inputs, dict):
            raise ValueError("task ID, workflow and input object are required")
        for name, value, minimum in (("total_steps", total_steps, 1),
                                     ("max_repairs", max_repairs, 0),
                                     ("max_claims", max_claims, 1)):
            if type(value) is not int or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        with self._session(write=True) as conn:
            # A duplicate ID is an error, never a request to overwrite old progress.
            conn.execute("""
                INSERT INTO tasks VALUES (
                    ?, ?, 'queued', 0, ?, ?, '{}', 0, ?, 0, ?, NULL, NULL, NULL, NULL
                )
            """, (task_id, workflow, total_steps, encode(inputs), max_repairs, max_claims))
            return self._read(conn, task_id)

    def get(self, task_id: str) -> TaskRecord:
        with self._session() as conn:
            return self._read(conn, task_id)

    def claim(self, task_id: str, *, worker_id: str, workflow: str,
              lease_seconds: float = 10) -> TaskRecord | None:
        positive_seconds(lease_seconds)
        if not worker_id.strip():
            raise ValueError("worker_id must not be blank")
        with self._session(write=True) as conn:
            task = self._read(conn, task_id)
            now = self.clock()  # Read the clock after acquiring the write lock.
            if task.workflow != workflow:
                raise ValueError("worker workflow does not match the saved task")
            if task.status in {"completed", "failed"}:
                return None
            if task.status == "running" and task.lease_until is not None:
                if task.lease_until > now:
                    return None
            if task.claim_count >= task.max_claims:
                conn.execute("""
                    UPDATE tasks SET status='failed', failure='claim budget exhausted',
                        lease_owner=NULL, lease_token=NULL, lease_until=NULL
                    WHERE task_id=?
                """, (task_id,))
                return None
            conn.execute("""
                UPDATE tasks SET status='running', lease_owner=?, lease_token=?,
                    lease_until=?, claim_count=claim_count+1 WHERE task_id=?
            """, (worker_id, uuid4().hex, now + lease_seconds, task_id))
            return self._read(conn, task_id)

    def _require_active(self, conn: sqlite3.Connection, claim: TaskRecord) -> TaskRecord:
        current = self._read(conn, claim.task_id)
        if (current.status != "running"
                or current.lease_owner != claim.lease_owner
                or current.lease_token != claim.lease_token
                or current.step_index != claim.step_index
                or current.repair_count != claim.repair_count
                or current.lease_until is None
                or current.lease_until <= self.clock()):
            raise LeaseError("claim is no longer the active lease")
        return current

    def heartbeat(self, claim: TaskRecord, *, lease_seconds: float) -> None:
        positive_seconds(lease_seconds)
        with self._session(write=True) as conn:
            current = self._require_active(conn, claim)
            conn.execute("UPDATE tasks SET lease_until=? WHERE task_id=?", (
                max(current.lease_until, self.clock() + lease_seconds), claim.task_id,
            ))

    def commit_step(self, claim: TaskRecord, result: StepResult) -> TaskRecord:
        if not isinstance(result, StepResult) or not isinstance(result.data, dict):
            raise ValueError("a step must return StepResult with a data object")
        output_json = encode(result.data)
        with self._session(write=True) as conn:
            task = self._require_active(conn, claim)
            restart = result.restart_step
            if restart is not None and (
                    type(restart) is not int or not 0 <= restart <= task.step_index):
                raise ValueError("repair must target an existing, already reached step")
            if result.artifact is not None and (
                    not isinstance(result.artifact, str) or not result.artifact.strip()
                    or restart is not None or task.step_index != task.total_steps - 1):
                raise ValueError("only the final forward step can publish non-empty text")

            progress = {**task.progress, **json.loads(output_json)}
            repair_count = task.repair_count
            failure = None
            if restart is None:
                next_step = task.step_index + 1
                status = "completed" if next_step == task.total_steps else "queued"
            elif repair_count >= task.max_repairs:
                next_step, status, failure = task.step_index, "failed", "repair budget exhausted"
            else:
                next_step, status = restart, "queued"
                repair_count += 1

            conn.execute("""
                INSERT INTO step_outputs (
                    task_id, lease_token, worker_id, repair_count,
                    step_index, output_json, restart_step
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (task.task_id, task.lease_token, task.lease_owner, task.repair_count,
                  task.step_index, output_json, restart))
            if result.artifact is not None:
                digest = hashlib.sha256(result.artifact.encode("utf-8")).hexdigest()
                conn.execute("INSERT INTO artifacts VALUES (?, ?, ?)",
                             (task.task_id, result.artifact, digest))
                progress["artifact_ref"] = f"sqlite:artifacts/{task.task_id}"
            # History, artifact and next-step state share this ONE transaction.
            conn.execute("""
                UPDATE tasks SET status=?, step_index=?, progress_json=?,
                    repair_count=?, failure=?, lease_owner=NULL,
                    lease_token=NULL, lease_until=NULL WHERE task_id=?
            """, (status, next_step, encode(progress), repair_count, failure, task.task_id))
            return self._read(conn, task.task_id)

    def step_outputs(self, task_id: str) -> tuple[dict[str, Any], ...]:
        with self._session() as conn:
            rows = conn.execute("""
                SELECT repair_count, step_index, worker_id, output_json, restart_step
                FROM step_outputs WHERE task_id=? ORDER BY sequence
            """, (task_id,)).fetchall()
        return tuple({"repair_count": row["repair_count"], "step_index": row["step_index"],
                      "worker_id": row["worker_id"], "output": json.loads(row["output_json"]),
                      "restart_step": row["restart_step"]} for row in rows)

    def artifact(self, task_id: str) -> str:
        with self._session() as conn:
            if self._read(conn, task_id).status != "completed":
                raise ValueError("task has no completed artifact")
            row = conn.execute("SELECT * FROM artifacts WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError("artifact is missing")
        digest = hashlib.sha256(row["content"].encode("utf-8")).hexdigest()
        if digest != row["sha256"]:
            raise ValueError("artifact checksum mismatch")
        return row["content"]

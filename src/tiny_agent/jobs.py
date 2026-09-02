from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class RunJob:
    run_id: str
    payload: Mapping[str, Any]
    status: str
    lease_owner: str | None
    lease_expires_at: float | None
    result: Mapping[str, Any] | None
    error_code: str | None


class SQLiteRunQueue:
    """Small durable run queue demonstrating lease-based worker ownership.

    This is an educational local backend. Production systems may use Postgres,
    a managed queue, or a workflow engine, but the semantics remain: durable
    enqueue, atomic claim, bounded lease, terminal result, and crash recovery.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(Path(path))
        self._setup()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def _setup(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    lease_owner TEXT,
                    lease_expires_at REAL,
                    result TEXT,
                    error_code TEXT
                )
                """
            )

    def enqueue(self, payload: Mapping[str, Any], *, run_id: str | None = None) -> str:
        identifier = run_id or uuid4().hex
        encoded = _encode_json(payload)
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO runs(run_id,payload,status,created_at,updated_at) VALUES(?,?,?,?,?)",
                (identifier, encoded, "queued", now, now),
            )
        return identifier

    def claim(self, *, worker_id: str, lease_seconds: float = 30.0) -> RunJob | None:
        if not worker_id.strip() or lease_seconds <= 0:
            raise ValueError("worker_id and lease_seconds must be valid")
        now = time.time()
        expires = now + lease_seconds
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM runs
                WHERE status='queued'
                   OR (status='running' AND lease_expires_at IS NOT NULL AND lease_expires_at < ?)
                ORDER BY created_at, run_id
                LIMIT 1
                """,
                (now,),
            ).fetchone()
            if row is None:
                connection.execute("COMMIT")
                return None
            connection.execute(
                """
                UPDATE runs
                SET status='running', lease_owner=?, lease_expires_at=?, updated_at=?
                WHERE run_id=?
                """,
                (worker_id, expires, now, row["run_id"]),
            )
            connection.execute("COMMIT")
        return self.get(str(row["run_id"]))

    def complete(self, run_id: str, *, worker_id: str, result: Mapping[str, Any]) -> None:
        self._finish(run_id, worker_id=worker_id, status="completed", result=result)

    def fail(self, run_id: str, *, worker_id: str, error_code: str) -> None:
        if not error_code.strip():
            raise ValueError("error_code must be non-empty")
        self._finish(run_id, worker_id=worker_id, status="failed", error_code=error_code)

    def _finish(
        self,
        run_id: str,
        *,
        worker_id: str,
        status: str,
        result: Mapping[str, Any] | None = None,
        error_code: str | None = None,
    ) -> None:
        encoded_result = _encode_json(result) if result is not None else None
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE runs
                SET status=?, result=?, error_code=?, lease_owner=NULL,
                    lease_expires_at=NULL, updated_at=?
                WHERE run_id=? AND status='running' AND lease_owner=?
                """,
                (status, encoded_result, error_code, time.time(), run_id, worker_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("worker does not own an active lease for this run")

    def get(self, run_id: str) -> RunJob:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return RunJob(
            run_id=str(row["run_id"]),
            payload=json.loads(row["payload"]),
            status=str(row["status"]),
            lease_owner=row["lease_owner"],
            lease_expires_at=row["lease_expires_at"],
            result=json.loads(row["result"]) if row["result"] else None,
            error_code=row["error_code"],
        )


def _encode_json(value: Mapping[str, Any] | None) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("run payload/result must be JSON-serializable") from exc

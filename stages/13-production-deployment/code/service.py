from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class TrustedIdentity:
    user_id: str
    tenant_id: str


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    thread_id: str
    user_id: str
    tenant_id: str
    status: str
    input_text: str
    output_text: str | None
    created_at: str
    updated_at: str


class BackpressureError(RuntimeError):
    pass


class RunStore:
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
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    idempotency_key TEXT,
                    status TEXT NOT NULL,
                    input_text TEXT NOT NULL,
                    output_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, idempotency_key)
                )
                """
            )

    def queued_count(self, tenant_id: str) -> int:
        with self._session() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM runs WHERE tenant_id=? AND status='queued'",
                (tenant_id,),
            ).fetchone()
        return int(row["n"])

    def submit(
        self,
        *,
        identity: TrustedIdentity,
        thread_id: str,
        input_text: str,
        idempotency_key: str | None,
        max_queued_per_tenant: int,
    ) -> RunRecord:
        if not thread_id.strip() or not input_text.strip():
            raise ValueError("thread_id and input_text are required")

        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                row = conn.execute(
                    """
                    SELECT * FROM runs
                    WHERE tenant_id=? AND idempotency_key=?
                    """,
                    (identity.tenant_id, idempotency_key),
                ).fetchone()
                if row is not None:
                    return self._record(row)

            queued = conn.execute(
                "SELECT COUNT(*) AS n FROM runs WHERE tenant_id=? AND status='queued'",
                (identity.tenant_id,),
            ).fetchone()["n"]
            if int(queued) >= max_queued_per_tenant:
                raise BackpressureError("tenant queue is full")

            run_id = str(uuid4())
            now = utc_now()
            conn.execute(
                """
                INSERT INTO runs(
                    run_id, thread_id, user_id, tenant_id, idempotency_key,
                    status, input_text, output_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'queued', ?, NULL, ?, ?)
                """,
                (
                    run_id,
                    thread_id,
                    identity.user_id,
                    identity.tenant_id,
                    idempotency_key,
                    input_text,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return self._record(row)

    def get(self, *, identity: TrustedIdentity, run_id: str) -> RunRecord:
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id=? AND tenant_id=?",
                (run_id, identity.tenant_id),
            ).fetchone()
        if row is None:
            raise KeyError("run not found")
        return self._record(row)

    def claim_next(self) -> RunRecord | None:
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT * FROM runs
                WHERE status='queued'
                ORDER BY created_at, run_id
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            now = utc_now()
            conn.execute(
                "UPDATE runs SET status='running', updated_at=? WHERE run_id=?",
                (now, row["run_id"]),
            )
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id=?", (row["run_id"],)
            ).fetchone()
        return self._record(row)

    def complete(self, run_id: str, output_text: str) -> RunRecord:
        now = utc_now()
        with self._session() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status='completed', output_text=?, updated_at=?
                WHERE run_id=? AND status='running'
                """,
                (output_text, now, run_id),
            )
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return self._record(row)

    def ready(self) -> bool:
        try:
            with self._session() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    @staticmethod
    def _record(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            thread_id=row["thread_id"],
            user_id=row["user_id"],
            tenant_id=row["tenant_id"],
            status=row["status"],
            input_text=row["input_text"],
            output_text=row["output_text"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class AgentService:
    def __init__(self, store: RunStore, *, max_queued_per_tenant: int = 4) -> None:
        self.store = store
        self.max_queued_per_tenant = max_queued_per_tenant

    def submit(
        self,
        *,
        identity: TrustedIdentity,
        thread_id: str,
        input_text: str,
        idempotency_key: str | None = None,
    ) -> RunRecord:
        return self.store.submit(
            identity=identity,
            thread_id=thread_id,
            input_text=input_text,
            idempotency_key=idempotency_key,
            max_queued_per_tenant=self.max_queued_per_tenant,
        )

    def run_one(self) -> RunRecord | None:
        run = self.store.claim_next()
        if run is None:
            return None
        output = f"processed for tenant={run.tenant_id}: {run.input_text}"
        return self.store.complete(run.run_id, output)

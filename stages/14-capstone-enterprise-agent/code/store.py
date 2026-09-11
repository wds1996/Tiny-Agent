from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class SupportRun:
    run_id: str
    tenant_id: str
    user_id: str
    status: str
    question: str
    order_id: str | None
    proposed_amount: str | None
    evidence_ids: tuple[str, ...]
    answer: str


class SupportStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._init_db()

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
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
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    question TEXT NOT NULL,
                    order_id TEXT,
                    proposed_amount TEXT,
                    evidence_json TEXT NOT NULL,
                    answer TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS effects (
                    effect_key TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL
                )
                """
            )

    def create_run(
        self,
        *,
        tenant_id: str,
        user_id: str,
        status: str,
        question: str,
        order_id: str | None,
        proposed_amount: str | None,
        evidence_ids: tuple[str, ...],
        answer: str,
    ) -> SupportRun:
        run_id = str(uuid4())
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO runs(
                    run_id, tenant_id, user_id, status, question,
                    order_id, proposed_amount, evidence_json, answer
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    tenant_id,
                    user_id,
                    status,
                    question,
                    order_id,
                    proposed_amount,
                    json.dumps(evidence_ids),
                    answer,
                ),
            )
        return self.get_run(run_id, tenant_id=tenant_id, user_id=user_id)

    def get_run(self, run_id: str, *, tenant_id: str, user_id: str) -> SupportRun:
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT * FROM runs
                WHERE run_id=? AND tenant_id=? AND user_id=?
                """,
                (run_id, tenant_id, user_id),
            ).fetchone()
        if row is None:
            raise KeyError("run not found")
        return self._record(row)

    def complete_run(self, run_id: str, *, answer: str) -> None:
        with self._session() as conn:
            conn.execute(
                "UPDATE runs SET status='completed', answer=? WHERE run_id=?",
                (answer, run_id),
            )

    def reject_run(self, run_id: str, *, answer: str) -> None:
        with self._session() as conn:
            conn.execute(
                "UPDATE runs SET status='rejected', answer=? WHERE run_id=?",
                (answer, run_id),
            )

    def record_refund_once(
        self,
        *,
        run_id: str,
        order_id: str,
        amount: str,
    ) -> dict[str, str]:
        key = f"{run_id}:refund"
        result = {
            "status": "refunded",
            "order_id": order_id,
            "amount": amount,
        }
        encoded = json.dumps(result, sort_keys=True)
        with self._session() as conn:
            row = conn.execute(
                "SELECT result_json FROM effects WHERE effect_key=?",
                (key,),
            ).fetchone()
            if row is not None:
                return json.loads(row["result_json"])
            conn.execute(
                "INSERT INTO effects(effect_key, result_json) VALUES (?, ?)",
                (key, encoded),
            )
        return result

    def effect_count(self) -> int:
        with self._session() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM effects").fetchone()
        return int(row["n"])

    @staticmethod
    def _record(row: sqlite3.Row) -> SupportRun:
        return SupportRun(
            run_id=row["run_id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            status=row["status"],
            question=row["question"],
            order_id=row["order_id"],
            proposed_amount=row["proposed_amount"],
            evidence_ids=tuple(json.loads(row["evidence_json"])),
            answer=row["answer"],
        )

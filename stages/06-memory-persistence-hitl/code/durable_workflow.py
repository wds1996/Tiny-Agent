from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import json
import sqlite3
from pathlib import Path
from typing import Any

from approval import ApprovalDecision, ApprovalRequest, resolve_refund_arguments


@dataclass(frozen=True, slots=True)
class WorkflowState:
    run_id: str
    phase: str
    action: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None


class SQLiteCheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

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
                CREATE TABLE IF NOT EXISTS checkpoints (
                    run_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS effects (
                    idempotency_key TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL
                )
                """
            )

    def save(self, state: WorkflowState) -> None:
        payload = json.dumps(asdict(state), ensure_ascii=False, sort_keys=True)
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints(run_id, state_json)
                VALUES (?, ?)
                ON CONFLICT(run_id) DO UPDATE SET state_json=excluded.state_json
                """,
                (state.run_id, payload),
            )

    def load(self, run_id: str) -> WorkflowState:
        with self._session() as conn:
            row = conn.execute(
                "SELECT state_json FROM checkpoints WHERE run_id=?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown run_id: {run_id}")
        return WorkflowState(**json.loads(row[0]))

    def record_effect_once(
        self,
        idempotency_key: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
        with self._session() as conn:
            existing = conn.execute(
                "SELECT result_json FROM effects WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                return json.loads(existing[0])
            conn.execute(
                "INSERT INTO effects(idempotency_key, result_json) VALUES (?, ?)",
                (idempotency_key, encoded),
            )
        return result


class RefundWorkflow:
    def __init__(self, store: SQLiteCheckpointStore) -> None:
        self.store = store

    def start(self, *, run_id: str, order_id: str, amount: str) -> ApprovalRequest:
        arguments = {"order_id": order_id, "amount": amount}
        state = WorkflowState(
            run_id=run_id,
            phase="waiting_approval",
            action="issue_refund",
            arguments=arguments,
        )
        self.store.save(state)
        return ApprovalRequest(
            run_id=run_id,
            action=state.action,
            arguments=arguments,
            reason="Refund changes external financial state.",
        )

    def resume(self, run_id: str, decision: ApprovalDecision) -> WorkflowState:
        state = self.store.load(run_id)
        if state.phase != "waiting_approval":
            return state

        resolved = resolve_refund_arguments(state.arguments, decision)
        if resolved is None:
            final = WorkflowState(
                run_id=run_id,
                phase="rejected",
                action=state.action,
                arguments=state.arguments,
                result=None,
            )
            self.store.save(final)
            return final

        idempotency_key = f"{run_id}:issue_refund"
        result = self.store.record_effect_once(
            idempotency_key,
            {
                "status": "refunded",
                "order_id": resolved["order_id"],
                "amount": resolved["amount"],
            },
        )
        final = WorkflowState(
            run_id=run_id,
            phase="completed",
            action=state.action,
            arguments=resolved,
            result=result,
        )
        self.store.save(final)
        return final

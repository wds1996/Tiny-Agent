from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from approval import (
    CREATE_SUPPORT_CASE,
    ApprovalDecision,
    ApprovalRequest,
    ReviewerContext,
    authorize_reviewer,
    resolve_case_arguments,
    validate_case_arguments,
)


@dataclass(frozen=True, slots=True)
class WorkflowState:
    run_id: str
    thread_id: str
    owner_id: str
    phase: str
    action: str
    arguments: dict[str, str]
    result: dict[str, Any] | None = None


class SQLiteWorkflowStore:
    """Persist one current checkpoint and one teaching effect per idempotency key."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._init_db()

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=5.0)
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

    @staticmethod
    def _encode_state(state: WorkflowState) -> str:
        return json.dumps(asdict(state), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _save_with_conn(conn: sqlite3.Connection, state: WorkflowState) -> None:
        conn.execute(
            """
            INSERT INTO checkpoints(run_id, state_json)
            VALUES (?, ?)
            ON CONFLICT(run_id) DO UPDATE SET state_json=excluded.state_json
            """,
            (state.run_id, SQLiteWorkflowStore._encode_state(state)),
        )

    def save(self, state: WorkflowState) -> None:
        with self._session() as conn:
            self._save_with_conn(conn, state)

    def load(self, run_id: str) -> WorkflowState:
        with self._session() as conn:
            row = conn.execute(
                "SELECT state_json FROM checkpoints WHERE run_id=?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown run_id: {run_id}")
        return WorkflowState(**json.loads(row[0]))

    def complete_case_once(
        self,
        *,
        waiting_state: WorkflowState,
        arguments: dict[str, str],
    ) -> WorkflowState:
        """Atomically record the teaching effect and completed checkpoint in SQLite.

        This protects only this local teaching database. It does not make a remote
        MCP service or payment API exactly-once.
        """

        idempotency_key = f"{waiting_state.run_id}:{waiting_state.action}"
        case_id = "CASE-" + hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:8].upper()
        proposed_result = {
            "status": "created",
            "case_id": case_id,
            "order_id": arguments["order_id"],
            "reason": arguments["reason"],
        }
        encoded_result = json.dumps(proposed_result, ensure_ascii=False, sort_keys=True)

        with self._session() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO effects(idempotency_key, result_json)
                VALUES (?, ?)
                """,
                (idempotency_key, encoded_result),
            )
            row = conn.execute(
                "SELECT result_json FROM effects WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                raise RuntimeError("teaching effect was not stored")
            result = json.loads(row[0])
            completed = WorkflowState(
                run_id=waiting_state.run_id,
                thread_id=waiting_state.thread_id,
                owner_id=waiting_state.owner_id,
                phase="completed",
                action=waiting_state.action,
                arguments=arguments,
                result=result,
            )
            self._save_with_conn(conn, completed)
        return completed

    def effect_count(self) -> int:
        with self._session() as conn:
            row = conn.execute("SELECT COUNT(*) FROM effects").fetchone()
        return int(row[0]) if row is not None else 0


class SupportCaseWorkflow:
    def __init__(self, store: SQLiteWorkflowStore) -> None:
        self.store = store

    @staticmethod
    def _request_from_state(state: WorkflowState) -> ApprovalRequest:
        return ApprovalRequest(
            run_id=state.run_id,
            thread_id=state.thread_id,
            owner_id=state.owner_id,
            action=state.action,
            arguments=state.arguments,
            reason="Creating a support case changes persistent business state.",
        )

    def start(
        self,
        *,
        run_id: str,
        thread_id: str,
        owner_id: str,
        order_id: str,
        reason: str,
    ) -> ApprovalRequest:
        if not run_id.strip() or not thread_id.strip() or not owner_id.strip():
            raise ValueError("run_id, thread_id, and owner_id must not be blank")
        arguments = validate_case_arguments({"order_id": order_id, "reason": reason})
        state = WorkflowState(
            run_id=run_id.strip(),
            thread_id=thread_id.strip(),
            owner_id=owner_id.strip(),
            phase="waiting_approval",
            action=CREATE_SUPPORT_CASE,
            arguments=arguments,
        )
        self.store.save(state)
        return self._request_from_state(state)

    def approval_request(self, run_id: str) -> ApprovalRequest:
        state = self.store.load(run_id)
        if state.phase != "waiting_approval":
            raise RuntimeError(f"run {run_id!r} is not waiting for approval")
        return self._request_from_state(state)

    def resume(
        self,
        run_id: str,
        decision: ApprovalDecision,
        *,
        reviewer: ReviewerContext,
    ) -> WorkflowState:
        state = self.store.load(run_id)
        if state.phase != "waiting_approval":
            return state

        request = self._request_from_state(state)
        authorize_reviewer(request, reviewer)
        resolved = resolve_case_arguments(state.arguments, decision)

        if resolved is None:
            rejected = WorkflowState(
                run_id=state.run_id,
                thread_id=state.thread_id,
                owner_id=state.owner_id,
                phase="rejected",
                action=state.action,
                arguments=state.arguments,
                result=None,
            )
            self.store.save(rejected)
            return rejected

        return self.store.complete_case_once(waiting_state=state, arguments=resolved)

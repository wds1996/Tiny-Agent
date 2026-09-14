from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Literal


MemoryKind = Literal["semantic", "episodic", "procedural"]


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    owner_id: str
    key: str
    value: dict[str, Any]
    kind: MemoryKind
    explicit_user_request: bool
    source_thread_id: str
    sensitive: bool = False


@dataclass(frozen=True, slots=True)
class MemoryDecision:
    store: bool
    reason: str


class ConservativeMemoryWritePolicy:
    def evaluate(self, candidate: MemoryCandidate) -> MemoryDecision:
        if not candidate.owner_id.strip() or not candidate.key.strip():
            return MemoryDecision(False, "owner_id and key are required")
        if not candidate.source_thread_id.strip():
            return MemoryDecision(False, "source_thread_id is required")
        if candidate.sensitive:
            return MemoryDecision(False, "sensitive data is not stored by this policy")
        if candidate.kind == "procedural":
            return MemoryDecision(False, "procedural self-rewrite requires stronger governance")
        if not candidate.explicit_user_request:
            return MemoryDecision(False, "incidental facts are not durable memory by default")
        return MemoryDecision(True, "explicit non-sensitive memory is allowed")


class SQLiteMemoryStore:
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
                CREATE TABLE IF NOT EXISTS memories (
                    owner_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    source_thread_id TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    PRIMARY KEY (owner_id, key)
                )
                """
            )

    def put(self, candidate: MemoryCandidate) -> None:
        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO memories(owner_id, key, kind, source_thread_id, value_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(owner_id, key) DO UPDATE SET
                    kind=excluded.kind,
                    source_thread_id=excluded.source_thread_id,
                    value_json=excluded.value_json
                """,
                (
                    candidate.owner_id,
                    candidate.key,
                    candidate.kind,
                    candidate.source_thread_id,
                    json.dumps(candidate.value, ensure_ascii=False, sort_keys=True),
                ),
            )

    def get(self, owner_id: str, key: str) -> dict[str, Any] | None:
        with self._session() as conn:
            row = conn.execute(
                "SELECT value_json FROM memories WHERE owner_id=? AND key=?",
                (owner_id, key),
            ).fetchone()
        return None if row is None else json.loads(row[0])

    def delete(self, owner_id: str, key: str) -> None:
        with self._session() as conn:
            conn.execute(
                "DELETE FROM memories WHERE owner_id=? AND key=?",
                (owner_id, key),
            )


def store_if_allowed(
    *,
    store: SQLiteMemoryStore,
    policy: ConservativeMemoryWritePolicy,
    candidate: MemoryCandidate,
) -> MemoryDecision:
    decision = policy.evaluate(candidate)
    if decision.store:
        store.put(candidate)
    return decision

"""Durable application state. One short transaction commits each work unit."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import json
import math
from pathlib import Path
import sqlite3
import time
import uuid

from domain import BoundaryError, Identity, digest, encode, text


class Store:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "application.db"
        with self.session() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, tenant TEXT, user TEXT,
                    status TEXT, phase TEXT, state TEXT, lease_token TEXT, lease_until REAL);
                CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, run_id TEXT UNIQUE,
                    payload TEXT, digest TEXT, status TEXT, reviewer TEXT, created REAL);
                CREATE TABLE IF NOT EXISTS charges(run_id TEXT, kind TEXT, count INTEGER, PRIMARY KEY(run_id,kind));
                CREATE TABLE IF NOT EXISTS preferences(tenant TEXT, user TEXT, language TEXT,
                    PRIMARY KEY(tenant,user));
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, run_id TEXT,
                    name TEXT, details TEXT);
            """)

    @contextmanager
    def session(self):
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            if conn.in_transaction:
                conn.commit()
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def create(self, identity: Identity, question: str, language: str) -> str:
        if identity.role != "customer":
            raise BoundaryError("customer_role_required")
        question = text(question, maximum=1800)
        if not isinstance(language, str) or language not in {"zh", "en"}:
            raise BoundaryError("invalid_language")
        run_id = uuid.uuid4().hex
        state = {"id": run_id, "identity": asdict(identity), "question": question,
                 "language": language, "phase": "plan", "status": "queued",
                 "model_calls": 0, "tool_calls": 0, "evidence": {}, "facts": {},
                 "preferences": self.preference(identity), "repairs": 0}
        with self.session() as c:
            c.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,NULL,NULL)",
                      (run_id, identity.tenant, identity.user, "queued", "plan", encode(state)))
        return run_id

    def get(self, run_id: str, identity: Identity) -> dict:
        with self.session() as c:
            row = c.execute("SELECT state,status,phase FROM runs WHERE id=? AND tenant=? AND user=?",
                            (run_id, identity.tenant, identity.user)).fetchone()
        if row is None:
            raise BoundaryError("run_not_accessible")
        return {**json.loads(row["state"]), "status": row["status"], "phase": row["phase"]}

    def claim(self, run_id: str, identity: Identity, *, seconds: float = 30) -> tuple[dict, str] | None:
        if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds) or seconds <= 0:
            raise BoundaryError("invalid_lease_duration")
        with self.session() as c:
            row = c.execute("SELECT * FROM runs WHERE id=? AND tenant=? AND user=?",
                            (run_id, identity.tenant, identity.user)).fetchone()
            if row is None:
                raise BoundaryError("run_not_accessible")
            now = time.time()
            if row["status"] not in {"queued", "running"}:
                return None
            if row["status"] == "running" and row["lease_until"] > now:
                raise BoundaryError("run_busy")
            token = uuid.uuid4().hex
            c.execute("UPDATE runs SET status='running',lease_token=?,lease_until=? WHERE id=?",
                      (token, now + seconds, run_id))
            return json.loads(row["state"]), token

    def _owner(self, c, run_id, token):
        row = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None or row["status"] != "running" or row["lease_token"] != token or row["lease_until"] <= time.time():
            raise BoundaryError("lease_lost")
        return row

    def heartbeat(self, run_id: str, token: str):
        with self.session() as c:
            self._owner(c, run_id, token)
            c.execute("UPDATE runs SET lease_until=? WHERE id=?", (time.time() + 30, run_id))

    def save(self, state: dict, token: str):
        with self.session() as c:
            self._owner(c, state["id"], token)
            approval = state.get("proposal")
            if state["status"] == "waiting_approval":
                payload = {"identity": state["identity"], "quote": approval,
                           "kind": "refund", "run_id": state["id"]}
                c.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,?)",
                          (state["id"], state["id"], encode(payload), digest(payload), "pending", None, time.time()))
                state["approval_digest"] = digest(payload)
            c.execute("UPDATE runs SET status=?,phase=?,state=?,lease_token=NULL,lease_until=NULL WHERE id=?",
                      (state["status"], state["phase"], encode(state), state["id"]))

    def consume(self, run_id: str, token: str, kind: str) -> int:
        limits = {'model': 20, 'tool': 24}
        if kind not in limits: raise BoundaryError('unknown_budget')
        with self.session() as c:
            self._owner(c,run_id,token)
            row=c.execute("SELECT count FROM charges WHERE run_id=? AND kind=?",(run_id,kind)).fetchone()
            count=0 if row is None else row[0]
            if count>=limits[kind]: raise BoundaryError(kind+'_budget_exhausted')
            c.execute("INSERT INTO charges VALUES(?,?,?) ON CONFLICT(run_id,kind) DO UPDATE SET count=excluded.count",(run_id,kind,count+1))
            return count+1

    def counts(self, run_id: str) -> dict:
        with self.session() as c:
            return {r[0]:r[1] for r in c.execute("SELECT kind,count FROM charges WHERE run_id=?",(run_id,))}

    def retry(self, run_id: str, identity: Identity):
        self.get(run_id,identity)
        with self.session() as c:
            row=c.execute("SELECT status FROM runs WHERE id=?",(run_id,)).fetchone()
            if row[0]!='failed': raise BoundaryError('only_failed_runs_can_retry')
            c.execute("UPDATE runs SET status='queued' WHERE id=?",(run_id,))
        # Counters intentionally remain charged across retries and crashes.

    def fail(self, state: dict, token: str, code: str):
        state.update(status="failed", error=code)
        self.save(state, token)

    def approval(self, run_id: str) -> dict:
        with self.session() as c:
            row = c.execute("SELECT * FROM approvals WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise BoundaryError("approval_missing")
        return {**dict(row), "payload": json.loads(row["payload"])}

    def approval_for(self, run_id: str, reviewer: Identity) -> dict:
        if reviewer.role != "reviewer":
            raise BoundaryError("reviewer_role_required")
        record = self.approval(run_id)
        owner = record["payload"]["identity"]
        if owner["tenant"] != reviewer.tenant or owner["user"] == reviewer.user:
            raise BoundaryError("approval_not_accessible")
        return record

    def review(self, run_id: str, reviewer: Identity, expected_digest: str, *, approve: bool):
        if type(approve) is not bool:
            raise BoundaryError("invalid_approval_decision")
        if reviewer.role != "reviewer":
            raise BoundaryError("reviewer_role_required")
        with self.session() as c:
            row = c.execute("SELECT * FROM approvals WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise BoundaryError("approval_missing")
            payload = json.loads(row["payload"])
            if payload["identity"]["tenant"] != reviewer.tenant or payload["identity"]["user"] == reviewer.user:
                raise BoundaryError("reviewer_scope_denied")
            if row["digest"] != expected_digest or digest(payload) != expected_digest:
                raise BoundaryError("approval_digest_mismatch")
            if row["status"] != "pending":
                raise BoundaryError("approval_already_decided")
            if time.time() - row["created"] > 900:
                raise BoundaryError("approval_expired")
            c.execute("UPDATE approvals SET status=?,reviewer=? WHERE id=?",
                      ("approved" if approve else "rejected", encode(asdict(reviewer)), run_id))
            old = c.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
            state = json.loads(old[0])
            state.update(status="queued" if approve else "rejected", phase="settle" if approve else "done")
            c.execute("UPDATE runs SET status=?,phase=?,state=? WHERE id=?",
                      (state["status"], state["phase"], encode(state), run_id))

    def remember(self, identity: Identity, language: str, *, consent: bool):
        if not consent or language not in {"zh", "en"}:
            raise BoundaryError("explicit_language_consent_required")
        with self.session() as c:
            c.execute("INSERT INTO preferences VALUES(?,?,?) ON CONFLICT(tenant,user) DO UPDATE SET language=excluded.language",
                      (identity.tenant, identity.user, language))

    def preference(self, identity: Identity) -> dict:
        with self.session() as c:
            row = c.execute("SELECT language FROM preferences WHERE tenant=? AND user=?", (identity.tenant, identity.user)).fetchone()
        return {} if row is None else {"language": row[0]}

    def event(self, run_id: str, name: str, **details):
        # Call sites supply fixed names and counters, never raw questions or responses.
        safe = {k: v for k, v in details.items() if k in {"phase", "tool", "status", "count", "model_calls", "tool_calls", "duration_ms", "error", "input_tokens", "output_tokens"}}
        with self.session() as c:
            c.execute("INSERT INTO events(run_id,name,details) VALUES(?,?,?)", (run_id, name, encode(safe)))

    def events(self, run_id: str, identity: Identity) -> list[dict]:
        self.get(run_id, identity)
        with self.session() as c:
            return [{"name": r[0], **json.loads(r[1])} for r in c.execute("SELECT name,details FROM events WHERE run_id=? ORDER BY id", (run_id,))]

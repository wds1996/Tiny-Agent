from pathlib import Path

import pytest

from tiny_agent.jobs import SQLiteRunQueue


def test_sqlite_run_queue_survives_recreation_and_enforces_lease_owner(tmp_path: Path) -> None:
    path = tmp_path / "runs.sqlite"
    first = SQLiteRunQueue(path)
    run_id = first.enqueue({"question": "hello"})

    second = SQLiteRunQueue(path)
    claimed = second.claim(worker_id="worker-a", lease_seconds=30)
    assert claimed is not None and claimed.run_id == run_id
    assert claimed.status == "running"

    with pytest.raises(RuntimeError):
        second.complete(run_id, worker_id="worker-b", result={"answer": "bad"})

    second.complete(run_id, worker_id="worker-a", result={"answer": "ok"})
    completed = SQLiteRunQueue(path).get(run_id)
    assert completed.status == "completed"
    assert completed.result == {"answer": "ok"}

from pathlib import Path
from tempfile import TemporaryDirectory

from tiny_agent.jobs import SQLiteRunQueue


with TemporaryDirectory() as tmp:
    database = Path(tmp) / "runs.sqlite"

    api_process = SQLiteRunQueue(database)
    run_id = api_process.enqueue({"question": "Prepare a research brief"})
    print("202 Accepted", {"run_id": run_id})

    # A different process/runtime object can claim the same durable job.
    worker = SQLiteRunQueue(database)
    job = worker.claim(worker_id="worker-1", lease_seconds=30)
    assert job is not None
    print("claimed:", job)

    worker.complete(job.run_id, worker_id="worker-1", result={"answer": "done"})
    print("terminal:", SQLiteRunQueue(database).get(job.run_id))

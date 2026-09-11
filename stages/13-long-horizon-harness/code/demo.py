"""Use real child processes to recover one report from two deliberate crashes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from ledger import TaskLedger
from report import STEP_NAMES


WORKER = Path(__file__).with_name("worker.py")


def run_worker(db: Path, command: str, *args: str, expected: int = 0) -> str:
    completed = subprocess.run(
        [sys.executable, str(WORKER), command, "--db", str(db), *args],
        text=True, encoding="utf-8", capture_output=True, timeout=15,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    if completed.returncode != expected:
        raise RuntimeError(f"worker exited {completed.returncode}: {completed.stderr}")
    return completed.stdout


def demonstrate(db: Path) -> None:
    run_worker(db, "create")
    ledger = TaskLedger(db)
    print("Created report-001. Required sections: Background, Risks, Recommendation.")
    first = run_worker(db, "work", "--worker-id", "alice",
                       "--crash", "after-commit", expected=23)
    first_result = json.JSONDecoder().raw_decode(first)[0]
    print(f"Worker PID {first_result['pid']} exited AFTER committing draft.")
    saved = ledger.get("report-001")
    assert saved.step_index == 1 and len(ledger.step_outputs(saved.task_id)) == 1
    print("Database: queued, next=verify; the draft is still present.")

    run_worker(db, "work", "--worker-id", "bob", "--lease-seconds", "0.6",
               "--crash", "after-compute", expected=23)
    saved = ledger.get("report-001")
    assert saved.status == "running" and saved.step_index == 1
    assert len(ledger.step_outputs(saved.task_id)) == 1
    print("Another worker exited BEFORE committing verify; no verdict was saved.")
    time.sleep(max(0, saved.lease_until - time.time()) + 0.05)

    for number in range(8):
        output = run_worker(db, "work", "--worker-id", f"replacement-{number}")
        row = json.loads(output)
        task = ledger.get("report-001")
        next_step = "END" if task.status == "completed" else STEP_NAMES[task.step_index]
        print(f"PID {row['pid']}: {row.get('executed', 'no work')} -> "
              f"{task.status}, next={next_step}, repairs={task.repair_count}")
        if task.status in {"completed", "failed"}:
            break
    assert task.status == "completed"
    assert task.claim_count == 6 and task.repair_count == 1
    assert len(ledger.step_outputs(task.task_id)) == 5
    print("\nCommitted history:")
    for item in ledger.step_outputs(task.task_id):
        print(f"  revision={item['repair_count']} step={STEP_NAMES[item['step_index']]} "
              f"worker={item['worker_id']}")
    print("\nArtifact read from the database:\n" + ledger.artifact(task.task_id))


def main() -> None:
    # Only the automatic demo is temporary. worker.py leaves its database in place.
    with tempfile.TemporaryDirectory() as directory:
        demonstrate(Path(directory) / "ledger.db")


if __name__ == "__main__":
    main()

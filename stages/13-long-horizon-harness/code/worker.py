"""Persist a report task, work once in this process, inspect it or export it."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from harness import LongHorizonHarness
from ledger import TaskLedger
from report import LIVE_WORKFLOW, OFFLINE_WORKFLOW, STEP_NAMES, offline_steps, report_inputs


def show(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)


def parser(default_mode: str) -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=("create", "work", "inspect", "export"))
    result.add_argument("--db", default="stage13-report.db")
    result.add_argument("--task-id", default="report-001")
    result.add_argument("--worker-id", default=f"worker-{os.getpid()}")
    result.add_argument("--mode", choices=("offline", "deepseek"), default=default_mode)
    result.add_argument("--max-repairs", type=int, default=1)
    result.add_argument("--max-claims", type=int, default=12)
    result.add_argument("--lease-seconds", type=float, default=10)
    result.add_argument("--max-unit-seconds", type=float, default=120)
    result.add_argument("--output", default="stage13-report.md")
    result.add_argument("--crash", choices=("after-compute", "after-commit"),
                        help="offline fault injection; deliberately exits with code 23")
    return result


def main(default_mode: str = "offline") -> None:
    args = parser(default_mode).parse_args()
    db = Path(args.db)
    if args.command != "create" and not db.is_file():
        raise ValueError("database not found; create the task first and reuse the same --db")
    ledger = TaskLedger(db)
    if args.command == "create":
        inputs = report_inputs()
        workflow = OFFLINE_WORKFLOW
        if args.mode == "deepseek":
            from deepseek_long_horizon import required_env
            inputs["model"] = required_env("DEEPSEEK_MODEL")
            workflow = LIVE_WORKFLOW
        task = ledger.create_task(task_id=args.task_id, workflow=workflow, inputs=inputs,
                                  max_repairs=args.max_repairs, max_claims=args.max_claims)
        show({"database": str(db.resolve()), "task_id": task.task_id, "status": task.status})
        return
    if args.command == "inspect":
        show({"task": asdict(ledger.get(args.task_id)),
              "history": ledger.step_outputs(args.task_id)})
        return
    if args.command == "export":
        text = ledger.artifact(args.task_id)
        # The path is a trusted CLI argument, never a model-supplied destination.
        with Path(args.output).open("x", encoding="utf-8") as destination:
            destination.write(text)
        show({"exported": str(Path(args.output).resolve())})
        return

    saved = ledger.get(args.task_id)
    if saved.status in {"completed", "failed"}:
        show({"worked": False, "status": saved.status})
        return
    client = None
    if saved.workflow == OFFLINE_WORKFLOW:
        steps = list(offline_steps())
    elif saved.workflow == LIVE_WORKFLOW:
        if args.crash:
            raise ValueError("fault injection is only available for offline tasks")
        from deepseek_long_horizon import DeepSeekWorkUnits, create_client
        client = create_client()
        units = DeepSeekWorkUnits(client=client)
        steps = [units.draft, units.verify, units.finalize]
    else:
        raise ValueError("unknown workflow version; do not reinterpret a saved step index")
    if args.crash == "after-compute":
        original = steps[saved.step_index]
        def interrupted(inputs, progress):
            original(inputs, progress)
            print("CRASH: computed output was not committed", flush=True)
            os._exit(23)  # Only this explicitly launched teaching subprocess exits.
        steps[saved.step_index] = interrupted
    try:
        harness = LongHorizonHarness(ledger, steps, workflow=saved.workflow,
                                     lease_seconds=args.lease_seconds,
                                     max_unit_seconds=args.max_unit_seconds)
        result = harness.work_once(args.task_id, worker_id=args.worker_id)
        if result is None:
            show({"worked": False, "status": ledger.get(args.task_id).status})
        else:
            show({"pid": os.getpid(), "worker": args.worker_id,
                  "executed": STEP_NAMES[result.executed_step],
                  "status": result.task.status, "next_step_index": result.task.step_index,
                  "repair_count": result.task.repair_count,
                  "claim_count": result.task.claim_count, "output": result.output.data})
            if args.crash == "after-commit":
                print("CRASH: committed output remains in the database", flush=True)
                os._exit(23)
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

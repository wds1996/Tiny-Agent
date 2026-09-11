"""Offline boundary checks, including real process exits and transaction failure."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

from deepseek_long_horizon import DeepSeekWorkUnits
from demo import demonstrate, run_worker
from harness import LeaseKeeper, LongHorizonHarness, UnitDeadlineExceeded
from ledger import LeaseError, StepResult, TaskLedger
from report import (OFFLINE_WORKFLOW, draft_digest, finalize, offline_draft,
                    offline_steps, report_inputs, review_result)


class Clock:
    value = 100.0
    def __call__(self):
        return self.value


class LedgerChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ledger.db"
        self.clock = Clock()
        self.ledger = TaskLedger(self.path, clock=self.clock)
        self.ledger.create_task(task_id="report", workflow="test-v1", inputs={"goal": "demo"})

    def claim(self, owner="a"):
        return self.ledger.claim("report", worker_id=owner, workflow="test-v1", lease_seconds=5)

    def test_inputs_survive_new_ledger(self):
        self.assertEqual(TaskLedger(self.path).get("report").inputs, {"goal": "demo"})

    def test_duplicate_creation_never_resets_progress(self):
        self.ledger.commit_step(self.claim(), StepResult({"draft": "saved"}))
        with self.assertRaises(sqlite3.IntegrityError):
            self.ledger.create_task(task_id="report", workflow="test-v1", inputs={})
        self.assertEqual(self.ledger.get("report").step_index, 1)

    def test_claims_are_exclusive(self):
        self.claim()
        self.assertIsNone(self.claim("b"))

    def test_competing_connections_obtain_only_one_claim(self):
        barrier = threading.Barrier(2)
        def compete(owner):
            ledger = TaskLedger(self.path, clock=self.clock)
            barrier.wait(timeout=3)
            return ledger.claim("report", worker_id=owner, workflow="test-v1", lease_seconds=5)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(compete, ("a", "b")))
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_expiry_is_inclusive(self):
        self.claim()
        self.clock.value = 104
        self.assertIsNone(self.claim("b"))
        self.clock.value = 105
        self.assertEqual(self.claim("b").lease_owner, "b")

    def test_old_token_rejected_even_when_worker_name_is_reused(self):
        old = self.claim()
        self.clock.value = 105
        new = self.claim()
        self.assertNotEqual(old.lease_token, new.lease_token)
        with self.assertRaises(LeaseError):
            self.ledger.commit_step(old, StepResult({"stale": True}))
        with self.assertRaises(LeaseError):
            self.ledger.heartbeat(old, lease_seconds=5)
        self.ledger.commit_step(new, StepResult({"current": True}))

    def test_expired_claim_cannot_commit_without_a_replacement(self):
        old = self.claim()
        self.clock.value = 105
        with self.assertRaises(LeaseError):
            self.ledger.commit_step(old, StepResult({}))
        self.assertEqual(self.ledger.step_outputs("report"), ())

    def test_other_worker_cannot_renew(self):
        old = self.claim()
        with self.assertRaises(LeaseError):
            self.ledger.heartbeat(replace(old, lease_owner="b"), lease_seconds=5)

    def test_heartbeat_extends_lease(self):
        old = self.claim()
        self.clock.value = 104
        self.ledger.heartbeat(old, lease_seconds=5)
        self.clock.value = 106
        self.assertIsNone(self.claim("b"))
        self.ledger.commit_step(old, StepResult({}))

    def test_committed_claim_cannot_commit_twice(self):
        old = self.claim()
        self.ledger.commit_step(old, StepResult({"x": 1}))
        with self.assertRaises(LeaseError):
            self.ledger.commit_step(old, StepResult({"x": 2}))
        self.assertEqual(len(self.ledger.step_outputs("report")), 1)

    def test_wrong_step_snapshot_is_rejected(self):
        old = self.claim()
        with self.assertRaises(LeaseError):
            self.ledger.commit_step(replace(old, step_index=1), StepResult({}))

    def test_old_workflow_version_does_not_claim(self):
        with self.assertRaises(ValueError):
            self.ledger.claim("report", worker_id="a", workflow="test-v2", lease_seconds=5)
        self.assertEqual(self.ledger.get("report").claim_count, 0)

    def test_invalid_duration_does_not_claim(self):
        for duration in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                self.ledger.claim("report", worker_id="a", workflow="test-v1", lease_seconds=duration)

    def test_output_and_state_roll_back_together(self):
        old = self.claim()
        with sqlite3.connect(self.path) as conn:
            conn.execute("""
                CREATE TRIGGER refuse_progress BEFORE UPDATE OF progress_json ON tasks
                BEGIN SELECT RAISE(ABORT, 'injected failure after output insert'); END
            """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.ledger.commit_step(old, StepResult({"draft": "not committed"}))
        self.assertEqual(self.ledger.step_outputs("report"), ())
        self.assertEqual(self.ledger.get("report").step_index, 0)

    def test_process_death_inside_commit_leaves_no_half_result(self):
        # The SQL trigger exits the child after INSERT history but before UPDATE tasks.
        script = '''
from contextlib import contextmanager
import os, sys
from ledger import TaskLedger, StepResult
class CrashingLedger(TaskLedger):
    @contextmanager
    def _session(self, **kwargs):
        with super()._session(**kwargs) as conn:
            conn.create_function("crash_now", 0, lambda: os._exit(23))
            yield conn
ledger = CrashingLedger(sys.argv[1], clock=lambda: 100)
claim = ledger.claim("report", worker_id="crasher", workflow="test-v1", lease_seconds=5)
with ledger._session(write=True) as conn:
    conn.execute("CREATE TRIGGER crash_commit BEFORE UPDATE OF progress_json ON tasks "
                 "BEGIN SELECT crash_now(); END")
ledger.commit_step(claim, StepResult({"draft":"unfinished transaction"}))
'''
        child = subprocess.run([sys.executable, "-c", script, str(self.path)],
                               cwd=Path(__file__).parent, timeout=10, capture_output=True)
        self.assertEqual(child.returncode, 23, child.stderr)
        self.assertEqual(self.ledger.step_outputs("report"), ())
        self.assertEqual(self.ledger.get("report").progress, {})
        self.assertEqual(self.ledger.get("report").status, "running")

    def test_invalid_repair_and_non_json_output_change_nothing(self):
        old = self.claim()
        for output in (StepResult({}, restart_step=2), StepResult({}, restart_step=True),
                       StepResult({"bad": float("nan")}), StepResult({"bad": object()})):
            with self.subTest(output=output), self.assertRaises((ValueError, TypeError)):
                self.ledger.commit_step(old, output)
        self.assertEqual(self.ledger.step_outputs("report"), ())

    def test_repair_budget_is_durable(self):
        self.ledger.commit_step(self.claim(), StepResult({"feedback": "missing Risks"}, restart_step=0))
        self.assertEqual(TaskLedger(self.path).get("report").repair_count, 1)
        failed = self.ledger.commit_step(self.claim(), StepResult({"feedback": "still bad"}, restart_step=0))
        self.assertEqual(failed.failure, "repair budget exhausted")
        self.assertIsNone(self.claim())
        self.assertEqual(len(self.ledger.step_outputs("report")), 2)

    def test_crash_retries_have_a_separate_claim_budget(self):
        self.ledger.create_task(task_id="limited", workflow="test-v1", inputs={}, max_claims=1)
        self.ledger.claim("limited", worker_id="a", workflow="test-v1", lease_seconds=5)
        self.clock.value = 105
        self.assertIsNone(self.ledger.claim("limited", worker_id="b", workflow="test-v1", lease_seconds=5))
        failed = self.ledger.get("limited")
        self.assertEqual(failed.failure, "claim budget exhausted")
        self.assertEqual(failed.repair_count, 0)

    def test_early_artifact_is_rejected(self):
        with self.assertRaises(ValueError):
            self.ledger.commit_step(self.claim(), StepResult({}, artifact="too early"))

    def test_old_database_is_not_silently_migrated_or_deleted(self):
        path = Path(self.tmp.name) / "old.db"
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE tasks(old_data TEXT)")
            conn.execute("INSERT INTO tasks VALUES ('keep me')")
        with self.assertRaises(RuntimeError):
            TaskLedger(path)
        with sqlite3.connect(path) as conn:
            self.assertEqual(conn.execute("SELECT * FROM tasks").fetchone(), ("keep me",))


class HarnessAndReportChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "report.db"
        self.ledger = TaskLedger(self.path)
        self.ledger.create_task(task_id="report", workflow=OFFLINE_WORKFLOW, inputs=report_inputs())
        self.harness = LongHorizonHarness(self.ledger, offline_steps(), workflow=OFFLINE_WORKFLOW)

    def test_five_committed_steps_and_both_drafts_survive(self):
        for number in range(5):
            self.harness.work_once("report", worker_id=f"worker-{number}")
        task = self.ledger.get("report")
        history = self.ledger.step_outputs("report")
        self.assertEqual([row["step_index"] for row in history], [0, 1, 0, 1, 2])
        self.assertEqual([row["repair_count"] for row in history], [0, 0, 1, 1, 1])
        self.assertNotIn("Risks", history[0]["output"]["draft"])
        self.assertIn("Risks", history[2]["output"]["draft"])
        self.assertNotIn("restart_step", task.progress)
        self.assertEqual(task.status, "completed")
        self.assertIn("## Risks", TaskLedger(self.path).artifact("report"))
        self.assertIsNone(self.harness.work_once("report", worker_id="late"))

    def test_step_failure_does_not_advance_or_consume_repair_budget(self):
        def fail(inputs, progress):
            raise TimeoutError("provider unavailable")
        harness = LongHorizonHarness(self.ledger, [fail] * 3, workflow=OFFLINE_WORKFLOW)
        with self.assertRaises(TimeoutError):
            harness.work_once("report", worker_id="a")
        task = self.ledger.get("report")
        self.assertEqual((task.status, task.step_index, task.repair_count), ("running", 0, 0))
        self.assertEqual(self.ledger.step_outputs("report"), ())

    def test_clock_is_checked_again_after_step_execution(self):
        clock = Clock()
        self.ledger.clock = clock
        def slow(inputs, progress):
            clock.value = 106
            return StepResult({"late": True})
        harness = LongHorizonHarness(self.ledger, [slow] * 3,
                                     workflow=OFFLINE_WORKFLOW, lease_seconds=5)
        with self.assertRaises(LeaseError):
            harness.work_once("report", worker_id="a")
        self.assertEqual(self.ledger.step_outputs("report"), ())

    def test_real_heartbeat_keeps_a_longer_step_alive(self):
        ready = threading.Event()
        original = self.ledger.heartbeat
        count = 0
        def heartbeat(*args, **kwargs):
            nonlocal count
            original(*args, **kwargs)
            count += 1
            if count == 4:
                ready.set()
        self.ledger.heartbeat = heartbeat
        def wait_for_renewal(inputs, progress):
            if not ready.wait(5):
                raise RuntimeError("heartbeat did not run")
            return StepResult({"renewed": True})
        harness = LongHorizonHarness(self.ledger, [wait_for_renewal] * 3,
                                     workflow=OFFLINE_WORKFLOW, lease_seconds=0.6,
                                     max_unit_seconds=5)
        result = harness.work_once("report", worker_id="a")
        self.assertTrue(result.task.progress["renewed"])
        self.assertGreaterEqual(count, 4)

    def test_deadline_is_not_extended_by_heartbeat(self):
        claim = self.ledger.claim("report", worker_id="a", workflow=OFFLINE_WORKFLOW)
        elapsed = Clock()
        guard = LeaseKeeper(self.ledger, claim, lease_seconds=10, max_unit_seconds=2, monotonic=elapsed)
        elapsed.value = 102
        with self.assertRaises(UnitDeadlineExceeded):
            guard.check()

    def test_renewal_failure_discards_result(self):
        done = threading.Event()
        def broken(*args, **kwargs):
            done.set()
            raise sqlite3.OperationalError("storage unavailable")
        self.ledger.heartbeat = broken
        def slow(inputs, progress):
            self.assertTrue(done.wait(3))
            return StepResult({"must_not_commit": True})
        harness = LongHorizonHarness(self.ledger, [slow] * 3,
                                     workflow=OFFLINE_WORKFLOW, lease_seconds=0.3)
        with self.assertRaises(LeaseError):
            harness.work_once("report", worker_id="a")
        self.assertEqual(self.ledger.step_outputs("report"), ())

    def test_step_count_mismatch_rejected_before_claim(self):
        harness = LongHorizonHarness(self.ledger, [offline_draft], workflow=OFFLINE_WORKFLOW)
        with self.assertRaises(ValueError):
            harness.work_once("report", worker_id="a")
        self.assertEqual(self.ledger.get("report").claim_count, 0)

    def test_report_cannot_publish_a_draft_changed_after_review(self):
        inputs = report_inputs()
        draft = {name: "some text" for name in inputs["sections"]}
        progress = {"draft": draft, "review": {"ok": True}, "reviewed_digest": draft_digest(draft)}
        draft["Risks"] = "changed after review"
        with self.assertRaises(ValueError):
            finalize(inputs, progress)

    def test_model_pass_cannot_override_missing_sections(self):
        inputs = report_inputs()
        progress = offline_draft(inputs, {}).data
        output = review_result(inputs, progress, {"ok": True, "feedback": "looks good"})
        self.assertEqual(output.restart_step, 0)
        self.assertIn("Risks", output.data["feedback"])

    def test_artifact_and_completion_roll_back_together(self):
        for _ in range(4):
            self.harness.work_once("report", worker_id="a")
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TRIGGER refuse_final BEFORE UPDATE OF progress_json ON tasks "
                         "BEGIN SELECT RAISE(ABORT, 'injected final failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.harness.work_once("report", worker_id="a")
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0], 0)
        self.assertEqual(len(self.ledger.step_outputs("report")), 4)
        self.assertEqual(self.ledger.get("report").step_index, 2)

    def test_corrupted_artifact_is_detected(self):
        for _ in range(5):
            self.harness.work_once("report", worker_id="a")
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE artifacts SET content='changed'")
        with self.assertRaises(ValueError):
            self.ledger.artifact("report")

    def test_actual_process_crashes_and_recovery(self):
        demonstrate(Path(self.tmp.name) / "processes.db")

    def test_export_does_not_overwrite_existing_file(self):
        db = Path(self.tmp.name) / "export.db"
        run_worker(db, "create")
        for _ in range(5):
            run_worker(db, "work")
        output = Path(self.tmp.name) / "existing.md"
        output.write_text("keep", encoding="utf-8")
        run_worker(db, "export", "--output", str(output), expected=1)
        self.assertEqual(output.read_text(encoding="utf-8"), "keep")


class ModelChecks(unittest.TestCase):
    def client(self, texts):
        self.requests = []
        outputs = iter(texts)
        def create(**kwargs):
            self.requests.append(kwargs)
            text, reason = next(outputs)
            return SimpleNamespace(choices=[SimpleNamespace(
                finish_reason=reason, message=SimpleNamespace(content=text))])
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    def test_new_model_instance_receives_saved_task_draft_and_feedback(self):
        inputs = {**report_inputs(), "model": "test-model"}
        progress = {"draft": {"Background": "earlier"}, "feedback": "add Risks"}
        units = DeepSeekWorkUnits(client=self.client([('{"Background":"new"}', "stop")]))
        units.draft(inputs, progress)
        request = self.requests[0]
        payload = json.loads(request["messages"][1]["content"])
        self.assertEqual(payload["previous_draft"], progress["draft"])
        self.assertEqual(payload["feedback"], "add Risks")
        self.assertEqual(payload["facts"], inputs["facts"])
        self.assertEqual(request["model"], "test-model")
        self.assertNotIn("lease_token", payload)

    def test_model_workflow_can_resume_with_fresh_units(self):
        inputs = {**report_inputs(), "model": "test-model"}
        draft0 = {"Background": "20 support staff.", "Recommendation": "Human review."}
        draft1 = {**draft0, "Risks": "回复可能有误，必须核对。"}
        client = self.client([(json.dumps(draft0), "stop"),
                              ('{"ok":true,"feedback":"pass"}', "stop"),
                              (json.dumps(draft1), "stop"),
                              ('{"ok":true,"feedback":"pass"}', "stop")])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "live.db"
            TaskLedger(path).create_task(task_id="live", workflow="model-v1", inputs=inputs)
            for turn in range(5):
                units = DeepSeekWorkUnits(client=client)
                harness = LongHorizonHarness(TaskLedger(path),
                    [units.draft, units.verify, units.finalize], workflow="model-v1")
                harness.work_once("live", worker_id=str(turn))
            ledger = TaskLedger(path)
            self.assertEqual(ledger.get("live").repair_count, 1)
            self.assertIn("必须核对", ledger.artifact("live"))
            self.assertEqual(len(self.requests), 4)

    def test_truncated_empty_and_invalid_json_fail_closed(self):
        for text, reason in (("{}", "length"), ("", "stop"), ("[]", "stop"),
                             ("not json", "stop"), ('{"x":NaN}', "stop")):
            with self.subTest(text=text):
                units = DeepSeekWorkUnits(client=self.client([(text, reason)]))
                with self.assertRaises(RuntimeError):
                    units._ask(model="test", instructions="json", payload={})

    def test_verdict_schema_rejects_string_boolean_and_extra_commands(self):
        inputs = {**report_inputs(), "model": "test-model"}
        for verdict in ({"ok": "true", "feedback": "pass"},
                        {"ok": True, "feedback": "pass", "restart_step": 2},
                        {"ok": False, "feedback": ""}):
            with self.subTest(verdict=verdict):
                units = DeepSeekWorkUnits(client=self.client([(json.dumps(verdict), "stop")]))
                with self.assertRaises(ValueError):
                    units.verify(inputs, offline_draft(inputs, {}).data)


if __name__ == "__main__":
    unittest.main(verbosity=2)

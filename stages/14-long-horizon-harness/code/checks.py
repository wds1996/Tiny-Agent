from pathlib import Path
import tempfile
import unittest

from harness import LongHorizonHarness
from ledger import LeaseError, TaskLedger


class Stage14Checks(unittest.TestCase):
    def test_expired_lease_can_be_reclaimed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = TaskLedger(Path(tmp) / "x.db")
            task = ledger.create_task(total_steps=1)
            first = ledger.claim(worker_id="a", lease_seconds=5, now=100)
            self.assertEqual(first.task_id, task.task_id)
            second = ledger.claim(worker_id="b", lease_seconds=5, now=106)
            self.assertEqual(second.lease_owner, "b")

    def test_unexpired_lease_cannot_be_stolen(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = TaskLedger(Path(tmp) / "x.db")
            ledger.create_task(total_steps=1)
            ledger.claim(worker_id="a", lease_seconds=5, now=100)
            self.assertIsNone(ledger.claim(worker_id="b", lease_seconds=5, now=104))

    def test_heartbeat_requires_lease_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = TaskLedger(Path(tmp) / "x.db")
            task = ledger.create_task(total_steps=1)
            ledger.claim(worker_id="a", lease_seconds=5, now=100)
            with self.assertRaises(LeaseError):
                ledger.heartbeat(task.task_id, worker_id="b", lease_seconds=5, now=101)

    def test_step_output_is_durable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.db"
            ledger = TaskLedger(path)
            task = ledger.create_task(total_steps=1)
            ledger.claim(worker_id="a", lease_seconds=5, now=100)
            ledger.record_step_output(task.task_id, worker_id="a", step_index=0, output={"x": 1})
            self.assertEqual(TaskLedger(path).step_output(task.task_id, 0), {"x": 1})

    def test_each_work_unit_advances_one_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = TaskLedger(Path(tmp) / "x.db")
            ledger.create_task(total_steps=2)
            harness = LongHorizonHarness(ledger, [lambda p: {"a": 1}, lambda p: {"b": 2}])
            first = harness.work_once(worker_id="a", now=100)
            self.assertEqual(first.task.step_index, 1)
            self.assertEqual(first.task.status, "queued")
            second = harness.work_once(worker_id="b", now=101)
            self.assertEqual(second.task.status, "completed")

    def test_repair_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = TaskLedger(Path(tmp) / "x.db")
            ledger.create_task(total_steps=1, max_repairs=1)
            def bad(progress):
                return {"needs_repair": True, "restart_step": 0}
            harness = LongHorizonHarness(ledger, [bad])
            first = harness.work_once(worker_id="a", now=100)
            self.assertEqual(first.task.repair_count, 1)
            with self.assertRaises(RuntimeError):
                harness.work_once(worker_id="b", now=101)

    def test_progress_survives_harness_recreation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.db"
            ledger = TaskLedger(path)
            task = ledger.create_task(total_steps=2)
            LongHorizonHarness(ledger, [lambda p: {"a": 1}, lambda p: {"b": 2}]).work_once(worker_id="a", now=100)
            self.assertEqual(TaskLedger(path).get(task.task_id).progress["a"], 1)

    def test_completed_task_is_not_reclaimed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = TaskLedger(Path(tmp) / "x.db")
            ledger.create_task(total_steps=1)
            LongHorizonHarness(ledger, [lambda p: {"done": True}]).work_once(worker_id="a", now=100)
            self.assertIsNone(ledger.claim(worker_id="b", lease_seconds=5, now=200))


if __name__ == "__main__":
    unittest.main(verbosity=2)

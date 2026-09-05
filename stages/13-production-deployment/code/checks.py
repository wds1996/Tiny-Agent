from pathlib import Path
import tempfile
import unittest

from service import AgentService, BackpressureError, RunStore, TrustedIdentity


class Stage13Checks(unittest.TestCase):
    def make(self, tmp, *, max_queued=2):
        return AgentService(RunStore(Path(tmp) / "runs.db"), max_queued_per_tenant=max_queued)

    def test_identity_is_supplied_separately_from_request_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self.make(tmp)
            run = service.submit(
                identity=TrustedIdentity("alice", "tenant-a"),
                thread_id="t1", input_text='{"tenant_id":"evil"}',
            )
            self.assertEqual(run.tenant_id, "tenant-a")

    def test_request_idempotency_returns_same_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self.make(tmp)
            identity = TrustedIdentity("alice", "tenant-a")
            first = service.submit(identity=identity, thread_id="t1", input_text="hello", idempotency_key="k1")
            second = service.submit(identity=identity, thread_id="t1", input_text="hello", idempotency_key="k1")
            self.assertEqual(first.run_id, second.run_id)

    def test_idempotency_key_is_tenant_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self.make(tmp)
            a = service.submit(identity=TrustedIdentity("a", "tenant-a"), thread_id="t", input_text="x", idempotency_key="same")
            b = service.submit(identity=TrustedIdentity("b", "tenant-b"), thread_id="t", input_text="x", idempotency_key="same")
            self.assertNotEqual(a.run_id, b.run_id)

    def test_backpressure_is_per_tenant(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self.make(tmp, max_queued=1)
            identity = TrustedIdentity("a", "tenant-a")
            service.submit(identity=identity, thread_id="t1", input_text="one")
            with self.assertRaises(BackpressureError):
                service.submit(identity=identity, thread_id="t2", input_text="two")
            other = service.submit(identity=TrustedIdentity("b", "tenant-b"), thread_id="t3", input_text="three")
            self.assertEqual(other.tenant_id, "tenant-b")

    def test_cross_tenant_run_lookup_is_denied_by_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self.make(tmp)
            run = service.submit(identity=TrustedIdentity("a", "tenant-a"), thread_id="t", input_text="x")
            with self.assertRaises(KeyError):
                service.store.get(identity=TrustedIdentity("b", "tenant-b"), run_id=run.run_id)

    def test_run_survives_service_recreation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.db"
            identity = TrustedIdentity("a", "tenant-a")
            run = AgentService(RunStore(path)).submit(identity=identity, thread_id="t", input_text="x")
            recreated = AgentService(RunStore(path))
            self.assertEqual(recreated.store.get(identity=identity, run_id=run.run_id).status, "queued")

    def test_worker_transitions_queued_running_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = self.make(tmp)
            identity = TrustedIdentity("a", "tenant-a")
            run = service.submit(identity=identity, thread_id="t", input_text="x")
            completed = service.run_one()
            self.assertEqual(completed.run_id, run.run_id)
            self.assertEqual(completed.status, "completed")

    def test_readiness_checks_durable_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(self.make(tmp).store.ready())


if __name__ == "__main__":
    unittest.main(verbosity=2)

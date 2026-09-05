from pathlib import Path
import tempfile

from service import AgentService, RunStore, TrustedIdentity


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "runs.db"
        service = AgentService(RunStore(path), max_queued_per_tenant=2)
        identity = TrustedIdentity(user_id="alice", tenant_id="acme")
        run = service.submit(
            identity=identity, thread_id="support-42",
            input_text="Summarize ORDER-42.", idempotency_key="request-123",
        )
        same = service.submit(
            identity=identity, thread_id="support-42",
            input_text="Summarize ORDER-42.", idempotency_key="request-123",
        )
        print("same run:", run.run_id == same.run_id)
        print("queued:", run)
        print("completed:", service.run_one())
        restarted = AgentService(RunStore(path))
        print("after restart:", restarted.store.get(identity=identity, run_id=run.run_id))


if __name__ == "__main__":
    main()

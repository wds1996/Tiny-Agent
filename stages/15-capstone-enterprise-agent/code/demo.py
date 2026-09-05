from pathlib import Path
import tempfile

from agent import ApprovalDecision, SupportAgent
from domain import TrustedIdentity
from store import SupportStore


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = SupportStore(Path(tmp) / "support.db")
        agent = SupportAgent(store)
        identity = TrustedIdentity(tenant_id="acme", user_id="alice")

        answer = agent.run(
            identity=identity,
            question="Can ORDER-42 be refunded to the original payment method?",
        )
        print("question result:", answer.status)
        print(answer.answer)
        print("trace:", answer.trace)

        proposed = agent.run(
            identity=identity,
            question="Please refund ORDER-42.",
        )
        print("\nrefund proposal:", proposed.status, proposed.approval)

        completed = agent.resume_refund(
            identity=identity,
            run_id=proposed.run_id,
            decision=ApprovalDecision(outcome="approve"),
        )
        print("refund result:", completed.answer)
        print("effects:", store.effect_count())


if __name__ == "__main__":
    main()

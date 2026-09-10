from __future__ import annotations

from pathlib import Path
import tempfile

from agent import ApprovalDecision, SupportAgent
from deepseek_decision import (
    DeepSeekDecisionModel,
    create_client,
    format_conversation,
    required_env,
)
from domain import TrustedIdentity
from store import SupportStore


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = SupportStore(Path(tmp) / "support.db")
        decision_model = DeepSeekDecisionModel(
            client=create_client(),
            model=required_env("DEEPSEEK_MODEL"),
        )
        agent = SupportAgent(store, decision_model=decision_model)
        identity = TrustedIdentity(tenant_id="acme", user_id="alice")

        question = "Can ORDER-42 be refunded to the original payment method?"
        answer = agent.run(identity=identity, question=question)
        print("question result:", answer.status)
        print(answer.answer)
        print("trace:", answer.trace)
        if decision_model.last_interaction is not None:
            print()
            print(format_conversation(interaction=decision_model.last_interaction))

        refund_question = "Please refund ORDER-42."
        proposed = agent.run(identity=identity, question=refund_question)
        print("\nrefund proposal:", proposed.status, proposed.approval)
        if decision_model.last_interaction is not None:
            print()
            print(format_conversation(interaction=decision_model.last_interaction))

        if proposed.approval is None:
            raise RuntimeError("The model did not produce a refund proposal for the demo.")
        completed = agent.resume_refund(
            identity=identity,
            run_id=proposed.run_id,
            decision=ApprovalDecision(outcome="approve"),
        )
        print("\nrefund result:", completed.answer)
        print("effects:", store.effect_count())


if __name__ == "__main__":
    main()

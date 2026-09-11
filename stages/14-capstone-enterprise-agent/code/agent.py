from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from decision import DecisionModel, DeterministicDecisionModel
from domain import ORDERS, POLICIES, Order, TrustedIdentity
from retrieval import Evidence, PolicyRetriever
from store import SupportStore


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    run_id: str
    order_id: str
    amount: str
    reason: str


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    outcome: Literal["approve", "edit", "reject"]
    amount: str | None = None


@dataclass(frozen=True, slots=True)
class SupportResult:
    run_id: str
    status: str
    answer: str
    evidence_ids: tuple[str, ...]
    trace: tuple[str, ...]
    approval: ApprovalRequest | None = None


class SupportAgent:
    def __init__(
        self,
        store: SupportStore,
        *,
        decision_model: DecisionModel | None = None,
    ) -> None:
        self.store = store
        self.retriever = PolicyRetriever(POLICIES)
        self.decision_model = decision_model or DeterministicDecisionModel()

    def run(self, *, identity: TrustedIdentity, question: str) -> SupportResult:
        if not question.strip():
            raise ValueError("question must not be blank")

        decision = self.decision_model.decide(question)
        trace: list[str] = [f"model:decision:{decision.kind}"]
        order_id = decision.order_id

        if decision.kind == "greeting":
            return self._persist(
                identity=identity,
                status="completed",
                question=question,
                order_id=None,
                proposed_amount=None,
                evidence=(),
                answer="Hello. How can I help with your order?",
                trace=trace,
            )

        if order_id is not None:
            trace.append("tool:lookup_order")
            order = self._lookup_owned_order(identity, order_id)
            if order is None:
                return self._persist(
                    identity=identity,
                    status="completed",
                    question=question,
                    order_id=None,
                    proposed_amount=None,
                    evidence=(),
                    answer="I cannot find an accessible order with that ID.",
                    trace=trace + ["answer:not_found"],
                )
        else:
            order = None

        if decision.kind in {"refund_question", "refund_action"}:
            evidence = self.retriever.retrieve(
                "refund original payment method within 30 days after 30 days store credit",
                top_k=2,
            )
            trace.append("retrieval:refund_policy")
            if not evidence:
                return self._abstain(identity, question, order_id, trace)

            if order is None:
                answer = self._answer_from_evidence("Refund policy: ", evidence)
                return self._persist(
                    identity=identity,
                    status="completed",
                    question=question,
                    order_id=None,
                    proposed_amount=None,
                    evidence=evidence,
                    answer=answer,
                    trace=trace + ["answer:grounded"],
                )

            if order.age_days > 30:
                late = tuple(
                    item for item in evidence if item.id == "refund-after-30-days"
                )
                answer = self._answer_from_evidence(
                    f"{order.order_id} is {order.age_days} days old. ",
                    late,
                )
                return self._persist(
                    identity=identity,
                    status="completed",
                    question=question,
                    order_id=order.order_id,
                    proposed_amount=None,
                    evidence=late,
                    answer=answer,
                    trace=trace + ["policy:late_refund", "answer:grounded"],
                )

            if decision.kind == "refund_action":
                trace.append("proposal:refund")
                run = self.store.create_run(
                    tenant_id=identity.tenant_id,
                    user_id=identity.user_id,
                    status="waiting_approval",
                    question=question,
                    order_id=order.order_id,
                    proposed_amount=order.amount,
                    evidence_ids=tuple(item.id for item in evidence),
                    answer=(
                        f"Refund for {order.order_id} is eligible under the retrieved "
                        f"policy. Approval is required before refunding {order.amount}."
                    ),
                )
                approval = ApprovalRequest(
                    run_id=run.run_id,
                    order_id=order.order_id,
                    amount=order.amount,
                    reason="Refund changes external financial state.",
                )
                return SupportResult(
                    run_id=run.run_id,
                    status=run.status,
                    answer=run.answer,
                    evidence_ids=run.evidence_ids,
                    trace=tuple(trace + ["approval:waiting"]),
                    approval=approval,
                )

            within = tuple(
                item for item in evidence if item.id == "refund-within-30-days"
            )
            answer = self._answer_from_evidence(
                f"{order.order_id} is {order.age_days} days old. ",
                within,
            )
            return self._persist(
                identity=identity,
                status="completed",
                question=question,
                order_id=order.order_id,
                proposed_amount=None,
                evidence=within,
                answer=answer,
                trace=trace + ["answer:grounded"],
            )

        evidence = self.retriever.retrieve(question, top_k=2)
        trace.append("retrieval:policy")
        if not evidence:
            return self._abstain(identity, question, order_id, trace)

        return self._persist(
            identity=identity,
            status="completed",
            question=question,
            order_id=order_id,
            proposed_amount=None,
            evidence=evidence,
            answer=self._answer_from_evidence("Policy evidence: ", evidence),
            trace=trace + ["answer:grounded"],
        )

    def resume_refund(
        self,
        *,
        identity: TrustedIdentity,
        run_id: str,
        decision: ApprovalDecision,
    ) -> SupportResult:
        run = self.store.get_run(
            run_id,
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
        )
        trace = ["resume:refund"]

        if run.status == "completed":
            return SupportResult(
                run_id=run.run_id,
                status=run.status,
                answer=run.answer,
                evidence_ids=run.evidence_ids,
                trace=tuple(trace + ["effect:already_completed"]),
            )
        if run.status == "rejected":
            return SupportResult(
                run_id=run.run_id,
                status=run.status,
                answer=run.answer,
                evidence_ids=run.evidence_ids,
                trace=tuple(trace + ["approval:already_rejected"]),
            )
        if run.status != "waiting_approval" or not run.order_id or not run.proposed_amount:
            raise ValueError("run is not waiting for a refund approval")

        if decision.outcome == "reject":
            answer = "Refund was rejected. No refund side effect was executed."
            self.store.reject_run(run_id, answer=answer)
            return SupportResult(
                run_id=run_id,
                status="rejected",
                answer=answer,
                evidence_ids=run.evidence_ids,
                trace=tuple(trace + ["approval:rejected"]),
            )

        amount = run.proposed_amount
        if decision.outcome == "edit":
            if decision.amount is None:
                raise ValueError("edit requires amount")
            amount = self._validate_edited_amount(
                proposed=run.proposed_amount,
                edited=decision.amount,
            )
            trace.append("approval:edited")
        elif decision.outcome == "approve":
            trace.append("approval:approved")
        else:
            raise ValueError(f"unknown approval outcome: {decision.outcome}")

        result = self.store.record_refund_once(
            run_id=run.run_id,
            order_id=run.order_id,
            amount=amount,
        )
        answer = (
            f"Refund completed for {result['order_id']} in the amount "
            f"{result['amount']}."
        )
        self.store.complete_run(run_id, answer=answer)
        return SupportResult(
            run_id=run_id,
            status="completed",
            answer=answer,
            evidence_ids=run.evidence_ids,
            trace=tuple(trace + ["effect:refund_completed"]),
        )

    def _persist(
        self,
        *,
        identity: TrustedIdentity,
        status: str,
        question: str,
        order_id: str | None,
        proposed_amount: str | None,
        evidence: tuple[Evidence, ...],
        answer: str,
        trace: list[str],
    ) -> SupportResult:
        run = self.store.create_run(
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
            status=status,
            question=question,
            order_id=order_id,
            proposed_amount=proposed_amount,
            evidence_ids=tuple(item.id for item in evidence),
            answer=answer,
        )
        return SupportResult(
            run_id=run.run_id,
            status=run.status,
            answer=run.answer,
            evidence_ids=run.evidence_ids,
            trace=tuple(trace),
        )

    def _abstain(
        self,
        identity: TrustedIdentity,
        question: str,
        order_id: str | None,
        trace: list[str],
    ) -> SupportResult:
        return self._persist(
            identity=identity,
            status="completed",
            question=question,
            order_id=order_id,
            proposed_amount=None,
            evidence=(),
            answer="I do not have enough policy evidence to answer reliably.",
            trace=trace + ["answer:abstain"],
        )

    @staticmethod
    def _lookup_owned_order(identity: TrustedIdentity, order_id: str) -> Order | None:
        order = ORDERS.get(order_id)
        if order is None:
            return None
        if order.tenant_id != identity.tenant_id or order.user_id != identity.user_id:
            return None
        return order

    @staticmethod
    def _answer_from_evidence(prefix: str, evidence: tuple[Evidence, ...]) -> str:
        if not evidence:
            return "I do not have enough policy evidence to answer reliably."
        citations = ", ".join(f"[{item.id}]" for item in evidence)
        return f"{prefix}{evidence[0].text} Evidence: {citations}"

    @staticmethod
    def _validate_edited_amount(*, proposed: str, edited: str) -> str:
        try:
            proposed_value = Decimal(proposed)
            edited_value = Decimal(edited)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("edited amount must be numeric") from exc
        if edited_value <= 0:
            raise ValueError("edited amount must be positive")
        if edited_value > proposed_value:
            raise ValueError("edited amount cannot exceed the proposed refund")
        return str(edited_value.quantize(Decimal("0.01")))

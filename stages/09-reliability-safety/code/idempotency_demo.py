from __future__ import annotations

from dataclasses import dataclass

from guardrails import (
    ExecutionBudget,
    ExecutionContext,
    GuardedExecutor,
    PermissionPolicy,
    Principal,
    ToolFailure,
    ToolSpec,
)


@dataclass(frozen=True, slots=True)
class RefundReceipt:
    receipt_id: str
    order_id: str
    amount: str


class RefundService:
    """A small stand-in for a payment API that enforces idempotency server-side."""

    def __init__(self) -> None:
        self._receipts_by_key: dict[str, RefundReceipt] = {}
        self.created_refunds = 0

    def issue_refund(
        self,
        *,
        order_id: str,
        amount: str,
        idempotency_key: str,
    ) -> RefundReceipt:
        existing = self._receipts_by_key.get(idempotency_key)
        if existing is not None:
            return existing

        self.created_refunds += 1
        receipt = RefundReceipt(
            receipt_id=f"refund-{self.created_refunds}",
            order_id=order_id,
            amount=amount,
        )
        self._receipts_by_key[idempotency_key] = receipt
        return receipt


class AmbiguousRefundTransport:
    """The first call succeeds at the service but loses its response afterward."""

    def __init__(self, service: RefundService) -> None:
        self._service = service
        self._calls = 0

    def issue_refund(
        self,
        *,
        context: ExecutionContext,
        order_id: str,
        amount: str,
    ) -> dict[str, str]:
        context.check_deadline()
        if context.idempotency_key is None:
            raise RuntimeError("refund handler requires an idempotency key")
        receipt = self._service.issue_refund(
            order_id=order_id,
            amount=amount,
            idempotency_key=context.idempotency_key,
        )
        self._calls += 1
        if self._calls == 1:
            raise ToolFailure("response lost after payment service accepted the refund", retryable=True)
        return {
            "receipt_id": receipt.receipt_id,
            "order_id": receipt.order_id,
            "amount": receipt.amount,
        }


def build_executor(service: RefundService) -> GuardedExecutor:
    transport = AmbiguousRefundTransport(service)
    tool = ToolSpec(
        "issue_refund",
        {"order_id": str, "amount": str},
        transport.issue_refund,
        idempotency_supported=True,
    )
    return GuardedExecutor(
        [tool],
        permissions=PermissionPolicy({"refund_manager": {"issue_refund"}}),
    )


def main() -> None:
    service = RefundService()
    executor = build_executor(service)
    result = executor.execute(
        principal=Principal("mia", frozenset({"refund_manager"})),
        tool_name="issue_refund",
        arguments={"order_id": "ORDER-42", "amount": "10.00"},
        budget=ExecutionBudget(max_retries=1, max_same_call=3),
        context=ExecutionContext(idempotency_key="refund:run-17:ORDER-42"),
    )

    print("=== ambiguous refund, then retry ===")
    print("executor attempts:", result.attempts)
    print("executor result:", result.value)
    print("refunds created by service:", service.created_refunds)
    assert result.ok
    assert result.attempts == 2
    assert service.created_refunds == 1


if __name__ == "__main__":
    main()

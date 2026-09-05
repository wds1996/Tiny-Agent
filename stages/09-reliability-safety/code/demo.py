from __future__ import annotations

import time

from guardrails import (
    ExecutionBudget,
    ExecutionContext,
    GuardedExecutor,
    PermissionPolicy,
    Principal,
    ToolFailure,
    ToolSpec,
)


_ATTEMPTS = {"flaky": 0}


def lookup_order(*, context: ExecutionContext, order_id: str) -> dict[str, str]:
    context.check_deadline()
    return {"order_id": order_id, "status": "paid"}


def flaky_catalog(*, context: ExecutionContext, sku: str) -> dict[str, str]:
    context.check_deadline()
    _ATTEMPTS["flaky"] += 1
    if _ATTEMPTS["flaky"] == 1:
        raise ToolFailure(
            "temporary upstream outage Authorization: Bearer demo-secret",
            retryable=True,
        )
    return {"sku": sku, "stock": "12"}


def issue_refund(*, context: ExecutionContext, order_id: str, amount: str) -> dict[str, str]:
    context.check_deadline()
    return {"order_id": order_id, "amount": amount, "status": "refunded"}


def main() -> None:
    tools = [
        ToolSpec("lookup_order", {"order_id": str}, lookup_order, safe_to_retry=True),
        ToolSpec("flaky_catalog", {"sku": str}, flaky_catalog, safe_to_retry=True),
        ToolSpec("issue_refund", {"order_id": str, "amount": str}, issue_refund),
    ]
    policy = PermissionPolicy(
        {
            "support": {"lookup_order", "flaky_catalog"},
            "refund_manager": {"lookup_order", "issue_refund"},
        }
    )
    executor = GuardedExecutor(tools, permissions=policy)
    support = Principal("alice", frozenset({"support"}))
    budget = ExecutionBudget(max_tool_calls=8, max_retries=2, max_same_call=2)

    print(executor.execute(
        principal=support,
        tool_name="lookup_order",
        arguments={"order_id": "ORDER-42"},
        budget=budget,
    ))
    print(executor.execute(
        principal=support,
        tool_name="issue_refund",
        arguments={"order_id": "ORDER-42", "amount": "10.00"},
        budget=budget,
    ))
    print(executor.execute(
        principal=support,
        tool_name="flaky_catalog",
        arguments={"sku": "BOOK-1"},
        budget=budget,
    ))

    deadline = ExecutionContext(deadline_monotonic=time.monotonic() - 0.01)
    print(executor.execute(
        principal=support,
        tool_name="lookup_order",
        arguments={"order_id": "ORDER-99"},
        budget=ExecutionBudget(),
        context=deadline,
    ))


if __name__ == "__main__":
    main()

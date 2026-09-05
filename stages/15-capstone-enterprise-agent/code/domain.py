from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrustedIdentity:
    tenant_id: str
    user_id: str


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    tenant_id: str
    user_id: str
    amount: str
    age_days: int
    status: str


ORDERS = {
    "ORDER-42": Order(
        order_id="ORDER-42",
        tenant_id="acme",
        user_id="alice",
        amount="49.00",
        age_days=12,
        status="paid",
    ),
    "ORDER-99": Order(
        order_id="ORDER-99",
        tenant_id="acme",
        user_id="alice",
        amount="27.50",
        age_days=45,
        status="paid",
    ),
}


@dataclass(frozen=True, slots=True)
class PolicyDocument:
    id: str
    text: str


POLICIES = (
    PolicyDocument(
        id="refund-within-30-days",
        text=(
            "Paid orders within 30 days may be refunded to the original payment "
            "method after required approval."
        ),
    ),
    PolicyDocument(
        id="refund-after-30-days",
        text=(
            "After 30 days, an original-payment refund is not available. "
            "Support may offer store credit after review."
        ),
    ),
    PolicyDocument(
        id="standard-shipping",
        text="Standard shipping normally takes three to five business days.",
    ),
)

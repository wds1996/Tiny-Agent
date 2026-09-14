from __future__ import annotations

from dataclasses import dataclass
from itertools import count


@dataclass(frozen=True, slots=True)
class OrderRecord:
    order_id: str
    placed_on: str
    status: str
    item_type: str
    amount_paid: float
    currency: str
    shipment_status: str
    tracking_number: str
    invoice_number: str


ORDERS: dict[str, OrderRecord] = {
    "ACME-1007": OrderRecord(
        order_id="ACME-1007",
        placed_on="2026-08-03",
        status="delivered",
        item_type="standard",
        amount_paid=129.0,
        currency="CNY",
        shipment_status="delivered",
        tracking_number="TEACH-7788",
        invoice_number="INV-1007",
    ),
    "ACME-1012": OrderRecord(
        order_id="ACME-1012",
        placed_on="2026-07-20",
        status="delivered",
        item_type="standard",
        amount_paid=89.0,
        currency="CNY",
        shipment_status="delivered",
        tracking_number="TEACH-7812",
        invoice_number="INV-1012",
    ),
}

SUPPORT_GUIDES = {
    "refund-evidence": (
        "Before a refund case is reviewed, support should verify the order record, "
        "the applicable policy version, and any required approval materials."
    ),
    "shipment-delay": (
        "For a shipment-delay case, record the order ID, current shipment status, "
        "tracking number, and the latest carrier event available to the support system."
    ),
}

_CASE_SEQUENCE = count(1)


def _order(order_id: str) -> OrderRecord:
    normalized = order_id.strip().upper()
    try:
        return ORDERS[normalized]
    except KeyError as exc:
        raise LookupError(f"unknown teaching order: {order_id}") from exc


def get_order_summary(order_id: str) -> dict[str, object]:
    order = _order(order_id)
    return {
        "order_id": order.order_id,
        "placed_on": order.placed_on,
        "status": order.status,
        "item_type": order.item_type,
        "amount_paid": order.amount_paid,
        "currency": order.currency,
    }


def get_shipment_status(order_id: str) -> dict[str, str]:
    order = _order(order_id)
    return {
        "order_id": order.order_id,
        "shipment_status": order.shipment_status,
        "tracking_number": order.tracking_number,
    }


def get_invoice_summary(order_id: str) -> dict[str, object]:
    order = _order(order_id)
    return {
        "order_id": order.order_id,
        "invoice_number": order.invoice_number,
        "amount_paid": order.amount_paid,
        "currency": order.currency,
    }


def create_support_case(order_id: str, reason: str) -> dict[str, str]:
    order = _order(order_id)
    clean_reason = " ".join(reason.split())
    if len(clean_reason) < 8:
        raise ValueError("support case reason must contain at least 8 characters")
    case_id = f"CASE-{next(_CASE_SEQUENCE):04d}"
    return {
        "case_id": case_id,
        "order_id": order.order_id,
        "status": "opened",
        "reason": clean_reason,
    }


def read_support_guide(topic: str) -> str:
    normalized = topic.strip().lower()
    try:
        return SUPPORT_GUIDES[normalized]
    except KeyError as exc:
        raise LookupError(f"unknown support guide: {topic}") from exc

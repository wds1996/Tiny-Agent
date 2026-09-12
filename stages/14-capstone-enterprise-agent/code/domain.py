"""Small contracts shared by the application and the simulated business service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
from pathlib import Path
from typing import Any

DATA = Path(__file__).with_name("data")


class BoundaryError(ValueError):
    """Only a stable code, never an upstream exception or a secret."""


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def object_from_json(text: str, *, limit: int = 30_000) -> dict:
    if not isinstance(text, str) or len(text) > limit:
        raise BoundaryError("invalid_json_size")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise BoundaryError("duplicate_json_key")
            result[key] = value
        return result
    def invalid(_):
        raise BoundaryError("nonfinite_json")
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, TypeError, RecursionError) as exc:
        raise BoundaryError("invalid_json") from exc
    if not isinstance(value, dict):
        raise BoundaryError("expected_object")
    return value


def fields(value: dict, required: set[str], optional: set[str] = frozenset()) -> None:
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise BoundaryError("unexpected_fields")


def text(value: Any, *, maximum: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise BoundaryError("invalid_text")
    return value.strip()


def integer(value: Any, *, minimum: int = 0, maximum: int = 10_000_000) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise BoundaryError("invalid_integer")
    return value


@dataclass(frozen=True)
class Identity:
    tenant: str
    user: str
    role: str


def profile(name: str) -> Identity:
    data = json.loads((DATA / "business.json").read_text(encoding="utf-8"))
    try:
        return Identity(**data["profiles"][name])
    except KeyError as exc:
        raise BoundaryError("unknown_demo_profile") from exc


def refund_quote(order: dict, rules: dict, as_of: str) -> dict:
    """Money is integer cents; this is a narrow *fictional* full-item return policy."""
    age = (date.fromisoformat(as_of) - date.fromisoformat(order["delivered_on"])).days if order["delivered_on"] else None
    reason = "eligible"
    if order["tenant"] != rules["tenant"]:
        reason = "merchant_requires_manual_review"
    elif order["status"] != "delivered" or age is None or age < 0:
        reason = "not_delivered"
    elif order["category"] in rules["excluded_categories"]:
        reason = "excluded_category"
    elif age > rules["return_days"]:
        reason = "outside_window"
    elif not order["return_received"]:
        reason = "return_not_received"
    elif order["refunded_cents"] >= order["paid_items_cents"]:
        reason = "already_refunded"
    amount = max(0, order["paid_items_cents"] - order["refunded_cents"])
    result = {
        "order_id": order["order_id"], "order_version": order["version"],
        "tenant": order["tenant"], "user": order["user"], "currency": "CNY",
        "as_of": as_of, "rule_version": rules["version"], "days_since_delivery": age,
        "eligible": reason == "eligible", "reason": reason,
        "amount_cents": amount if reason == "eligible" else 0,
        "shipping_refund_cents": 0, "policy_pages": rules["policy_pages"],
    }
    result["quote_id"] = digest(result)
    return result

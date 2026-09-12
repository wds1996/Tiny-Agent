"""Small data contracts. Test expectations deliberately live elsewhere."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from tracing import Trace

DECISIONS = frozenset({
    "greeting", "eligible", "ineligible", "insufficient_evidence",
    "access_denied", "temporarily_unavailable",
})
POLICY_ID = "refund-policy-v1"


def json_object(raw: str, *, max_chars: int = 16000) -> dict[str, Any]:
    if not isinstance(raw, str) or len(raw) > max_chars:
        raise ValueError("invalid JSON input size")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("non-finite JSON number")

    value = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


@dataclass(frozen=True)
class Order:
    id: str = "ORDER-42"
    owner: str = "alice"
    delivered_days: int = 7

    def __post_init__(self):
        if type(self.delivered_days) is not int or self.delivered_days < 0:
            raise ValueError("delivered_days must be a nonnegative integer")


@dataclass(frozen=True)
class Request:
    question: str
    user_id: str = "alice"
    orders: tuple[Order, ...] = (Order(),)
    policy_available: bool = True
    lookup_unavailable: bool = False

    def __post_init__(self):
        if not isinstance(self.question, str) or not self.question.strip():
            raise ValueError("question must not be blank")
        if len(self.question) > 4000 or not self.user_id:
            raise ValueError("invalid request")
        if len({o.id for o in self.orders}) != len(self.orders):
            raise ValueError("duplicate order IDs")


@dataclass(frozen=True)
class Answer:
    decision: str
    text: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self):
        if self.decision not in DECISIONS:
            raise ValueError("unknown decision")
        if not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 6000:
            raise ValueError("invalid answer text")
        if (not isinstance(self.evidence_ids, tuple)
                or len(self.evidence_ids) > 8
                or any(not isinstance(x, str) or not x or len(x) > 100 for x in self.evidence_ids)
                or len(set(self.evidence_ids)) != len(self.evidence_ids)):
            raise ValueError("invalid evidence IDs")

    @classmethod
    def parse(cls, raw: str) -> "Answer":
        obj = json_object(raw)
        if set(obj) != {"decision", "text", "evidence_ids"}:
            raise ValueError("answer fields do not match the contract")
        if not isinstance(obj["decision"], str) or not isinstance(obj["evidence_ids"], list):
            raise ValueError("invalid answer types")
        return cls(obj["decision"], obj["text"], tuple(obj["evidence_ids"]))


@dataclass(frozen=True)
class ToolRecord:
    name: str
    arguments_json: str
    outcome: str

    @classmethod
    def of(cls, name: str, arguments: dict, outcome: str = "ok") -> "ToolRecord":
        return cls(name, json.dumps(arguments, sort_keys=True, ensure_ascii=False), outcome)


@dataclass(frozen=True)
class AgentRun:
    run_id: str
    answer: Answer | None
    calls: tuple[ToolRecord, ...]
    retrieved_ids: tuple[str, ...]
    visible_ids: tuple[str, ...]
    latency_ms: float
    trace: Trace
    error: str | None = None
    model_calls: int = 0
    prompt_tokens: int | None = 0
    completion_tokens: int | None = 0
    estimated_cost_usd: float | None = None
    metadata: dict[str, str] = field(default_factory=dict)

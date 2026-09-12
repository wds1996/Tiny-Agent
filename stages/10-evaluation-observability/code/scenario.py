"""Read-only, synthetic support tasks with actual instrumented tool execution."""
from __future__ import annotations

import re
import time
from typing import Any
from uuid import uuid4

from contracts import AgentRun, Answer, POLICY_ID, Request, ToolRecord
from tracing import Trace, Tracer

POLICY = {
    "source_id": POLICY_ID,
    "kind": "policy",
    "window_days": 30,
    "text": "Teaching policy: delivered orders within 30 days may be returned to the original payment method.",
}
VERSIONS = ("baseline", "candidate", "fixed")


class ToolRejected(ValueError):
    pass


class BudgetExceeded(RuntimeError):
    pass


class SupportSession:
    def __init__(self, request: Request, *, version: str, max_tools: int = 6) -> None:
        if type(max_tools) is not int or max_tools < 1:
            raise ValueError("max_tools must be positive")
        self.request = request
        self.version = version
        self.max_tools = max_tools
        self.trace = Trace(uuid4().hex)
        self.tracer = Tracer(self.trace)
        self.started = time.perf_counter()
        self.calls: list[ToolRecord] = []
        self.documents: dict[str, dict[str, Any]] = {}
        self.visible_ids: list[str] = []
        self.model_calls = 0
        self.prompt_tokens: int | None = 0
        self.completion_tokens: int | None = 0

    def dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if len(self.calls) >= self.max_tools:
            raise BudgetExceeded("tool request budget exhausted")
        label = name if name in {"lookup_order", "search_refund_policy"} else "unknown"
        with self.tracer.span("tool.request", tool=label, attempt=len(self.calls) + 1) as span:
            try:
                with self.tracer.span("tool.validate"):
                    if name not in {"lookup_order", "search_refund_policy"}:
                        raise ToolRejected("unknown_tool")
                    expected = {"order_id"} if name == "lookup_order" else set()
                    if (not isinstance(arguments, dict) or set(arguments) != expected
                            or (expected and (not isinstance(arguments["order_id"], str)
                                or re.fullmatch(r"ORDER-\d{1,8}", arguments["order_id"]) is None))):
                        raise ToolRejected("invalid_arguments")
                with self.tracer.span("tool.authorize") as auth:
                    order = None
                    if name == "lookup_order":
                        order = next((o for o in self.request.orders if o.id == arguments["order_id"]), None)
                        if order is not None and order.owner != self.request.user_id:
                            auth["allowed"] = False
                            raise ToolRejected("access_denied")
                    auth["allowed"] = True
                with self.tracer.span("tool.execute", tool=name) as execution:
                    if name == "lookup_order":
                        if self.request.lookup_unavailable:
                            raise TimeoutError("synthetic upstream failure; do not log raw errors")
                        docs = [] if order is None else [{
                            "source_id": f"order:{order.id}", "kind": "order",
                            "delivered_days": order.delivered_days,
                        }]
                    else:
                        docs = [dict(POLICY)] if self.request.policy_available else []
                    execution["found_count"] = len(docs)
                    for doc in docs:
                        self.documents[doc["source_id"]] = doc
                outcome, response = "ok", {"ok": True, "documents": docs}
            except ToolRejected as exc:
                outcome = "rejected"
                response = {"ok": False, "error": str(exc)}  # fixed application codes only
            except TimeoutError:
                outcome = "failed"
                response = {"ok": False, "error": "temporarily_unavailable"}
            span["outcome"] = outcome
            self.calls.append(ToolRecord.of(name, arguments, outcome))
        return response

    def reject_request(self, name: str) -> dict[str, Any]:
        if len(self.calls) >= self.max_tools:
            raise BudgetExceeded("tool request budget exhausted")
        with self.tracer.span("tool.request", tool="unknown", outcome="rejected"):
            self.calls.append(ToolRecord.of(name, {"invalid_arguments": True}, "rejected"))
        return {"ok": False, "error": "invalid_arguments"}

    def context(self) -> list[dict[str, Any]]:
        with self.tracer.span("context.build") as span:
            documents = list(self.documents.values())
            span["found_count"] = len(documents)
            if self.version == "candidate":
                # Deliberate regression: a context "optimization" drops policy evidence.
                documents = [doc for doc in documents if doc["kind"] == "order"]
            self.visible_ids = [doc["source_id"] for doc in documents]
            span["selected_count"] = len(documents)
            return documents

    def finish(self, answer: Answer | None, *, error: str | None = None,
               metadata: dict[str, str] | None = None) -> AgentRun:
        return AgentRun(
            run_id=self.trace.run_id, answer=answer, calls=tuple(self.calls),
            retrieved_ids=tuple(self.documents), visible_ids=tuple(self.visible_ids),
            latency_ms=(time.perf_counter() - self.started) * 1000, trace=self.trace,
            error=error, model_calls=self.model_calls, prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens, estimated_cost_usd=None,
            metadata={"variant": self.version, "fixtures": "support-fixtures-v1", **(metadata or {})},
        )


def compose_answer(question: str, documents: list[dict[str, Any]]) -> Answer:
    """Deterministic model substitute. It sees selected documents, not test labels."""
    if question.strip().lower() in {"hello", "hi", "你好"}:
        return Answer("greeting", "Hello. I can explain the teaching refund policy.")
    order = next((d for d in documents if d["kind"] == "order"), None)
    policy = next((d for d in documents if d["kind"] == "policy"), None)
    if "refund" not in question.lower() or order is None or policy is None:
        return Answer("insufficient_evidence", "I do not have enough evidence to judge this request.")
    eligible = order["delivered_days"] <= policy["window_days"]
    return Answer(
        "eligible" if eligible else "ineligible",
        ("The order is within the teaching 30-day window; a return may use the original payment method."
         if eligible else "The order is outside the teaching 30-day window."),
        (order["source_id"], policy["source_id"]),
    )


def run_offline(request: Request, *, version: str = "baseline") -> AgentRun:
    if version not in VERSIONS:
        raise ValueError("unknown version")
    session = SupportSession(request, version=version)
    answer = None
    with session.tracer.span("agent.run") as root:
        with session.tracer.span("route.decide"):
            greeting = request.question.strip().lower() in {"hello", "hi", "你好"}
            order_match = re.search(r"ORDER-\d{1,8}\b", request.question)
        if not greeting:
            if order_match:
                result = session.dispatch("lookup_order", {"order_id": order_match.group()})
                if not result["ok"]:
                    decision = result["error"]
                    answer = Answer(decision, "Access denied." if decision == "access_denied"
                                    else "The order service is unavailable; no eligibility decision was made.")
            if answer is None:
                session.dispatch("search_refund_policy", {})
        documents = session.context()
        with session.tracer.span("answer.compose"):
            if answer is None:
                answer = compose_answer(request.question, documents)
        root["decision"] = answer.decision
    return session.finish(answer, metadata={"model": "deterministic-substitute"})

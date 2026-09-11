from __future__ import annotations

from evaluation import AgentRun, EvalCase, evaluate
from tracing import CapturePolicy, Trace, Tracer, format_trace


def deterministic_agent(case: EvalCase) -> AgentRun:
    if "hello" in case.question.lower():
        return AgentRun("Hello.", (), latency_ms=5, estimated_cost_usd=0.0001)
    if "refund" in case.question.lower():
        return AgentRun(
            "Orders within 30 days may use the original payment method.",
            ("lookup_order", "search_policy"),
            retrieved_ids=("refund-policy",),
            latency_ms=18,
            estimated_cost_usd=0.0012,
        )
    return AgentRun(
        "I do not have enough evidence to answer reliably.",
        ("search_policy",),
        abstained=True,
        latency_ms=12,
        estimated_cost_usd=0.0008,
    )


def main() -> None:
    trace = Trace("run-001")
    tracer = Tracer(trace, capture_policy=CapturePolicy(capture_content=False))

    with tracer.span("agent.run", workflow="refund_support"):
        with tracer.span("context.build", question="Can ORDER-42 be refunded?") as span:
            span["selected_items"] = 3

        with tracer.span("tool.lookup_order", tool="lookup_order") as span:
            span["status_code"] = 200

    print("trace:")
    print(format_trace(trace))
    print("safe span attributes:", trace.spans[0].attributes)

    cases = [
        EvalCase("greet", "hello", ("hello",), ()),
        EvalCase(
            "refund",
            "Can this refund use the original payment method?",
            ("30 days",),
            ("lookup_order", "search_policy"),
        ),
        EvalCase(
            "unknown",
            "What is the policy for lunar delivery?",
            ("not have enough evidence",),
            ("search_policy",),
            should_abstain=True,
        ),
    ]
    print("\neval:", evaluate(cases, deterministic_agent))


if __name__ == "__main__":
    main()

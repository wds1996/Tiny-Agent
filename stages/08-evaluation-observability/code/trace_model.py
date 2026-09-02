"""Stage 08 example 1: inspect the minimum data model behind a trace span."""

from tiny_agent import SpanRecord


span = SpanRecord(
    trace_id="trace-001",
    span_id="span-001",
    parent_span_id=None,
    name="invoke_agent",
    kind="agent",
    status="ok",
    start_time_ns=1_000_000_000,
    end_time_ns=1_025_000_000,
    duration_ns=25_000_000,
    attributes={"gen_ai.operation.name": "invoke_agent"},
)

print("trace_id   =", span.trace_id)
print("span_id    =", span.span_id)
print("parent     =", span.parent_span_id)
print("duration_ms=", span.duration_ms)
print("attributes =", dict(span.attributes))

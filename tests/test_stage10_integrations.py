import pytest
from langsmith import traceable, tracing_context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from tiny_agent.integrations.opentelemetry import OpenTelemetryTracer


def test_langsmith_traceable_can_be_disabled_without_network_or_api_key():
    @traceable(name="tiny-agent-stage10-ci")
    def add(a: int, b: int) -> int:
        return a + b

    with tracing_context(enabled=False):
        assert add(20, 22) == 42


def test_opentelemetry_adapter_exports_nested_spans_in_memory():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = OpenTelemetryTracer(provider.get_tracer("tiny-agent-stage10-test"))

    with tracer.span(
        "invoke_agent",
        kind="agent",
        attributes={"gen_ai.operation.name": "invoke_agent"},
    ):
        with tracer.span(
            "execute_tool search",
            kind="tool",
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "tool.name": "search",
            },
        ):
            pass

    finished = exporter.get_finished_spans()
    assert [span.name for span in finished] == ["execute_tool search", "invoke_agent"]
    child, root = finished
    assert child.parent is not None
    assert child.parent.span_id == root.context.span_id
    assert child.attributes["tool.name"] == "search"
    assert root.attributes["gen_ai.operation.name"] == "invoke_agent"


def test_opentelemetry_adapter_marks_error_without_exception_span_event():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = OpenTelemetryTracer(provider.get_tracer("tiny-agent-stage10-error-test"))

    with pytest.raises(RuntimeError, match="private detail"):
        with tracer.span("explode", kind="tool"):
            raise RuntimeError("private detail")

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    span = finished[0]
    assert span.status.status_code == StatusCode.ERROR
    assert span.attributes["error.type"] == "RuntimeError"
    assert span.events == ()
    assert "private detail" not in str(dict(span.attributes))

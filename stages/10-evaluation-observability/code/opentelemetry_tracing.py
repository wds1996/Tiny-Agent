"""Stage 10 example 9: export Tiny-Agent spans through OpenTelemetry in memory."""

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tiny_agent.integrations.opentelemetry import OpenTelemetryTracer


exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
tracer = OpenTelemetryTracer(provider.get_tracer("tiny-agent-stage10-demo"))

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

for span in exporter.get_finished_spans():
    parent = span.parent.span_id if span.parent else None
    print(span.name, "parent=", parent, "attributes=", dict(span.attributes))

print("\nNo backend is required: the in-memory exporter proves the adapter contract.")

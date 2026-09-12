"""Optional local OpenTelemetry SDK example; no Collector or network exporter."""
from contracts import Request
from scenario import SupportSession


def run_demo(exporter=None):
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
    from opentelemetry.trace import Status, StatusCode

    provider = TracerProvider(resource=Resource.create({"service.name": "tiny-agent-stage10"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter or ConsoleSpanExporter()))
    tracer = provider.get_tracer("stage10-demo")  # do not replace a global provider
    session = SupportSession(Request("Can ORDER-42 be refunded?"), version="baseline")
    try:
        with tracer.start_as_current_span("support.inspect", record_exception=False,
                                          set_status_on_exception=False) as root:
            root.set_attribute("run.id", session.trace.run_id)
            with tracer.start_as_current_span("tool.lookup_order", record_exception=False,
                                              set_status_on_exception=False) as child:
                try:
                    result = session.dispatch("lookup_order", {"order_id": "ORDER-42"})
                    child.set_attribute("tool.outcome", "ok" if result["ok"] else "rejected")
                    child.set_attribute("evidence.count", len(result.get("documents", [])))
                except Exception:
                    child.set_status(Status(StatusCode.ERROR))
                    root.set_status(Status(StatusCode.ERROR))
                    raise
    finally:
        provider.force_flush()
        provider.shutdown()
    return result


if __name__ == "__main__":
    run_demo()

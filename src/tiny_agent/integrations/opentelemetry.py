from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator, Mapping

from opentelemetry import trace as otel_trace
from opentelemetry.trace import Status, StatusCode

from ..observability import SpanKind, SpanStatus, TraceCapturePolicy


class _OpenTelemetrySpanHandle:
    def __init__(self, span: Any, policy: TraceCapturePolicy) -> None:
        self._span = span
        self._policy = policy
        context = span.get_span_context()
        self.trace_id = format(context.trace_id, "032x")
        self.span_id = format(context.span_id, "016x")

    def set_attribute(self, key: str, value: Any) -> None:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("attribute key must be a non-empty string")
        sanitized = self._policy.sanitize_attribute(key, value)
        self._span.set_attribute(key, _otel_attribute_value(sanitized))

    def record_input(self, value: Any) -> None:
        if self._policy.capture_inputs:
            self._span.set_attribute(
                "tiny_agent.input.data",
                _otel_attribute_value(self._policy.sanitize(value)),
            )

    def record_output(self, value: Any) -> None:
        if self._policy.capture_outputs:
            self._span.set_attribute(
                "tiny_agent.output.data",
                _otel_attribute_value(self._policy.sanitize(value)),
            )

    def set_status(self, status: SpanStatus, *, error_type: str | None = None) -> None:
        if status == "error":
            self._span.set_status(Status(StatusCode.ERROR))
            if error_type:
                self._span.set_attribute("error.type", error_type)
        elif status == "ok":
            return
        elif status != "unset":
            raise ValueError(f"invalid span status: {status!r}")


class OpenTelemetryTracer:
    """Adapt Tiny-Agent's small Tracer protocol to OpenTelemetry spans.

    OpenTelemetry deprecated the Span Events API in 2026. This adapter disables
    the Python SDK's automatic exception event recording and records only error
    status/type on the span. Future event-like telemetry should use log records
    correlated with the active span.

    GenAI semantic-convention names are still evolving, so examples use only a
    small operation/tool-name subset and keep Tiny-Agent-specific attributes in
    the ``tiny_agent.*`` namespace.
    """

    def __init__(
        self,
        tracer: Any | None = None,
        *,
        capture_policy: TraceCapturePolicy | None = None,
        instrumentation_name: str = "tiny-agent",
    ) -> None:
        self._tracer = tracer or otel_trace.get_tracer(instrumentation_name)
        self.capture_policy = capture_policy or TraceCapturePolicy()

    @contextmanager
    def span(
        self,
        name: str,
        *,
        kind: SpanKind = "custom",
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[_OpenTelemetrySpanHandle]:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("span name must be a non-empty string")

        with self._tracer.start_as_current_span(
            name.strip(),
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            handle = _OpenTelemetrySpanHandle(span, self.capture_policy)
            handle.set_attribute("tiny_agent.span.kind", kind)
            for key, value in (attributes or {}).items():
                handle.set_attribute(key, value)
            try:
                yield handle
            except BaseException as exc:
                handle.set_status("error", error_type=type(exc).__name__)
                raise


def _otel_attribute_value(value: Any) -> Any:
    if value is None:
        return "null"
    if isinstance(value, (bool, int, float, str)):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

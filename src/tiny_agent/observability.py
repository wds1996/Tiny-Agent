from __future__ import annotations

import contextvars
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Literal, Mapping, Protocol
from uuid import uuid4


SpanKind = Literal[
    "agent",
    "workflow",
    "model",
    "tool",
    "retrieval",
    "memory",
    "evaluation",
    "custom",
]
SpanStatus = Literal["unset", "ok", "error"]

_DEFAULT_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "access_token",
    "refresh_token",
    "id_token",
)
_EXACT_SENSITIVE_KEYS = frozenset({"token", "bearer_token"})


@dataclass(frozen=True, slots=True)
class TraceCapturePolicy:
    """Privacy-oriented capture policy for local traces.

    Raw inputs and outputs are disabled by default. Observability is useful only
    if it does not silently undo the redaction and least-privilege boundaries
    established in Stage 07.
    """

    capture_inputs: bool = False
    capture_outputs: bool = False
    max_text_chars: int = 256
    sensitive_key_fragments: tuple[str, ...] = _DEFAULT_SENSITIVE_KEY_FRAGMENTS

    def __post_init__(self) -> None:
        if self.max_text_chars <= 0:
            raise ValueError("max_text_chars must be positive")
        if not self.sensitive_key_fragments:
            raise ValueError("sensitive_key_fragments must not be empty")

    def is_sensitive_key(self, key: str) -> bool:
        normalized = key.lower().replace("-", "_")
        if normalized in _EXACT_SENSITIVE_KEYS:
            return True
        return any(fragment in normalized for fragment in self.sensitive_key_fragments)

    def sanitize(self, value: Any) -> Any:
        return _sanitize_value(value, policy=self)

    def sanitize_attribute(self, key: str, value: Any) -> Any:
        if self.is_sensitive_key(key):
            return "<redacted>"
        return self.sanitize(value)


@dataclass(frozen=True, slots=True)
class SpanRecord:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    kind: SpanKind
    status: SpanStatus
    start_time_ns: int
    end_time_ns: int
    duration_ns: int
    attributes: Mapping[str, Any] = field(default_factory=dict)
    input_data: Any | None = None
    output_data: Any | None = None
    error_type: str | None = None

    def __post_init__(self) -> None:
        if not self.trace_id or not self.span_id:
            raise ValueError("trace_id and span_id must be non-empty")
        if not self.name.strip():
            raise ValueError("span name must be non-empty")
        if self.end_time_ns < self.start_time_ns:
            raise ValueError("end_time_ns must be >= start_time_ns")
        if self.duration_ns < 0:
            raise ValueError("duration_ns must be non-negative")

    @property
    def duration_ms(self) -> float:
        return self.duration_ns / 1_000_000


class SpanSink(Protocol):
    def emit(self, span: SpanRecord) -> None:
        ...


class InMemorySpanSink:
    """Deterministic local sink used for learning, tests, and offline evals."""

    def __init__(self) -> None:
        self._spans: list[SpanRecord] = []

    def emit(self, span: SpanRecord) -> None:
        self._spans.append(span)

    @property
    def spans(self) -> tuple[SpanRecord, ...]:
        return tuple(self._spans)

    def for_trace(self, trace_id: str) -> tuple[SpanRecord, ...]:
        return tuple(
            sorted(
                (span for span in self._spans if span.trace_id == trace_id),
                key=lambda span: (span.start_time_ns, span.end_time_ns),
            )
        )

    def clear(self) -> None:
        self._spans.clear()


class TraceSpan(Protocol):
    trace_id: str
    span_id: str

    def set_attribute(self, key: str, value: Any) -> None:
        ...

    def record_input(self, value: Any) -> None:
        ...

    def record_output(self, value: Any) -> None:
        ...

    def set_status(self, status: SpanStatus, *, error_type: str | None = None) -> None:
        ...


class Tracer(Protocol):
    def span(
        self,
        name: str,
        *,
        kind: SpanKind = "custom",
        attributes: Mapping[str, Any] | None = None,
    ) -> Any:
        ...


@dataclass(slots=True)
class _MutableSpan:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    kind: SpanKind
    policy: TraceCapturePolicy
    start_time_ns: int
    start_monotonic_ns: int
    attributes: dict[str, Any] = field(default_factory=dict)
    input_data: Any | None = None
    output_data: Any | None = None
    status: SpanStatus = "unset"
    error_type: str | None = None

    def set_attribute(self, key: str, value: Any) -> None:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("attribute key must be a non-empty string")
        self.attributes[key] = self.policy.sanitize_attribute(key, value)

    def record_input(self, value: Any) -> None:
        if self.policy.capture_inputs:
            self.input_data = self.policy.sanitize(value)

    def record_output(self, value: Any) -> None:
        if self.policy.capture_outputs:
            self.output_data = self.policy.sanitize(value)

    def set_status(self, status: SpanStatus, *, error_type: str | None = None) -> None:
        if status not in {"unset", "ok", "error"}:
            raise ValueError(f"invalid span status: {status!r}")
        self.status = status
        self.error_type = error_type if status == "error" else None


class LocalTracer:
    """Small nested-span tracer built from first principles.

    A per-tracer ContextVar keeps parent/child relationships correct across
    normal async task propagation. The tracer intentionally stores completed
    spans rather than printing them so the same records can feed debugging and
    deterministic evaluation.
    """

    def __init__(
        self,
        sink: SpanSink | None = None,
        *,
        capture_policy: TraceCapturePolicy | None = None,
        wall_clock_ns: Any = time.time_ns,
        monotonic_ns: Any = time.perf_counter_ns,
    ) -> None:
        self.sink = sink or InMemorySpanSink()
        self.capture_policy = capture_policy or TraceCapturePolicy()
        self._wall_clock_ns = wall_clock_ns
        self._monotonic_ns = monotonic_ns
        self._current_span: contextvars.ContextVar[_MutableSpan | None] = (
            contextvars.ContextVar(
                f"tiny_agent_current_span_{id(self)}",
                default=None,
            )
        )

    @contextmanager
    def span(
        self,
        name: str,
        *,
        kind: SpanKind = "custom",
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[_MutableSpan]:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("span name must be a non-empty string")

        parent = self._current_span.get()
        mutable = _MutableSpan(
            trace_id=parent.trace_id if parent is not None else uuid4().hex,
            span_id=uuid4().hex,
            parent_span_id=parent.span_id if parent is not None else None,
            name=name.strip(),
            kind=kind,
            policy=self.capture_policy,
            start_time_ns=self._wall_clock_ns(),
            start_monotonic_ns=self._monotonic_ns(),
        )
        for key, value in (attributes or {}).items():
            mutable.set_attribute(key, value)

        token = self._current_span.set(mutable)
        try:
            yield mutable
        except BaseException as exc:
            mutable.set_status("error", error_type=type(exc).__name__)
            raise
        finally:
            self._current_span.reset(token)
            if mutable.status == "unset":
                mutable.set_status("ok")
            end_time_ns = self._wall_clock_ns()
            duration_ns = max(0, self._monotonic_ns() - mutable.start_monotonic_ns)
            self.sink.emit(
                SpanRecord(
                    trace_id=mutable.trace_id,
                    span_id=mutable.span_id,
                    parent_span_id=mutable.parent_span_id,
                    name=mutable.name,
                    kind=mutable.kind,
                    status=mutable.status,
                    start_time_ns=mutable.start_time_ns,
                    end_time_ns=max(end_time_ns, mutable.start_time_ns),
                    duration_ns=duration_ns,
                    attributes=dict(mutable.attributes),
                    input_data=mutable.input_data,
                    output_data=mutable.output_data,
                    error_type=mutable.error_type,
                )
            )


def trace_roots(spans: tuple[SpanRecord, ...] | list[SpanRecord]) -> tuple[SpanRecord, ...]:
    return tuple(
        sorted(
            (span for span in spans if span.parent_span_id is None),
            key=lambda span: span.start_time_ns,
        )
    )


def trace_tree_lines(spans: tuple[SpanRecord, ...] | list[SpanRecord]) -> tuple[str, ...]:
    """Render a tiny deterministic tree for terminal/debugging examples."""

    by_parent: dict[str | None, list[SpanRecord]] = {}
    for span in spans:
        by_parent.setdefault(span.parent_span_id, []).append(span)
    for children in by_parent.values():
        children.sort(key=lambda span: (span.start_time_ns, span.end_time_ns))

    lines: list[str] = []

    def visit(span: SpanRecord, depth: int) -> None:
        lines.append(
            f"{'  ' * depth}- {span.name} [{span.kind}] {span.status} "
            f"{span.duration_ms:.2f}ms"
        )
        for child in by_parent.get(span.span_id, []):
            visit(child, depth + 1)

    for root in by_parent.get(None, []):
        visit(root, 0)
    return tuple(lines)


def _sanitize_value(value: Any, *, policy: TraceCapturePolicy, depth: int = 0) -> Any:
    if depth > 6:
        return "<max-depth>"

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, str):
        if len(value) <= policy.max_text_chars:
            return value
        return value[: policy.max_text_chars] + "…<truncated>"

    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (raw_key, raw_value) in enumerate(value.items()):
            if index >= 50:
                result["<truncated-items>"] = len(value) - 50
                break
            key = str(raw_key)
            if policy.is_sensitive_key(key):
                result[key] = "<redacted>"
                continue
            result[key] = _sanitize_value(
                raw_value,
                policy=policy,
                depth=depth + 1,
            )
        return result

    if isinstance(value, (list, tuple)):
        return [
            _sanitize_value(item, policy=policy, depth=depth + 1)
            for item in list(value)[:50]
        ]

    # Avoid repr(value): arbitrary object reprs can contain credentials or raw
    # provider payloads. Unknown objects are described only by type.
    return f"<{type(value).__name__}>"


def json_telemetry_value(value: Any) -> str:
    """Stable JSON helper for backends that only accept scalar attributes."""

    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

"""Local diagnostic spans, not an OTLP implementation or an audit database."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import math
from threading import Lock
import time
from typing import Any, Iterator, Mapping
from uuid import uuid4

# Immutable context-local state avoids one shared mutable nesting stack.
_ACTIVE: ContextVar[tuple[str, str] | None] = ContextVar("stage10_span", default=None)
NUMERIC_KEYS = frozenset({
    "found_count", "selected_count", "attempt", "allowed", "prompt_tokens",
    "completion_tokens", "model_calls", "message_count", "input_chars",
})
LABEL_VALUES = {
    "outcome": frozenset({"ok", "rejected", "failed", "missing", "dropped"}),
    "decision": frozenset({"greeting", "eligible", "ineligible", "insufficient_evidence",
                           "access_denied", "temporarily_unavailable"}),
    "tool": frozenset({"lookup_order", "search_refund_policy", "unknown"}),
}


@dataclass(frozen=True)
class CapturePolicy:
    """Only reviewed counters and enumerated labels are retained; no raw text."""

    def sanitize(self, attributes: Mapping[str, Any]) -> dict[str, Any]:
        safe = {}
        for key, value in attributes.items():
            if key in NUMERIC_KEYS and type(value) in (int, float, bool):
                if math.isfinite(value) and 0 <= value <= 10**12:
                    safe[key] = value
            elif key in LABEL_VALUES and isinstance(value, str):
                if value in LABEL_VALUES[key]:
                    safe[key] = value
        return safe


@dataclass(frozen=True)
class Span:
    span_id: str
    parent_span_id: str | None
    name: str
    sequence: int
    started_at: float
    duration_ms: float
    attributes: dict[str, Any]
    status: str


@dataclass
class Trace:
    run_id: str
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    spans: list[Span] = field(default_factory=list)
    dropped_spans: int = 0
    telemetry_errors: int = 0


class Tracer:
    def __init__(self, trace: Trace, *, capture_policy: CapturePolicy | None = None,
                 max_spans: int = 128, clock=time.perf_counter) -> None:
        if type(max_spans) is not int or max_spans < 1:
            raise ValueError("max_spans must be a positive integer")
        self.trace = trace
        self.policy = capture_policy or CapturePolicy()
        self.max_spans = max_spans
        self.clock = clock
        self._lock = Lock()
        self._sequence = 0

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[dict[str, Any]]:
        # Names are fixed application code, never a question or model-supplied tool name.
        if not isinstance(name, str) or not name or len(name) > 80:
            raise ValueError("invalid application span name")
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
            keep = sequence <= self.max_spans
            if not keep:
                self.trace.dropped_spans += 1
        active = _ACTIVE.get()
        parent = active[1] if active and active[0] == self.trace.trace_id else None
        span_id = uuid4().hex[:16]
        token = _ACTIVE.set((self.trace.trace_id, span_id))
        started, wall_time = self.clock(), time.time()
        mutable = dict(attributes)
        status = "ok"
        try:
            yield mutable
        except BaseException:
            status = "error"
            raise
        finally:
            _ACTIVE.reset(token)
            if keep:
                try:
                    safe = self.policy.sanitize(mutable)
                except Exception:
                    # A broken diagnostic filter must not mask a business exception.
                    safe = {}
                    with self._lock:
                        self.trace.telemetry_errors += 1
                record = Span(span_id, parent, name, sequence, wall_time,
                              max(0.0, (self.clock() - started) * 1000), safe, status)
                with self._lock:
                    self.trace.spans.append(record)


def format_trace(trace: Trace) -> str:
    children: dict[str | None, list[Span]] = {}
    ids = {s.span_id for s in trace.spans}
    for span in sorted(trace.spans, key=lambda s: s.sequence):
        parent = span.parent_span_id if span.parent_span_id in ids else None
        children.setdefault(parent, []).append(span)
    lines = [f"run={trace.run_id} trace={trace.trace_id}"]

    def visit(parent: str | None, prefix: str) -> None:
        group = children.get(parent, [])
        for i, span in enumerate(group):
            last = i == len(group) - 1
            branch = "└── " if last else "├── "
            labels = " ".join(f"{k}={v}" for k, v in span.attributes.items())
            lines.append(f"{prefix}{branch}{span.name} [{span.status}] {labels}".rstrip())
            visit(span.span_id, prefix + ("    " if last else "│   "))

    visit(None, "")
    if trace.dropped_spans or trace.telemetry_errors:
        lines.append(f"INCOMPLETE: dropped={trace.dropped_spans}, errors={trace.telemetry_errors}")
    return "\n".join(lines)


def trace_dict(trace: Trace) -> dict[str, Any]:
    """Export only attributes already filtered at recording time."""
    from dataclasses import asdict
    return asdict(trace)

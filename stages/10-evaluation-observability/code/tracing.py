from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import time
from typing import Any, Iterator, Mapping


SAFE_STRING_ATTRIBUTE_KEYS = frozenset({"error_type"})


@dataclass(frozen=True, slots=True)
class CapturePolicy:
    capture_content: bool = False
    max_text_chars: int = 120

    def sanitize(self, attributes: Mapping[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in attributes.items():
            if isinstance(value, str):
                if key in SAFE_STRING_ATTRIBUTE_KEYS:
                    safe[key] = value
                elif self.capture_content:
                    safe[key] = value[: self.max_text_chars]
                else:
                    safe[f"{key}_sha256"] = hashlib.sha256(
                        value.encode("utf-8")
                    ).hexdigest()[:12]
                    safe[f"{key}_chars"] = len(value)
            else:
                safe[key] = value
        return safe


@dataclass(frozen=True, slots=True)
class Span:
    span_id: str
    parent_span_id: str | None
    name: str
    started_at: float
    duration_ms: float
    attributes: Mapping[str, Any]
    status: str


@dataclass(slots=True)
class Trace:
    run_id: str
    spans: list[Span] = field(default_factory=list)


class Tracer:
    def __init__(self, trace: Trace, *, capture_policy: CapturePolicy | None = None) -> None:
        self.trace = trace
        self.capture_policy = capture_policy or CapturePolicy()
        self._active_span_ids: list[str] = []
        self._next_span_number = 0

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[dict[str, Any]]:
        started = time.perf_counter()
        mutable = dict(attributes)
        self._next_span_number += 1
        span_id = f"{self.trace.run_id}-{self._next_span_number}"
        parent_span_id = self._active_span_ids[-1] if self._active_span_ids else None
        self._active_span_ids.append(span_id)
        status = "ok"
        try:
            yield mutable
        except Exception as exc:
            status = "error"
            mutable["error_type"] = type(exc).__name__
            raise
        finally:
            self._active_span_ids.pop()
            duration_ms = (time.perf_counter() - started) * 1000
            self.trace.spans.append(
                Span(
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    name=name,
                    started_at=started,
                    duration_ms=duration_ms,
                    attributes=self.capture_policy.sanitize(mutable),
                    status=status,
                )
            )


def format_trace(trace: Trace) -> str:
    """Render the recorded parent-child structure without exposing attributes."""

    children: dict[str | None, list[Span]] = {}
    for span in trace.spans:
        children.setdefault(span.parent_span_id, []).append(span)

    lines = [trace.run_id]

    def visit(parent_span_id: str | None, prefix: str) -> None:
        siblings = children.get(parent_span_id, [])
        for index, span in enumerate(siblings):
            is_last = index == len(siblings) - 1
            branch = "└── " if is_last else "├── "
            lines.append(f"{prefix}{branch}{span.name} [{span.status}]")
            visit(span.span_id, prefix + ("    " if is_last else "│   "))

    visit(None, "")
    return "\n".join(lines)

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import time
from typing import Any, Iterator, Mapping


@dataclass(frozen=True, slots=True)
class CapturePolicy:
    capture_content: bool = False
    max_text_chars: int = 120

    def sanitize(self, attributes: Mapping[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in attributes.items():
            if isinstance(value, str):
                if self.capture_content:
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

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[dict[str, Any]]:
        started = time.perf_counter()
        mutable = dict(attributes)
        status = "ok"
        try:
            yield mutable
        except Exception:
            status = "error"
            raise
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            self.trace.spans.append(
                Span(
                    name=name,
                    started_at=started,
                    duration_ms=duration_ms,
                    attributes=self.capture_policy.sanitize(mutable),
                    status=status,
                )
            )

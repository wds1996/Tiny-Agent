from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol, Sequence


EvidenceKind = Literal["local_fulltext", "scholarly_metadata"]
ReportStatus = Literal["completed", "insufficient_evidence", "approval_required"]
_VALID_EVIDENCE_KINDS = frozenset({"local_fulltext", "scholarly_metadata"})
_VALID_REPORT_STATUSES = frozenset({"completed", "insufficient_evidence", "approval_required"})


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    """One user-visible research task.

    ``request_id`` is transport correlation metadata, ``run_id`` is created by
    the Agent runtime, and ``thread_id`` identifies durable conversation state.
    They intentionally remain different concepts.
    """

    question: str
    user_id: str = "demo-user"
    thread_id: str = "demo-thread"
    request_id: str | None = None
    allow_external_search: bool = True
    preferred_style: str | None = None
    remember_style: bool = False
    export_path: str | None = None

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("question must be non-empty")
        if not self.user_id.strip():
            raise ValueError("user_id must be non-empty")
        if not self.thread_id.strip():
            raise ValueError("thread_id must be non-empty")
        if len(self.thread_id) > 255:
            raise ValueError("thread_id must be at most 255 characters for durable backend portability")
        if self.preferred_style is not None and not self.preferred_style.strip():
            raise ValueError("preferred_style must be non-empty when provided")
        if self.remember_style and self.preferred_style is None:
            raise ValueError("remember_style requires preferred_style")


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    kind: EvidenceKind
    title: str
    text: str
    source_url: str | None = None
    locator: str | None = None
    score: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("evidence id must be non-empty")
        if not self.title.strip():
            raise ValueError("evidence title must be non-empty")
        if not self.text.strip():
            raise ValueError("evidence text must be non-empty")
        if self.kind not in _VALID_EVIDENCE_KINDS:
            raise ValueError("unknown evidence kind")

    @property
    def citation(self) -> str:
        return f"[{self.id}]"


@dataclass(frozen=True, slots=True)
class ResearchPlan:
    subquestions: tuple[str, ...]
    use_external_search: bool
    reason: str

    def __post_init__(self) -> None:
        if not self.subquestions:
            raise ValueError("research plan must contain at least one subquestion")
        if any(not item.strip() for item in self.subquestions):
            raise ValueError("research subquestions must be non-empty")
        if not self.reason.strip():
            raise ValueError("plan reason must be non-empty")


@dataclass(frozen=True, slots=True)
class Critique:
    needs_revision: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResearchMetrics:
    local_searches: int = 0
    external_searches: int = 0
    evidence_items: int = 0
    model_calls: int = 0
    revisions: int = 0
    agent_calls: int = 0

    def __post_init__(self) -> None:
        for name in ("local_searches", "external_searches", "evidence_items", "model_calls", "revisions", "agent_calls"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class ResearchReport:
    run_id: str
    status: ReportStatus
    question: str
    answer: str
    evidence: tuple[Evidence, ...]
    citations: tuple[str, ...]
    metrics: ResearchMetrics
    warnings: tuple[str, ...] = ()
    approval_request: Mapping[str, Any] | None = None
    exported_path: str | None = None
    trace_id: str | None = None

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id must be non-empty")
        if self.status not in _VALID_REPORT_STATUSES:
            raise ValueError("unknown report status")
        if not self.question.strip():
            raise ValueError("report question must be non-empty")


class ResearchModel(Protocol):
    """Provider-neutral boundary used by both capstone implementations."""

    def plan(
        self,
        *,
        question: str,
        remembered_context: Mapping[str, Any],
    ) -> ResearchPlan:
        ...

    def synthesize(
        self,
        *,
        question: str,
        evidence: Sequence[Evidence],
        remembered_context: Mapping[str, Any],
        previous_draft: str | None = None,
        critique_notes: Sequence[str] = (),
    ) -> str:
        ...

    def critique(
        self,
        *,
        question: str,
        draft: str,
        evidence: Sequence[Evidence],
    ) -> Critique:
        ...

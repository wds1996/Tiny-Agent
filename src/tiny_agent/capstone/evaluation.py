from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

from .models import ResearchReport

_CITATION_RE = re.compile(r"\[E\d+\]")


@dataclass(frozen=True, slots=True)
class ResearchEvaluation:
    status_ok: bool
    has_local_evidence: bool
    used_citations: tuple[str, ...]
    unknown_citations: tuple[str, ...]
    citation_coverage: float
    grounding_gate_passed: bool
    required_terms_recall: float

    @property
    def passed(self) -> bool:
        return (
            self.status_ok
            and not self.unknown_citations
            and self.grounding_gate_passed
            and self.required_terms_recall >= 1.0
        )


def evaluate_research_report(
    report: ResearchReport,
    *,
    required_terms: Sequence[str] = (),
) -> ResearchEvaluation:
    """Deterministic contract checks before any LLM-as-judge layer."""

    available = set(report.citations)
    used = tuple(dict.fromkeys(_CITATION_RE.findall(report.answer)))
    unknown = tuple(label for label in used if label not in available)
    local = [item for item in report.evidence if item.kind == "local_fulltext"]
    if local:
        grounding_gate = report.status in {"completed", "approval_required"} and any(
            item.citation in used for item in local
        )
    else:
        grounding_gate = report.status == "insufficient_evidence"
    coverage = 1.0 if not available else len(set(used) & available) / len(available)
    answer = report.answer.lower()
    terms = [term.lower() for term in required_terms if term.strip()]
    recall = 1.0 if not terms else sum(term in answer for term in terms) / len(terms)
    return ResearchEvaluation(
        status_ok=report.status in {"completed", "insufficient_evidence", "approval_required"},
        has_local_evidence=bool(local),
        used_citations=used,
        unknown_citations=unknown,
        citation_coverage=coverage,
        grounding_gate_passed=grounding_gate,
        required_terms_recall=recall,
    )

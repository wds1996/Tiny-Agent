from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol, Sequence

from ..decision import StructuredDecisionModel
from .models import Evidence, ResearchReport


_CITATION = re.compile(r"\[E\d+\]")
_SENTENCE = re.compile(r"[^\n.!?]+(?:[.!?]|$)")


@dataclass(frozen=True, slots=True)
class SupportDecision:
    supported: bool
    reason: str


class CitationSupportJudge(Protocol):
    def judge(self, *, claim: str, evidence: Sequence[Evidence]) -> SupportDecision:
        ...


@dataclass(frozen=True, slots=True)
class ClaimSupportResult:
    claim: str
    citations: tuple[str, ...]
    supported: bool
    reason: str


@dataclass(frozen=True, slots=True)
class SemanticGroundingReport:
    claims: tuple[ClaimSupportResult, ...]

    @property
    def support_rate(self) -> float:
        return 1.0 if not self.claims else sum(item.supported for item in self.claims) / len(self.claims)

    @property
    def passed(self) -> bool:
        return all(item.supported for item in self.claims)


class StructuredCitationSupportJudge:
    """Optional semantic grounding layer using a schema-constrained decision model."""

    def __init__(self, model: StructuredDecisionModel) -> None:
        self.model = model

    def judge(self, *, claim: str, evidence: Sequence[Evidence]) -> SupportDecision:
        inventory = "\n\n".join(
            f"{item.citation} kind={item.kind} title={item.title}\n{item.text}"
            for item in evidence
        )
        value = self.model.decide(
            prompt=f"Claim:\n{claim}\n\nCited evidence:\n{inventory}",
            schema_name="citation_support",
            schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "supported": {"type": "boolean"},
                    "reason": {"type": "string", "minLength": 1},
                },
                "required": ["supported", "reason"],
            },
            instructions=(
                "Judge only whether the cited evidence supports the claim at the stated strength. "
                "Metadata-only evidence cannot prove substantive findings. Be conservative."
            ),
        )
        return SupportDecision(bool(value["supported"]), str(value["reason"]))


def evaluate_citation_support(
    report: ResearchReport,
    judge: CitationSupportJudge,
) -> SemanticGroundingReport:
    by_citation = {item.citation: item for item in report.evidence}
    results: list[ClaimSupportResult] = []
    for match in _SENTENCE.finditer(report.answer):
        claim = match.group(0).strip()
        citations = tuple(dict.fromkeys(_CITATION.findall(claim)))
        if not citations:
            continue
        evidence = [by_citation[label] for label in citations if label in by_citation]
        if len(evidence) != len(citations):
            results.append(
                ClaimSupportResult(claim, citations, False, "unknown citation label")
            )
            continue
        decision = judge.judge(claim=claim, evidence=evidence)
        results.append(
            ClaimSupportResult(claim, citations, decision.supported, decision.reason)
        )
    return SemanticGroundingReport(tuple(results))

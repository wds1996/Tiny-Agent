from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from ..approval import ApprovalDecision, ApprovalRequest, resolve_approval
from ..observability import InMemorySpanSink, LocalTracer
from .corpus import LocalResearchCorpus
from .export import MarkdownReportExporter
from .memory import InMemoryResearchMemory, ResearchMemoryStore
from .models import Evidence, ResearchMetrics, ResearchModel, ResearchPlan, ResearchReport, ResearchRequest
from .scholarly import ScholarlySearchClient
from .team import ResearchReviewTeam
from .utils import normalize_evidence


@dataclass(frozen=True, slots=True)
class ResearchAgentConfig:
    max_subquestions: int = 4
    local_top_k: int = 4
    external_top_k: int = 3
    max_evidence: int = 12
    max_revisions: int = 1
    min_local_evidence: int = 1
    min_local_score: float = 0.01

    def __post_init__(self) -> None:
        for name, value in (
            ("max_subquestions", self.max_subquestions),
            ("local_top_k", self.local_top_k),
            ("external_top_k", self.external_top_k),
            ("max_evidence", self.max_evidence),
            ("min_local_evidence", self.min_local_evidence),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_revisions < 0:
            raise ValueError("max_revisions must be non-negative")
        if not 0.0 <= self.min_local_score <= 1.0:
            raise ValueError("min_local_score must satisfy 0 <= value <= 1")


class BaseOpenScholarAgent:
    """Framework-free capstone Agent.

    Model output proposes plans/drafts/critiques. Application code owns budgets,
    retrieval, trust labels, memory policy, approval, export authorization, and
    stop conditions.
    """

    def __init__(
        self,
        *,
        model: ResearchModel,
        corpus: LocalResearchCorpus,
        scholarly_search: ScholarlySearchClient | None = None,
        memory: ResearchMemoryStore | None = None,
        exporter: MarkdownReportExporter | None = None,
        tracer: LocalTracer | None = None,
        config: ResearchAgentConfig | None = None,
    ) -> None:
        self.model = model
        self.corpus = corpus
        self.scholarly_search = scholarly_search
        self.memory = memory or InMemoryResearchMemory()
        self.exporter = exporter
        self.tracer = tracer or LocalTracer(InMemorySpanSink())
        self.config = config or ResearchAgentConfig()
        self.review_team = ResearchReviewTeam(model)

    async def run(
        self,
        request: ResearchRequest,
        *,
        approval_decision: ApprovalDecision | None = None,
    ) -> ResearchReport:
        run_id = uuid4().hex
        counters = {
            "local_searches": 0,
            "external_searches": 0,
            "model_calls": 0,
            "revisions": 0,
            "agent_calls": 0,
        }
        warnings: list[str] = []

        with self.tracer.span(
            "openscholar.run",
            kind="agent",
            attributes={
                "run_id": run_id,
                "thread_id": request.thread_id,
                "external_search_allowed": request.allow_external_search,
            },
        ) as root_span:
            remembered = dict(self.memory.read_context(request.user_id))
            if request.preferred_style is not None:
                remembered["preferred_style"] = request.preferred_style

            with self.tracer.span("plan", kind="workflow"):
                plan = await asyncio.to_thread(
                    self.model.plan,
                    question=request.question,
                    remembered_context=remembered,
                )
                counters["model_calls"] += 1
            plan = self._bound_plan(plan, request)

            evidence, retrieval_warnings, search_counts = await self._gather_evidence(plan)
            warnings.extend(retrieval_warnings)
            counters["local_searches"] += search_counts["local"]
            counters["external_searches"] += search_counts["external"]
            evidence = normalize_evidence(evidence, limit=self.config.max_evidence)
            local_count = sum(item.kind == "local_fulltext" for item in evidence)

            if local_count < self.config.min_local_evidence:
                answer = (
                    "I found insufficient local full-text evidence to support a substantive answer. "
                    "External scholarly metadata may identify related works, but metadata alone is not "
                    "treated as evidence of a paper's findings."
                )
                status = "insufficient_evidence"
            else:
                with self.tracer.span("synthesize", kind="model"):
                    answer = await asyncio.to_thread(
                        self.model.synthesize,
                        question=request.question,
                        evidence=evidence,
                        remembered_context=remembered,
                    )
                    counters["model_calls"] += 1

                for _ in range(self.config.max_revisions):
                    with self.tracer.span("review.team", kind="agent"):
                        review = await self.review_team.review(
                            question=request.question,
                            draft=answer,
                            evidence=evidence,
                            remembered_context=remembered,
                        )
                    counters["model_calls"] += review.model_calls
                    counters["agent_calls"] += review.agent_calls
                    counters["revisions"] += review.revisions
                    for warning in ("critic_failed", "critic_invalid_output", "writer_failed"):
                        if warning in review.notes:
                            warnings.append(warning)
                    answer = review.draft
                    if not review.needs_revision or review.revisions == 0:
                        break
                status = "completed"

            if request.preferred_style is not None and request.remember_style:
                with self.tracer.span("memory.write", kind="memory"):
                    decision = self.memory.write_style(
                        user_id=request.user_id,
                        style=request.preferred_style,
                        explicit_user_request=True,
                    )
                if not decision.store:
                    warnings.append("memory_write_denied")

            report = ResearchReport(
                run_id=run_id,
                status=status,  # type: ignore[arg-type]
                question=request.question,
                answer=answer,
                evidence=tuple(evidence),
                citations=tuple(item.citation for item in evidence),
                metrics=ResearchMetrics(
                    local_searches=counters["local_searches"],
                    external_searches=counters["external_searches"],
                    evidence_items=len(evidence),
                    model_calls=counters["model_calls"],
                    revisions=counters["revisions"],
                    agent_calls=counters["agent_calls"],
                ),
                warnings=tuple(warnings),
                trace_id=root_span.trace_id,
            )
            if request.export_path is not None:
                report = self._handle_export(
                    report,
                    requested_path=request.export_path,
                    decision=approval_decision,
                )
            root_span.set_attribute("status", report.status)
            root_span.set_attribute("evidence_items", len(report.evidence))
            return report

    def _bound_plan(self, plan: ResearchPlan, request: ResearchRequest) -> ResearchPlan:
        subquestions = tuple(plan.subquestions[: self.config.max_subquestions])
        use_external = (
            request.allow_external_search
            and self.scholarly_search is not None
            and plan.use_external_search
        )
        return ResearchPlan(subquestions=subquestions, use_external_search=use_external, reason=plan.reason)

    async def _gather_evidence(
        self,
        plan: ResearchPlan,
    ) -> tuple[list[Evidence], list[str], dict[str, int]]:
        warnings: list[str] = []
        counts = {"local": 0, "external": 0}

        async def local_search(query: str) -> list[Evidence]:
            counts["local"] += 1
            with self.tracer.span("retrieve.local", kind="retrieval"):
                results = await asyncio.to_thread(
                    self.corpus.search,
                    query,
                    top_k=self.config.local_top_k,
                )
            return [item for item in results if item.score >= self.config.min_local_score]

        async def external_search(query: str) -> list[Evidence]:
            assert self.scholarly_search is not None
            counts["external"] += 1
            try:
                with self.tracer.span("retrieve.crossref", kind="tool"):
                    return list(
                        await asyncio.to_thread(
                            self.scholarly_search.search,
                            query,
                            limit=self.config.external_top_k,
                        )
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                warnings.append(f"external_search_failed:{type(exc).__name__}")
                return []

        tasks: list[asyncio.Task[list[Evidence]]] = []
        for subquestion in plan.subquestions:
            tasks.append(asyncio.create_task(local_search(subquestion)))
            if plan.use_external_search:
                tasks.append(asyncio.create_task(external_search(subquestion)))
        batches = await asyncio.gather(*tasks)
        return [item for batch in batches for item in batch], warnings, counts

    def _handle_export(
        self,
        report: ResearchReport,
        *,
        requested_path: str,
        decision: ApprovalDecision | None,
    ) -> ResearchReport:
        approval = ApprovalRequest(
            action="export_research_report",
            arguments={"relative_path": requested_path},
            reason="Writing a durable report is an external side effect.",
            risk="medium",
        )
        if decision is None:
            return _replace_report(
                report,
                status="approval_required",
                approval_request=approval.to_interrupt_payload(),
            )
        resolution = resolve_approval(approval, decision)
        if not resolution.approved:
            return _with_warning(report, "export_rejected")
        if self.exporter is None:
            return _with_warning(report, "export_unavailable")
        assert resolution.arguments is not None
        relative_path = resolution.arguments.get("relative_path")
        if not isinstance(relative_path, str):
            return _with_warning(report, "export_invalid_arguments")
        try:
            exported = self.exporter.export(report, relative_path)
        except Exception as exc:
            return _with_warning(report, f"export_failed:{type(exc).__name__}")
        return _replace_report(report, exported_path=exported)


def _replace_report(report: ResearchReport, **changes: Any) -> ResearchReport:
    values: dict[str, Any] = {
        "run_id": report.run_id,
        "status": report.status,
        "question": report.question,
        "answer": report.answer,
        "evidence": report.evidence,
        "citations": report.citations,
        "metrics": report.metrics,
        "warnings": report.warnings,
        "approval_request": report.approval_request,
        "exported_path": report.exported_path,
        "trace_id": report.trace_id,
    }
    values.update(changes)
    return ResearchReport(**values)


def _with_warning(report: ResearchReport, warning: str) -> ResearchReport:
    return _replace_report(report, warnings=(*report.warnings, warning))

from __future__ import annotations

import asyncio
from typing import Any, Mapping, TypedDict
from uuid import uuid4

from ..approval import ApprovalDecision, ApprovalRequest, resolve_approval
from ..observability import InMemorySpanSink, LocalTracer
from .base_agent import ResearchAgentConfig
from .corpus import LocalResearchCorpus
from .export import MarkdownReportExporter
from .memory import InMemoryResearchMemory, ResearchMemoryStore
from .models import ResearchModel, ResearchReport, ResearchRequest
from .scholarly import ScholarlySearchClient
from .team import ResearchReviewTeam
from .utils import bump, evidence_from_dict, evidence_to_dict, metrics_from_dict, normalize_evidence


class OpenScholarGraphState(TypedDict, total=False):
    run_id: str
    trace_id: str
    question: str
    user_id: str
    thread_id: str
    request_id: str | None
    allow_external_search: bool
    preferred_style: str | None
    remember_style: bool
    export_path: str | None
    remembered_context: dict[str, Any]
    plan: dict[str, Any]
    evidence: list[dict[str, Any]]
    answer: str
    warnings: list[str]
    metrics: dict[str, int]
    status: str
    exported_path: str | None


class LangGraphOpenScholarAgent:
    """Framework version: same domain services, LangGraph orchestration plumbing."""

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
        checkpointer: Any | None = None,
    ) -> None:
        self.model = model
        self.corpus = corpus
        self.scholarly_search = scholarly_search
        self.memory = memory or InMemoryResearchMemory()
        self.exporter = exporter
        self.tracer = tracer or LocalTracer(InMemorySpanSink())
        self.config = config or ResearchAgentConfig()
        self.review_team = ResearchReviewTeam(model)
        self.graph = self._build_graph(checkpointer)

    def _build_graph(self, checkpointer: Any | None):
        try:
            from langgraph.checkpoint.memory import InMemorySaver
            from langgraph.graph import END, START, StateGraph
            from langgraph.types import interrupt
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "LangGraph capstone requires: python -m pip install -e '.[stage11]'"
            ) from exc

        saver = checkpointer or InMemorySaver()

        def load_memory(state: OpenScholarGraphState) -> dict[str, Any]:
            with self.tracer.span("graph.memory.read", kind="memory"):
                remembered = dict(self.memory.read_context(state["user_id"]))
            if state.get("preferred_style"):
                remembered["preferred_style"] = state["preferred_style"]
            return {"remembered_context": remembered}

        def plan_node(state: OpenScholarGraphState) -> dict[str, Any]:
            with self.tracer.span("graph.plan", kind="model"):
                plan = self.model.plan(
                    question=state["question"],
                    remembered_context=state.get("remembered_context", {}),
                )
            return {
                "plan": {
                    "subquestions": list(plan.subquestions[: self.config.max_subquestions]),
                    "use_external_search": bool(
                        state.get("allow_external_search", True)
                        and self.scholarly_search is not None
                        and plan.use_external_search
                    ),
                    "reason": plan.reason,
                },
                "metrics": bump(state.get("metrics", {}), model_calls=1),
            }

        async def retrieve_node(state: OpenScholarGraphState) -> dict[str, Any]:
            plan = state["plan"]
            warnings = list(state.get("warnings", []))
            counts = {"local": 0, "external": 0}

            async def local(query: str):
                counts["local"] += 1
                with self.tracer.span("graph.retrieve.local", kind="retrieval"):
                    results = await asyncio.to_thread(
                        self.corpus.search,
                        query,
                        top_k=self.config.local_top_k,
                    )
                return [item for item in results if item.score >= self.config.min_local_score]

            async def external(query: str):
                assert self.scholarly_search is not None
                counts["external"] += 1
                try:
                    with self.tracer.span("graph.retrieve.crossref", kind="tool"):
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

            tasks = []
            for subquestion in plan["subquestions"]:
                tasks.append(asyncio.create_task(local(str(subquestion))))
                if plan["use_external_search"]:
                    tasks.append(asyncio.create_task(external(str(subquestion))))
            batches = await asyncio.gather(*tasks)
            evidence = normalize_evidence(
                [item for batch in batches for item in batch],
                limit=self.config.max_evidence,
            )
            fulltext_count = sum(item.kind == "local_fulltext" for item in evidence)
            return {
                "evidence": [evidence_to_dict(item) for item in evidence],
                "warnings": warnings,
                "metrics": bump(
                    state.get("metrics", {}),
                    local_searches=counts["local"],
                    external_searches=counts["external"],
                    evidence_items=len(evidence),
                ),
                "status": (
                    "insufficient_evidence"
                    if fulltext_count < self.config.min_local_evidence
                    else "running"
                ),
            }

        def route_after_retrieve(state: OpenScholarGraphState) -> str:
            return "insufficient" if state.get("status") == "insufficient_evidence" else "draft"

        def insufficient_node(state: OpenScholarGraphState) -> dict[str, Any]:
            return {
                "answer": (
                    "I found insufficient local full-text evidence to support a substantive answer. "
                    "External scholarly metadata may identify related works, but metadata alone is not "
                    "treated as evidence of a paper's findings."
                ),
                "status": "insufficient_evidence",
            }

        def draft_node(state: OpenScholarGraphState) -> dict[str, Any]:
            evidence = [evidence_from_dict(item) for item in state.get("evidence", [])]
            with self.tracer.span("graph.synthesize", kind="model"):
                answer = self.model.synthesize(
                    question=state["question"],
                    evidence=evidence,
                    remembered_context=state.get("remembered_context", {}),
                )
            return {
                "answer": answer,
                "status": "completed",
                "metrics": bump(state.get("metrics", {}), model_calls=1),
            }

        async def review_node(state: OpenScholarGraphState) -> dict[str, Any]:
            if self.config.max_revisions <= 0:
                return {}
            evidence = [evidence_from_dict(item) for item in state.get("evidence", [])]
            answer = state["answer"]
            warnings = list(state.get("warnings", []))
            metrics = dict(state.get("metrics", {}))
            for _ in range(self.config.max_revisions):
                with self.tracer.span("graph.review.team", kind="agent"):
                    review = await self.review_team.review(
                        question=state["question"],
                        draft=answer,
                        evidence=evidence,
                        remembered_context=state.get("remembered_context", {}),
                    )
                metrics = bump(
                    metrics,
                    model_calls=review.model_calls,
                    agent_calls=review.agent_calls,
                    revisions=review.revisions,
                )
                answer = review.draft
                for warning in ("critic_failed", "critic_invalid_output", "writer_failed"):
                    if warning in review.notes:
                        warnings.append(warning)
                if not review.needs_revision or review.revisions == 0:
                    break
            return {"answer": answer, "warnings": warnings, "metrics": metrics}

        def remember_node(state: OpenScholarGraphState) -> dict[str, Any]:
            style = state.get("preferred_style")
            if not style or not state.get("remember_style"):
                return {}
            with self.tracer.span("graph.memory.write", kind="memory"):
                decision = self.memory.write_style(
                    user_id=state["user_id"],
                    style=style,
                    explicit_user_request=True,
                )
            if decision.store:
                return {}
            return {"warnings": [*state.get("warnings", []), "memory_write_denied"]}

        def route_after_memory(state: OpenScholarGraphState) -> str:
            return "approval_export" if state.get("export_path") else "finalize"

        async def approval_export_node(state: OpenScholarGraphState) -> dict[str, Any]:
            requested_path = state.get("export_path")
            if not requested_path:
                return {}
            approval = ApprovalRequest(
                action="export_research_report",
                arguments={"relative_path": requested_path},
                reason="Writing a durable report is an external side effect.",
                risk="medium",
            )
            # Keep the interrupt in the async runnable context. On Python 3.10,
            # a synchronous node may run in an executor thread where LangGraph's
            # runnable context is not available. No side effect occurs before
            # interrupt(): this node can restart safely when resumed.
            decision_payload = interrupt(approval.to_interrupt_payload())
            decision = ApprovalDecision.from_payload(decision_payload)
            resolution = resolve_approval(approval, decision)
            warnings = list(state.get("warnings", []))
            if not resolution.approved:
                return {"warnings": [*warnings, "export_rejected"]}
            if self.exporter is None:
                return {"warnings": [*warnings, "export_unavailable"]}
            assert resolution.arguments is not None
            relative_path = resolution.arguments.get("relative_path")
            if not isinstance(relative_path, str):
                return {"warnings": [*warnings, "export_invalid_arguments"]}
            try:
                exported = self.exporter.export(self._report_from_state(state), relative_path)
            except Exception as exc:
                return {"warnings": [*warnings, f"export_failed:{type(exc).__name__}"]}
            return {"exported_path": exported}

        def finalize_node(state: OpenScholarGraphState) -> dict[str, Any]:
            return {"status": "completed"} if state.get("status") == "running" else {}

        builder = StateGraph(OpenScholarGraphState)
        for name, node in (
            ("load_memory", load_memory),
            ("plan", plan_node),
            ("retrieve", retrieve_node),
            ("insufficient", insufficient_node),
            ("draft", draft_node),
            ("review", review_node),
            ("remember", remember_node),
            ("approval_export", approval_export_node),
            ("finalize", finalize_node),
        ):
            builder.add_node(name, node)
        builder.add_edge(START, "load_memory")
        builder.add_edge("load_memory", "plan")
        builder.add_edge("plan", "retrieve")
        builder.add_conditional_edges(
            "retrieve",
            route_after_retrieve,
            {"insufficient": "insufficient", "draft": "draft"},
        )
        builder.add_edge("insufficient", "remember")
        builder.add_edge("draft", "review")
        builder.add_edge("review", "remember")
        builder.add_conditional_edges(
            "remember",
            route_after_memory,
            {"approval_export": "approval_export", "finalize": "finalize"},
        )
        builder.add_edge("approval_export", "finalize")
        builder.add_edge("finalize", END)
        return builder.compile(checkpointer=saver)

    async def run(self, request: ResearchRequest) -> ResearchReport:
        initial: OpenScholarGraphState = {
            "run_id": uuid4().hex,
            "question": request.question,
            "user_id": request.user_id,
            "thread_id": request.thread_id,
            "request_id": request.request_id,
            "allow_external_search": request.allow_external_search,
            "preferred_style": request.preferred_style,
            "remember_style": request.remember_style,
            "export_path": request.export_path,
            "warnings": [],
            "metrics": {
                "local_searches": 0,
                "external_searches": 0,
                "evidence_items": 0,
                "model_calls": 0,
                "revisions": 0,
                "agent_calls": 0,
            },
            "status": "running",
        }
        config = {"configurable": {"thread_id": request.thread_id}}
        with self.tracer.span(
            "openscholar.langgraph",
            kind="agent",
            attributes={"thread_id": request.thread_id, "run_id": initial["run_id"]},
        ) as root_span:
            initial["trace_id"] = root_span.trace_id
            result = await self.graph.ainvoke(initial, config=config)
        return self._result_to_report(result)

    async def resume(self, *, thread_id: str, decision: ApprovalDecision) -> ResearchReport:
        try:
            from langgraph.types import Command
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("LangGraph is not installed") from exc
        payload = {
            "outcome": decision.outcome,
            "edited_arguments": decision.edited_arguments,
            "feedback": decision.feedback,
        }
        config = {"configurable": {"thread_id": thread_id}}
        result = await self.graph.ainvoke(Command(resume=payload), config=config)
        return self._result_to_report(result)

    def _result_to_report(self, state: Mapping[str, Any]) -> ResearchReport:
        interrupts = state.get("__interrupt__")
        if interrupts:
            first = interrupts[0]
            payload = getattr(first, "value", first)
            base = self._report_from_state(state)
            return ResearchReport(
                run_id=base.run_id,
                status="approval_required",
                question=base.question,
                answer=base.answer,
                evidence=base.evidence,
                citations=base.citations,
                metrics=base.metrics,
                warnings=base.warnings,
                approval_request=(payload if isinstance(payload, Mapping) else {"value": payload}),
                exported_path=base.exported_path,
                trace_id=base.trace_id,
            )
        return self._report_from_state(state)

    def _report_from_state(self, state: Mapping[str, Any]) -> ResearchReport:
        evidence = tuple(evidence_from_dict(item) for item in state.get("evidence", []))
        status = str(state.get("status") or "completed")
        if status not in {"completed", "insufficient_evidence", "approval_required"}:
            status = "completed"
        return ResearchReport(
            run_id=str(state.get("run_id") or "unknown"),
            status=status,  # type: ignore[arg-type]
            question=str(state.get("question") or ""),
            answer=str(state.get("answer") or ""),
            evidence=evidence,
            citations=tuple(item.citation for item in evidence),
            metrics=metrics_from_dict(state.get("metrics", {})),
            warnings=tuple(str(item) for item in state.get("warnings", [])),
            exported_path=state.get("exported_path"),
            trace_id=state.get("trace_id"),
        )

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tiny_agent.approval import ApprovalDecision
from tiny_agent.capstone import (
    BaseOpenScholarAgent,
    CorpusDocument,
    HeuristicResearchModel,
    InMemoryResearchMemory,
    LocalResearchCorpus,
    MarkdownReportExporter,
    ResearchAgentConfig,
    ResearchRequest,
    evaluate_research_report,
)


def corpus() -> LocalResearchCorpus:
    return LocalResearchCorpus(
        [
            CorpusDocument(
                id="react",
                title="ReAct note",
                text=(
                    "ReAct combines reasoning traces and environment actions. "
                    "The agent reasons, acts with tools, observes results, and continues the trajectory."
                ),
            ),
            CorpusDocument(
                id="rag",
                title="RAG note",
                text=(
                    "Retrieval augmented generation retrieves external evidence from a corpus before generation. "
                    "Retrieval quality and answer grounding are separate concerns."
                ),
            ),
        ],
        chunk_size=50,
        overlap=5,
    )


def test_request_requires_style_when_remembering() -> None:
    with pytest.raises(ValueError):
        ResearchRequest(question="x", remember_style=True)


def test_unrelated_zero_score_does_not_become_substantive_evidence() -> None:
    agent = BaseOpenScholarAgent(
        model=HeuristicResearchModel(),
        corpus=corpus(),
        config=ResearchAgentConfig(min_local_score=1.0, min_local_evidence=1),
    )
    report = asyncio.run(
        agent.run(
            ResearchRequest(
                question="What evidence exists about an unrelated astronomy concept?",
                allow_external_search=False,
            )
        )
    )
    assert report.status == "insufficient_evidence"
    assert report.evidence == ()
    assert report.metrics.model_calls == 1  # planning only; no unsupported synthesis


def test_base_agent_returns_grounded_report() -> None:
    agent = BaseOpenScholarAgent(
        model=HeuristicResearchModel(),
        corpus=corpus(),
        config=ResearchAgentConfig(min_local_score=0.01, min_local_evidence=1),
    )
    report = asyncio.run(
        agent.run(
            ResearchRequest(
                question="How do ReAct and retrieval augmented generation differ?",
                allow_external_search=False,
            )
        )
    )
    evaluation = evaluate_research_report(report, required_terms=("reason", "retriev"))
    assert report.status == "completed"
    assert any(item.kind == "local_fulltext" for item in report.evidence)
    assert evaluation.grounding_gate_passed
    assert not evaluation.unknown_citations
    assert evaluation.passed


def test_memory_requires_explicit_request() -> None:
    memory = InMemoryResearchMemory()
    denied = memory.write_style(user_id="u", style="brief", explicit_user_request=False)
    assert not denied.store
    allowed = memory.write_style(user_id="u", style="brief", explicit_user_request=True)
    assert allowed.store
    assert memory.read_context("u")["preferred_style"] == "brief"


def test_base_export_requires_approval_and_confines_path(tmp_path: Path) -> None:
    exporter = MarkdownReportExporter(tmp_path)
    agent = BaseOpenScholarAgent(
        model=HeuristicResearchModel(),
        corpus=corpus(),
        exporter=exporter,
        config=ResearchAgentConfig(max_revisions=0, min_local_score=0.01),
    )
    request = ResearchRequest(
        question="What is retrieval augmented generation?",
        allow_external_search=False,
        export_path="reports/rag.md",
    )
    paused = asyncio.run(agent.run(request))
    assert paused.status == "approval_required"
    assert paused.exported_path is None

    completed = asyncio.run(
        agent.run(request, approval_decision=ApprovalDecision(outcome="approve"))
    )
    assert completed.exported_path is not None
    assert Path(completed.exported_path).is_file()

    malicious = ResearchRequest(
        question="What is ReAct?",
        allow_external_search=False,
        export_path="../escape.md",
    )
    rejected = asyncio.run(
        agent.run(malicious, approval_decision=ApprovalDecision(outcome="approve"))
    )
    assert rejected.exported_path is None
    assert any(item.startswith("export_failed:") for item in rejected.warnings)
    assert not (tmp_path.parent / "escape.md").exists()


def test_evaluator_detects_unknown_citation() -> None:
    agent = BaseOpenScholarAgent(
        model=HeuristicResearchModel(),
        corpus=corpus(),
        config=ResearchAgentConfig(max_revisions=0, min_local_score=0.01),
    )
    report = asyncio.run(
        agent.run(ResearchRequest(question="What is ReAct?", allow_external_search=False))
    )
    mutated = type(report)(
        run_id=report.run_id,
        status=report.status,
        question=report.question,
        answer=report.answer + " invented [E999]",
        evidence=report.evidence,
        citations=report.citations,
        metrics=report.metrics,
        warnings=report.warnings,
        trace_id=report.trace_id,
    )
    evaluation = evaluate_research_report(mutated)
    assert evaluation.unknown_citations == ("[E999]",)
    assert not evaluation.passed

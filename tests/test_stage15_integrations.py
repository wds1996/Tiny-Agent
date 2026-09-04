from __future__ import annotations

import asyncio
import runpy
import sys
from pathlib import Path

import pytest

# The core package deliberately has no LangGraph/FastAPI/A2A/MCP dependency.
# In the lightweight core job this module is skipped; the dedicated Stage 15
# workflow installs the extra and executes the full integration suite.
pytest.importorskip("langgraph")
pytest.importorskip("fastapi")
pytest.importorskip("mcp")
pytest.importorskip("a2a")
pytest.importorskip("starlette")

from starlette.testclient import TestClient

from tiny_agent.approval import ApprovalDecision
from tiny_agent.capstone import (
    BaseOpenScholarAgent,
    CorpusDocument,
    HeuristicResearchModel,
    LocalResearchCorpus,
    MarkdownReportExporter,
    ResearchAgentConfig,
    ResearchRequest,
)
from tiny_agent.capstone.langgraph_agent import LangGraphOpenScholarAgent
from tiny_agent.integrations.openscholar_api import build_openscholar_app


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "stages" / "15-capstone-enterprise-agent"
CODE = STAGE / "code"


def corpus() -> LocalResearchCorpus:
    return LocalResearchCorpus(
        [
            CorpusDocument(
                id="react",
                title="ReAct note",
                text="ReAct interleaves reasoning traces, actions, tool use, and observations in an Agent trajectory.",
            ),
            CorpusDocument(
                id="rag",
                title="RAG note",
                text="Retrieval augmented generation retrieves corpus evidence before a generator writes the grounded answer.",
            ),
        ],
        chunk_size=40,
        overlap=4,
    )


def config() -> ResearchAgentConfig:
    return ResearchAgentConfig(
        max_subquestions=2,
        local_top_k=2,
        max_evidence=4,
        max_revisions=1,
        min_local_evidence=1,
        min_local_score=0.01,
    )


def test_langgraph_agent_completes() -> None:
    agent = LangGraphOpenScholarAgent(
        model=HeuristicResearchModel(),
        corpus=corpus(),
        config=config(),
    )
    report = asyncio.run(
        agent.run(
            ResearchRequest(
                question="Compare ReAct and retrieval augmented generation.",
                allow_external_search=False,
                thread_id="stage15-test-complete",
            )
        )
    )
    assert report.status == "completed"
    assert report.evidence
    assert report.trace_id


def test_langgraph_hitl_resume(tmp_path: Path) -> None:
    agent = LangGraphOpenScholarAgent(
        model=HeuristicResearchModel(),
        corpus=corpus(),
        exporter=MarkdownReportExporter(tmp_path),
        config=ResearchAgentConfig(max_revisions=0, min_local_score=0.01),
    )
    thread_id = "stage15-test-hitl"
    paused = asyncio.run(
        agent.run(
            ResearchRequest(
                question="What is ReAct?",
                allow_external_search=False,
                thread_id=thread_id,
                export_path="reports/react.md",
            )
        )
    )
    assert paused.status == "approval_required"
    assert paused.approval_request is not None
    assert not (tmp_path / "reports" / "react.md").exists()

    completed = asyncio.run(
        agent.resume(thread_id=thread_id, decision=ApprovalDecision(outcome="approve"))
    )
    assert completed.status == "completed"
    assert completed.exported_path is not None
    assert (tmp_path / "reports" / "react.md").exists()


def test_fastapi_exposes_both_implementations() -> None:
    shared_corpus = corpus()
    base = BaseOpenScholarAgent(
        model=HeuristicResearchModel(), corpus=shared_corpus, config=config()
    )
    graph = LangGraphOpenScholarAgent(
        model=HeuristicResearchModel(), corpus=shared_corpus, config=config()
    )
    app = build_openscholar_app(base_agent=base, graph_agent=graph)
    with TestClient(app) as client:
        assert client.get("/livez").status_code == 200
        payload = {
            "question": "What is retrieval augmented generation?",
            "allow_external_search": False,
            "thread_id": "http-stage15",
        }
        base_response = client.post("/v1/research/base", json=payload)
        graph_response = client.post(
            "/v1/research/langgraph",
            json={**payload, "thread_id": "http-stage15-graph"},
        )
    assert base_response.status_code == 200
    assert graph_response.status_code == 200
    assert base_response.json()["status"] == "completed"
    assert graph_response.json()["status"] == "completed"


def run_example(name: str):
    sys.path.insert(0, str(CODE))
    try:
        return runpy.run_path(str(CODE / name), run_name=f"stage15_{name}")
    finally:
        sys.path.pop(0)


def test_mcp_example_builds_and_searches() -> None:
    namespace = run_example("mcp_server.py")
    result = namespace["search_corpus"]("retrieval augmented generation", top_k=2)
    assert result["results"]
    assert result["results"][0]["kind"] == "local_fulltext"


def test_a2a_example_builds_routes() -> None:
    namespace = run_example("a2a_server.py")
    app = namespace["build_app"]()
    assert app.routes


def test_api_example_exports_app_object() -> None:
    namespace = run_example("api_app.py")
    assert "app" in namespace

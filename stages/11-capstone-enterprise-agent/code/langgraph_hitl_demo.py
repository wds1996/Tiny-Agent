from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from tiny_agent.approval import ApprovalDecision
from tiny_agent.capstone import HeuristicResearchModel, MarkdownReportExporter, ResearchAgentConfig, ResearchRequest
from tiny_agent.capstone.langgraph_agent import LangGraphOpenScholarAgent

from common import synthetic_corpus


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="openscholar-hitl-") as tmp:
        agent = LangGraphOpenScholarAgent(
            model=HeuristicResearchModel(),
            corpus=synthetic_corpus(),
            exporter=MarkdownReportExporter(tmp),
            config=ResearchAgentConfig(max_revisions=0, min_local_score=0.01),
        )
        thread_id = "stage11-hitl-demo"
        paused = await agent.run(
            ResearchRequest(
                question="What is retrieval-augmented generation?",
                allow_external_search=False,
                thread_id=thread_id,
                export_path="reports/rag.md",
            )
        )
        print("Paused status:", paused.status)
        print("Approval payload:", paused.approval_request)
        assert paused.status == "approval_required"

        completed = await agent.resume(
            thread_id=thread_id,
            decision=ApprovalDecision(outcome="approve"),
        )
        print("Resumed status:", completed.status)
        print("Exported path:", completed.exported_path)
        assert completed.exported_path is not None
        assert Path(completed.exported_path).exists()


if __name__ == "__main__":
    asyncio.run(main())

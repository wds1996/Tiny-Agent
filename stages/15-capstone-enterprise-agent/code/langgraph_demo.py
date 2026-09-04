from __future__ import annotations

import asyncio
from dataclasses import asdict

from tiny_agent.capstone import HeuristicResearchModel, ResearchAgentConfig, ResearchRequest, evaluate_research_report
from tiny_agent.capstone.langgraph_agent import LangGraphOpenScholarAgent

from common import synthetic_corpus


async def main() -> None:
    agent = LangGraphOpenScholarAgent(
        model=HeuristicResearchModel(),
        corpus=synthetic_corpus(),
        config=ResearchAgentConfig(
            max_subquestions=3,
            local_top_k=3,
            max_evidence=8,
            max_revisions=1,
            min_local_evidence=1,
            min_local_score=0.01,
        ),
    )
    report = await agent.run(
        ResearchRequest(
            question="How do ReAct and Reflexion change an Agent trajectory?",
            allow_external_search=False,
            thread_id="stage15-langgraph-demo",
        )
    )
    print("=== LANGGRAPH OPEN-SCHOLAR ===")
    print(report.answer)
    print("\nMetrics:", asdict(report.metrics))
    print("Evaluation:", asdict(evaluate_research_report(report)))
    print("Trace ID:", report.trace_id)


if __name__ == "__main__":
    asyncio.run(main())

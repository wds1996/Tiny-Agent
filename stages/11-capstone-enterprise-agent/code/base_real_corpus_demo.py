from __future__ import annotations

import asyncio

from tiny_agent.capstone import BaseOpenScholarAgent, HeuristicResearchModel, ResearchAgentConfig, ResearchRequest

from common import generated_corpus


async def main() -> None:
    agent = BaseOpenScholarAgent(
        model=HeuristicResearchModel(),
        corpus=generated_corpus(),
        config=ResearchAgentConfig(
            max_subquestions=3,
            local_top_k=4,
            max_evidence=10,
            max_revisions=1,
            min_local_evidence=1,
            min_local_score=0.01,
        ),
    )
    report = await agent.run(
        ResearchRequest(
            question="Compare ReAct, RAG, and Reflexion as mechanisms for improving language-model Agents.",
            allow_external_search=False,
        )
    )
    print(report.answer)
    print("\nEvidence inventory:")
    for item in report.evidence:
        print(f"- {item.citation} {item.title} ({item.locator}) score={item.score:.3f}")


if __name__ == "__main__":
    asyncio.run(main())

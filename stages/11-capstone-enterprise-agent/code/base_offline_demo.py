from __future__ import annotations

import asyncio
from dataclasses import asdict

from tiny_agent.capstone import ResearchRequest, evaluate_research_report

from common import offline_base_agent


async def main() -> None:
    agent = offline_base_agent()
    report = await agent.run(
        ResearchRequest(
            question="How do ReAct and retrieval-augmented generation address different Agent limitations?",
            allow_external_search=False,
            preferred_style="concise",
        )
    )
    evaluation = evaluate_research_report(report, required_terms=("reason", "retriev"))

    print("=== BASE OPEN-SCHOLAR ===")
    print(report.answer)
    print("\nEvidence:")
    for item in report.evidence:
        print(f"  {item.citation} {item.kind} score={item.score:.3f} {item.title}")
    print("\nMetrics:", asdict(report.metrics))
    print("Evaluation:", asdict(evaluation))
    print("Trace ID:", report.trace_id)


if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

import asyncio
from dataclasses import asdict

from tiny_agent.capstone import ResearchRequest, evaluate_research_report

from common import offline_base_agent


async def main() -> None:
    agent = offline_base_agent()
    cases = [
        (
            "react-rag",
            ResearchRequest(
                question="How do ReAct and retrieval-augmented generation address different limitations?",
                allow_external_search=False,
            ),
            ("reason", "retriev"),
        ),
        (
            "reflexion",
            ResearchRequest(
                question="What role does verbal reflection play in Reflexion?",
                allow_external_search=False,
            ),
            ("reflection",),
        ),
    ]

    passed = 0
    for name, request, required_terms in cases:
        report = await agent.run(request)
        evaluation = evaluate_research_report(report, required_terms=required_terms)
        print(f"[{name}]", asdict(evaluation))
        passed += int(evaluation.passed)

    print(f"Passed {passed}/{len(cases)} deterministic capstone checks")
    if passed != len(cases):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio

from tiny_agent.capstone import ResearchRequest
from tiny_agent.capstone.semantic_evaluation import SupportDecision, evaluate_citation_support

from common import offline_base_agent, synthetic_corpus


class DemoJudge:
    def judge(self, *, claim, evidence):
        cited_text = " ".join(item.text.lower() for item in evidence)
        words = [word.strip(".,[]").lower() for word in claim.split() if len(word) > 5]
        supported = any(word in cited_text for word in words)
        return SupportDecision(supported, "offline lexical demonstration")


report = asyncio.run(
    offline_base_agent(corpus=synthetic_corpus()).run(
        ResearchRequest(
            question="How do ReAct and retrieval-augmented generation differ?",
            allow_external_search=False,
        )
    )
)
semantic = evaluate_citation_support(report, DemoJudge())
print("support rate:", semantic.support_rate)
for result in semantic.claims:
    print(result.supported, result.citations, result.claim)

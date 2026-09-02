from __future__ import annotations

import uvicorn

from tiny_agent.capstone import HeuristicResearchModel, ResearchAgentConfig
from tiny_agent.capstone.langgraph_agent import LangGraphOpenScholarAgent
from tiny_agent.integrations.openscholar_api import build_openscholar_app

from common import offline_base_agent, synthetic_corpus

corpus = synthetic_corpus()
base_agent = offline_base_agent(corpus=corpus)
graph_agent = LangGraphOpenScholarAgent(
    model=HeuristicResearchModel(),
    corpus=corpus,
    config=ResearchAgentConfig(
        max_subquestions=3,
        local_top_k=3,
        max_evidence=8,
        max_revisions=1,
        min_local_evidence=1,
        min_local_score=0.01,
    ),
)
app = build_openscholar_app(base_agent=base_agent, graph_agent=graph_agent)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

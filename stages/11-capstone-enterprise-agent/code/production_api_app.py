import os
from pathlib import Path
import sys

import uvicorn
from fastapi import HTTPException, Request

from tiny_agent.capstone import BaseOpenScholarAgent, HeuristicResearchModel, LocalResearchCorpus, ResearchAgentConfig
from tiny_agent.governance import Principal
from tiny_agent.integrations.openscholar_production import build_authenticated_openscholar_app, build_bounded_openscholar_service
from tiny_agent.service_identity import AuthenticatedIdentity

# Reuse the stage's offline synthetic corpus helper.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import synthetic_corpus  # noqa: E402


agent = BaseOpenScholarAgent(
    model=HeuristicResearchModel(),
    corpus=synthetic_corpus(),
    config=ResearchAgentConfig(max_subquestions=3, local_top_k=3, max_evidence=8, max_revisions=1, min_local_score=0.01),
)
service = build_bounded_openscholar_service(agent, max_concurrency=4, request_timeout_seconds=30)


def authenticate(request: Request) -> AuthenticatedIdentity:
    expected = os.getenv("OPEN_SCHOLAR_DEMO_API_KEY", "local-secret")
    value = request.headers.get("authorization", "")
    if value != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="invalid credentials")
    return AuthenticatedIdentity(
        Principal("demo-authenticated-user", frozenset({"researcher"})),
        "demo-tenant",
    )


app = build_authenticated_openscholar_app(service, authenticate=authenticate)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

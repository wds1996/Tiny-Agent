import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient

from tiny_agent.capstone import BaseOpenScholarAgent, CorpusDocument, HeuristicResearchModel, LocalResearchCorpus, ResearchAgentConfig
from tiny_agent.governance import Principal
from tiny_agent.integrations.openscholar_production import build_authenticated_openscholar_app, build_bounded_openscholar_service
from tiny_agent.service_identity import AuthenticatedIdentity


def test_production_app_uses_server_authenticated_identity_not_body_identity() -> None:
    corpus = LocalResearchCorpus([
        CorpusDocument(id="react", title="ReAct", text="ReAct combines reasoning, actions, observations, and tool use."),
    ])
    agent = BaseOpenScholarAgent(
        model=HeuristicResearchModel(),
        corpus=corpus,
        config=ResearchAgentConfig(max_revisions=0, min_local_score=0.01),
    )
    service = build_bounded_openscholar_service(agent, max_concurrency=1)

    def authenticate(_request):
        return AuthenticatedIdentity(Principal("trusted-user", frozenset({"researcher"})), "tenant-a")

    app = build_authenticated_openscholar_app(service, authenticate=authenticate)
    with TestClient(app) as client:
        response = client.post("/v1/research", json={"question": "What is ReAct?", "allow_external_search": False})
        assert response.status_code == 200
        assert response.json()["output"]["status"] == "completed"
        malicious = client.post("/v1/research", json={"question": "What is ReAct?", "user_id": "admin"})
        assert malicious.status_code == 422

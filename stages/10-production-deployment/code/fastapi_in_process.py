from fastapi.testclient import TestClient

from tiny_agent.integrations.fastapi_app import create_app
from tiny_agent.production import BoundedAgentService


async def handler(text, metadata):
    return {"answer": f"Agent received: {text}"}


app = create_app(BoundedAgentService(handler), readiness_checks={"self": lambda: True})

with TestClient(app) as client:
    print("live:", client.get("/livez").json())
    print("ready:", client.get("/readyz").json())
    print("run:", client.post("/v1/runs", json={"input": "hello"}).json())

from fastapi.testclient import TestClient

from tiny_agent.integrations.fastapi_app import create_app
from tiny_agent.production import BoundedAgentService


async def handler(text, metadata):
    return {"answer": text[::-1]}


app = create_app(BoundedAgentService(handler))
with TestClient(app) as client:
    response = client.post("/v1/runs/stream", json={"input": "stream me"})
    print(response.text)

print("Notice: after streaming starts, failures are run.error events, not a new HTTP 500 body.")

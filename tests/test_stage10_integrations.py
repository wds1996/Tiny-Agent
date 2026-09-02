import asyncio
import os

from fastapi.testclient import TestClient
import pytest

from tiny_agent.integrations.fastapi_app import create_app
from tiny_agent.integrations.postgres_backend import PostgresPool
from tiny_agent.integrations.redis_backend import RedisFixedWindowRateLimiter, RedisHealthCheck
from tiny_agent.integrations.settings import ServiceSettings
from tiny_agent.production import BoundedAgentService


def test_fastapi_run_health_request_id_and_streaming():
    async def handler(text, metadata):
        return {"answer": text.upper(), "tenant": metadata.get("tenant")}

    app = create_app(BoundedAgentService(handler), readiness_checks={"self": lambda: True})
    with TestClient(app) as client:
        live = client.get("/livez")
        ready = client.get("/readyz")
        response = client.post(
            "/v1/runs",
            headers={"x-request-id": "request-123"},
            json={"input": "hello", "metadata": {"tenant": "demo"}},
        )
        stream = client.post("/v1/runs/stream", json={"input": "hello"})

    assert live.status_code == 200
    assert ready.status_code == 200
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "request-123"
    assert response.json()["output"]["answer"] == "HELLO"
    assert "event: run.started" in stream.text
    assert "event: run.completed" in stream.text


def test_fastapi_failure_is_model_safe():
    async def handler(text, metadata):
        raise RuntimeError("api-key=do-not-leak")

    app = create_app(BoundedAgentService(handler))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/v1/runs", json={"input": "boom"})
    assert response.status_code == 500
    assert response.json() == {"detail": "agent run failed"}
    assert "do-not-leak" not in response.text


def test_readiness_returns_503_without_secret_exception_text():
    async def broken():
        raise RuntimeError("redis-password=secret")

    app = create_app(BoundedAgentService(lambda text, metadata: text), readiness_checks={"redis": broken})
    with TestClient(app) as client:
        response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["checks"][0]["error_type"] == "RuntimeError"
    assert "secret" not in response.text


def test_settings_keep_secret_out_of_safe_summary(monkeypatch):
    monkeypatch.setenv("TINY_AGENT_ENVIRONMENT", "prod")
    monkeypatch.setenv("TINY_AGENT_MODEL_API_KEY", "super-secret")
    settings = ServiceSettings(_env_file=None)
    assert settings.environment == "prod"
    assert settings.model_api_key.get_secret_value() == "super-secret"
    assert "super-secret" not in repr(settings)
    assert "super-secret" not in repr(settings.safe_summary())


@pytest.mark.skipif(not os.getenv("TEST_REDIS_URL"), reason="TEST_REDIS_URL is required")
def test_real_redis_health_and_distributed_fixed_window():
    import redis.asyncio as redis

    async def scenario():
        client = redis.Redis.from_url(os.environ["TEST_REDIS_URL"], decode_responses=True)
        try:
            await client.flushdb()
            assert await RedisHealthCheck(client)() is True
            limiter = RedisFixedWindowRateLimiter(client, limit=2, window_seconds=30)
            first = await limiter.allow("user@example.com")
            second = await limiter.allow("user@example.com")
            third = await limiter.allow("user@example.com")
            assert [first.allowed, second.allowed, third.allowed] == [True, True, False]
            keys = await client.keys("tiny-agent:rate:*")
            assert all("user@example.com" not in key for key in keys)
        finally:
            await client.aclose()

    asyncio.run(scenario())


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URI"), reason="TEST_POSTGRES_URI is required")
def test_real_postgres_pool_lifecycle_and_readiness():
    async def scenario():
        pool = PostgresPool(os.environ["TEST_POSTGRES_URI"], min_size=1, max_size=2)
        await pool.open(timeout=5)
        try:
            assert await pool.ready() is True
        finally:
            await pool.aclose()

    asyncio.run(scenario())

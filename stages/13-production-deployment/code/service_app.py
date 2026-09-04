from contextlib import asynccontextmanager

import redis.asyncio as redis
import uvicorn

from tiny_agent.integrations.fastapi_app import create_app
from tiny_agent.integrations.postgres_backend import PostgresPool
from tiny_agent.integrations.redis_backend import RedisHealthCheck
from tiny_agent.integrations.settings import ServiceSettings
from tiny_agent.production import BoundedAgentService


settings = ServiceSettings()


async def demo_agent(text, metadata):
    return {
        "answer": f"Tiny-Agent production demo received: {text}",
        "environment": settings.environment,
    }


service = BoundedAgentService(
    demo_agent,
    max_concurrency=settings.max_concurrency,
    queue_timeout_seconds=settings.queue_timeout_seconds,
    request_timeout_seconds=settings.request_timeout_seconds,
)

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True) if settings.redis_url else None
postgres_pool = PostgresPool(settings.database_url) if settings.database_url else None


@asynccontextmanager
async def lifespan(app):
    if postgres_pool is not None:
        await postgres_pool.open(timeout=5)
    if redis_client is not None:
        await redis_client.ping()
    yield
    if redis_client is not None:
        await redis_client.aclose()
    if postgres_pool is not None:
        await postgres_pool.aclose()


checks = {}
if postgres_pool is not None:
    checks["postgres"] = postgres_pool.ready
if redis_client is not None:
    checks["redis"] = RedisHealthCheck(redis_client)

app = create_app(service, readiness_checks=checks, lifespan=lifespan)


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)

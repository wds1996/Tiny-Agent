import asyncio
import os

import redis.asyncio as redis

from tiny_agent.integrations.redis_backend import RedisFixedWindowRateLimiter


async def main():
    url = os.environ.get("TEST_REDIS_URL") or os.environ.get("TINY_AGENT_REDIS_URL")
    if not url:
        print("Set TEST_REDIS_URL or TINY_AGENT_REDIS_URL to run the real Redis example.")
        return
    client = redis.Redis.from_url(url, decode_responses=True)
    try:
        limiter = RedisFixedWindowRateLimiter(client, limit=2, window_seconds=30)
        for _ in range(3):
            print(await limiter.allow("demo-user"))
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os

from tiny_agent.integrations.postgres_backend import PostgresPool


async def main():
    dsn = os.environ.get("TEST_POSTGRES_URI") or os.environ.get("TINY_AGENT_DATABASE_URL")
    if not dsn:
        print("Set TEST_POSTGRES_URI or TINY_AGENT_DATABASE_URL to run the real Postgres example.")
        return
    pool = PostgresPool(dsn, min_size=1, max_size=2)
    await pool.open(timeout=5)
    try:
        print("postgres ready:", await pool.ready())
    finally:
        await pool.aclose()


if __name__ == "__main__":
    asyncio.run(main())

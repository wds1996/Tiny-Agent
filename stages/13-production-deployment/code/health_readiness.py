import asyncio

from tiny_agent.production import run_readiness_checks


async def postgres_ok():
    await asyncio.sleep(0.01)
    return True


async def redis_broken():
    raise RuntimeError("redis://user:password@secret-host")


async def main():
    report = await run_readiness_checks(
        {"postgres": postgres_ok, "redis": redis_broken},
        timeout_seconds=0.5,
    )
    print(report)
    print("Raw exception text is absent; only the error type crosses this boundary.")


if __name__ == "__main__":
    asyncio.run(main())

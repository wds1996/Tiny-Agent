import asyncio

from tiny_agent.production import BoundedAgentService, ServiceRequest


async def agent_handler(text, metadata):
    await asyncio.sleep(0.01)
    return {"answer": text.upper(), "tenant": metadata.get("tenant")}


async def main():
    service = BoundedAgentService(
        agent_handler,
        max_concurrency=4,
        queue_timeout_seconds=0.1,
        request_timeout_seconds=2.0,
    )
    result = await service.run(ServiceRequest("hello service", {"tenant": "demo"}))
    print(result)
    print(await service.snapshot())


if __name__ == "__main__":
    asyncio.run(main())

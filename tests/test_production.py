import asyncio
import threading

import pytest

from tiny_agent.production import (
    BoundedAgentService,
    ServiceCapacityError,
    ServiceRequest,
    ServiceTimeoutError,
    run_readiness_checks,
)


def run(coro):
    return asyncio.run(coro)


def test_async_service_success_and_metrics():
    async def handler(text, metadata):
        return f"{text}:{metadata['stage']}"

    async def scenario():
        service = BoundedAgentService(handler, max_concurrency=2)
        result = await service.run(ServiceRequest("hello", {"stage": 10}))
        snapshot = await service.snapshot()
        assert result.output == "hello:10"
        assert snapshot.requests_received == 1
        assert snapshot.succeeded == 1
        assert snapshot.in_flight == 0
        assert snapshot.peak_in_flight == 1

    run(scenario())


def test_sync_handler_runs_off_event_loop_thread():
    main_thread = threading.get_ident()

    def handler(text, metadata):
        return threading.get_ident()

    async def scenario():
        service = BoundedAgentService(handler)
        result = await service.run(ServiceRequest("hello"))
        assert result.output != main_thread

    run(scenario())


def test_capacity_rejection_is_bounded():
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()

        async def handler(text, metadata):
            entered.set()
            await release.wait()
            return text

        service = BoundedAgentService(
            handler,
            max_concurrency=1,
            queue_timeout_seconds=0.01,
            request_timeout_seconds=1,
        )
        first = asyncio.create_task(service.run(ServiceRequest("first")))
        await entered.wait()
        with pytest.raises(ServiceCapacityError):
            await service.run(ServiceRequest("second"))
        release.set()
        await first
        snapshot = await service.snapshot()
        assert snapshot.rejected == 1
        assert snapshot.succeeded == 1

    run(scenario())


def test_execution_timeout_is_typed():
    async def handler(text, metadata):
        await asyncio.sleep(0.1)
        return text

    async def scenario():
        service = BoundedAgentService(handler, request_timeout_seconds=0.01)
        with pytest.raises(ServiceTimeoutError):
            await service.run(ServiceRequest("slow"))
        snapshot = await service.snapshot()
        assert snapshot.timed_out == 1
        assert snapshot.in_flight == 0

    run(scenario())


def test_timed_out_sync_thread_keeps_capacity_until_it_really_finishes():
    release_worker = threading.Event()

    def blocking_handler(text, metadata):
        release_worker.wait(timeout=1.0)
        return text

    async def scenario():
        service = BoundedAgentService(
            blocking_handler,
            max_concurrency=1,
            queue_timeout_seconds=0.01,
            request_timeout_seconds=0.01,
        )

        with pytest.raises(ServiceTimeoutError):
            await service.run(ServiceRequest("first"))

        after_timeout = await service.snapshot()
        assert after_timeout.timed_out == 1
        assert after_timeout.in_flight == 1

        with pytest.raises(ServiceCapacityError):
            await service.run(ServiceRequest("second"))

        release_worker.set()
        for _ in range(100):
            if (await service.snapshot()).in_flight == 0:
                break
            await asyncio.sleep(0.005)
        else:
            raise AssertionError("worker-thread capacity was never released")

        final = await service.snapshot()
        assert final.in_flight == 0
        assert final.rejected == 1

    run(scenario())


def test_readiness_redacts_raw_exception_message():
    async def bad_check():
        raise RuntimeError("postgres-password=super-secret")

    report = run(run_readiness_checks({"db": bad_check}))
    assert report.ready is False
    assert report.checks[0].error_type == "RuntimeError"
    assert "super-secret" not in repr(report)

from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping


class ServiceError(RuntimeError):
    """Base class for model-safe service-boundary failures."""


class ServiceCapacityError(ServiceError):
    """The service could not acquire capacity within the queue budget."""


class ServiceTimeoutError(ServiceError):
    """The accepted run exceeded its execution deadline."""


ServiceHandler = Callable[[str, Mapping[str, Any]], Any | Awaitable[Any]]
ReadinessCheck = Callable[[], bool | Awaitable[bool]]


@dataclass(frozen=True, slots=True)
class ServiceRequest:
    input: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        if not isinstance(self.input, str) or not self.input.strip():
            raise ValueError("service input must be a non-empty string")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        if not self.request_id.strip() or not self.run_id.strip():
            raise ValueError("request_id and run_id must be non-empty")


@dataclass(frozen=True, slots=True)
class ServiceRunResult:
    request_id: str
    run_id: str
    output: Any
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class ServiceSnapshot:
    requests_received: int
    succeeded: int
    failed: int
    timed_out: int
    rejected: int
    cancelled: int
    in_flight: int
    peak_in_flight: int


@dataclass(frozen=True, slots=True)
class DependencyStatus:
    name: str
    ok: bool
    error_type: str | None = None


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    ready: bool
    checks: tuple[DependencyStatus, ...]


class BoundedAgentService:
    """Framework-neutral async service boundary around one Agent handler.

    The semaphore is process-local: it protects one worker from overload but is
    not a distributed rate limiter. A sync handler is moved to a worker thread;
    if its caller times out/cancels, the thread cannot be hard-killed. In that
    case Tiny-Agent deliberately keeps the capacity slot occupied until the
    underlying invocation actually finishes.
    """

    def __init__(
        self,
        handler: ServiceHandler,
        *,
        max_concurrency: int = 8,
        queue_timeout_seconds: float = 0.25,
        request_timeout_seconds: float = 30.0,
    ) -> None:
        if not callable(handler):
            raise TypeError("handler must be callable")
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive")
        if queue_timeout_seconds <= 0 or request_timeout_seconds <= 0:
            raise ValueError("timeouts must be positive")

        self._handler = handler
        self._handler_is_async = inspect.iscoroutinefunction(handler)
        self._gate = asyncio.Semaphore(max_concurrency)
        self._queue_timeout_seconds = float(queue_timeout_seconds)
        self._request_timeout_seconds = float(request_timeout_seconds)
        self._metrics_lock = asyncio.Lock()
        self._requests_received = 0
        self._succeeded = 0
        self._failed = 0
        self._timed_out = 0
        self._rejected = 0
        self._cancelled = 0
        self._in_flight = 0
        self._peak_in_flight = 0

    async def run(self, request: ServiceRequest) -> ServiceRunResult:
        await self._metric("received")
        try:
            await asyncio.wait_for(
                self._gate.acquire(), timeout=self._queue_timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            await self._metric("rejected")
            raise ServiceCapacityError("service capacity queue timeout") from exc

        await self._metric("accepted")
        started = time.perf_counter()
        invocation = asyncio.create_task(self._invoke_handler(request))
        release_deferred = False

        try:
            try:
                if self._handler_is_async:
                    output = await asyncio.wait_for(
                        invocation,
                        timeout=self._request_timeout_seconds,
                    )
                else:
                    # Shield prevents wait_for from cancelling the task that is
                    # awaiting an underlying worker thread we cannot hard-kill.
                    output = await asyncio.wait_for(
                        asyncio.shield(invocation),
                        timeout=self._request_timeout_seconds,
                    )
            except asyncio.TimeoutError as exc:
                await self._metric("timed_out")
                if not invocation.done():
                    release_deferred = True
                    self._release_when_done(invocation)
                raise ServiceTimeoutError("agent run exceeded its deadline") from exc
            except asyncio.CancelledError:
                await self._metric("cancelled")
                if not invocation.done():
                    if self._handler_is_async:
                        invocation.cancel()
                    release_deferred = True
                    self._release_when_done(invocation)
                raise
            except Exception:
                await self._metric("failed")
                raise
            else:
                await self._metric("succeeded")
        finally:
            if not release_deferred:
                await self._release_capacity()

        return ServiceRunResult(
            request_id=request.request_id,
            run_id=request.run_id,
            output=output,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
        )

    async def snapshot(self) -> ServiceSnapshot:
        async with self._metrics_lock:
            return ServiceSnapshot(
                requests_received=self._requests_received,
                succeeded=self._succeeded,
                failed=self._failed,
                timed_out=self._timed_out,
                rejected=self._rejected,
                cancelled=self._cancelled,
                in_flight=self._in_flight,
                peak_in_flight=self._peak_in_flight,
            )

    async def _invoke_handler(self, request: ServiceRequest) -> Any:
        payload = dict(request.metadata)
        if self._handler_is_async:
            return await self._handler(request.input, payload)
        value = await asyncio.to_thread(self._handler, request.input, payload)
        if inspect.isawaitable(value):
            return await value
        return value

    def _release_when_done(self, invocation: asyncio.Task[Any]) -> None:
        def completed(task: asyncio.Task[Any]) -> None:
            # Retrieve the result so a post-timeout worker exception does not
            # become an unhandled-task warning. The caller already received a
            # timeout/cancellation outcome, so this does not change that result.
            try:
                task.result()
            except BaseException:
                pass
            task.get_loop().create_task(self._release_capacity())

        invocation.add_done_callback(completed)

    async def _release_capacity(self) -> None:
        await self._metric("finished")
        self._gate.release()

    async def _metric(self, event: str) -> None:
        async with self._metrics_lock:
            if event == "received":
                self._requests_received += 1
            elif event == "accepted":
                self._in_flight += 1
                self._peak_in_flight = max(self._peak_in_flight, self._in_flight)
            elif event == "finished":
                self._in_flight -= 1
            elif event == "succeeded":
                self._succeeded += 1
            elif event == "failed":
                self._failed += 1
            elif event == "timed_out":
                self._timed_out += 1
            elif event == "rejected":
                self._rejected += 1
            elif event == "cancelled":
                self._cancelled += 1
            else:  # pragma: no cover
                raise ValueError(f"unknown metric event: {event}")


async def run_readiness_checks(
    checks: Mapping[str, ReadinessCheck],
    *,
    timeout_seconds: float = 1.0,
) -> ReadinessReport:
    """Run dependency checks without exposing raw exception messages."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    async def run_one(name: str, check: ReadinessCheck) -> DependencyStatus:
        try:
            ok = await asyncio.wait_for(
                _call_readiness_check(check), timeout=timeout_seconds
            )
        except Exception as exc:
            return DependencyStatus(name=name, ok=False, error_type=type(exc).__name__)
        return DependencyStatus(name=name, ok=bool(ok))

    statuses = await asyncio.gather(
        *(run_one(name, check) for name, check in checks.items())
    )
    return ReadinessReport(
        ready=all(status.ok for status in statuses),
        checks=tuple(statuses),
    )


async def _call_readiness_check(check: ReadinessCheck) -> bool:
    if inspect.iscoroutinefunction(check):
        return bool(await check())
    value = await asyncio.to_thread(check)
    if inspect.isawaitable(value):
        return bool(await value)
    return bool(value)

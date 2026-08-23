from __future__ import annotations

import asyncio
import inspect
import random
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Mapping

from .governance import AllowlistPermissionPolicy, ApprovalGrant, Principal
from .reliability import (
    BudgetLedger,
    RepeatedToolCallDetector,
    RetryPolicy,
    ToolFailure,
    ToolTimeoutError,
    UnknownToolError,
    failure_from_exception,
)
from .tool import Tool, ToolRegistry
from .validation import SimpleToolArgumentsValidator, ToolArgumentsValidator


ExecutionStatus = Literal["ok", "failed"]


@dataclass(frozen=True, slots=True)
class ToolExecutionPolicy:
    timeout_seconds: float = 10.0
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    retry_safe: bool = False

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.retry_policy.max_attempts > 1 and not self.retry_safe:
            raise ValueError(
                "retries require retry_safe=True because duplicate side effects may be unsafe"
            )


@dataclass(slots=True)
class GuardedRunState:
    """Mutable reliability state owned by one logical Agent execution.

    Executors may be shared across requests; budgets and loop history must not be.
    """

    budget: BudgetLedger
    loop_detector: RepeatedToolCallDetector = field(
        default_factory=RepeatedToolCallDetector
    )


@dataclass(frozen=True, slots=True)
class GuardedToolResult:
    status: ExecutionStatus
    value: Any | None
    failure: ToolFailure | None
    attempts: int

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def observation(self) -> str:
        if self.failure is not None:
            return self.failure.observation()
        return str(self.value)


class GuardedToolExecutor:
    """Deterministic policy boundary around ToolRegistry execution.

    Order of enforcement:

    1. run-scoped budget
    2. local argument validation
    3. permission / exact-action approval
    4. run-scoped repeated-call detection
    5. timeout
    6. bounded retry for explicitly retry-safe operations only
    7. model-safe failure redaction

    Async handlers run as tasks. Sync handlers are moved to a worker thread so
    they do not block the event loop, but timing out a thread does *not* kill
    the underlying function. Hard termination requires a process/container
    boundary.
    """

    def __init__(
        self,
        *,
        tools: ToolRegistry,
        permission_policy: AllowlistPermissionPolicy,
        validator: ToolArgumentsValidator | None = None,
        tool_policies: Mapping[str, ToolExecutionPolicy] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random_unit: Callable[[], float] = random.random,
    ) -> None:
        self.tools = tools
        self.permission_policy = permission_policy
        self.validator = validator or SimpleToolArgumentsValidator()
        self.tool_policies = dict(tool_policies or {})
        self.sleep = sleep
        self.random_unit = random_unit

    async def execute(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        principal: Principal,
        run_state: GuardedRunState,
        approval: ApprovalGrant | None = None,
    ) -> GuardedToolResult:
        budget = run_state.budget
        try:
            budget.consume_tool_call()
            tool = self._get_tool(tool_name)
            self.validator.validate(tool.parameters, arguments)
            self.permission_policy.enforce(
                tool_name=tool_name,
                principal=principal,
                arguments=arguments,
                approval=approval,
            )
            run_state.loop_detector.observe(tool_name, arguments)
        except Exception as exc:
            return GuardedToolResult(
                status="failed",
                value=None,
                failure=failure_from_exception(exc),
                attempts=0,
            )

        policy = self.tool_policies.get(tool_name, ToolExecutionPolicy())
        attempts = 0

        while attempts < policy.retry_policy.max_attempts:
            attempts += 1
            try:
                budget.check_time()
                value = await self._invoke_with_timeout(
                    tool,
                    arguments,
                    policy.timeout_seconds,
                )
                return GuardedToolResult("ok", value, None, attempts)
            except asyncio.CancelledError:
                # Caller cancellation is control flow, not a tool failure.
                raise
            except Exception as exc:
                failure = failure_from_exception(exc)

            if not failure.retryable or attempts >= policy.retry_policy.max_attempts:
                return GuardedToolResult("failed", None, failure, attempts)

            try:
                budget.consume_retry()
            except Exception as exc:
                return GuardedToolResult(
                    "failed",
                    None,
                    failure_from_exception(exc),
                    attempts,
                )

            delay = policy.retry_policy.delay_for_retry(
                attempts,
                random_unit=self.random_unit(),
            )
            budget.check_time()
            if delay > 0:
                await self.sleep(delay)

        raise AssertionError("retry loop exited unexpectedly")

    def _get_tool(self, tool_name: str) -> Tool:
        try:
            return self.tools.get(tool_name)
        except KeyError as exc:
            raise UnknownToolError("Requested tool is not registered.") from exc

    @staticmethod
    async def _invoke_with_timeout(
        tool: Tool,
        arguments: dict[str, Any],
        timeout_seconds: float,
    ) -> Any:
        try:
            if inspect.iscoroutinefunction(tool.handler):
                return await asyncio.wait_for(
                    tool.ainvoke(arguments),
                    timeout=timeout_seconds,
                )

            return await asyncio.wait_for(
                asyncio.to_thread(tool.invoke, arguments),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            # Python 3.10 exposes asyncio.TimeoutError here; modern Python aliases
            # that name to the built-in TimeoutError. Using the asyncio name keeps
            # the supported 3.10/3.12 matrix semantically consistent.
            raise ToolTimeoutError(
                f"Tool {tool.name!r} exceeded its execution timeout."
            ) from exc

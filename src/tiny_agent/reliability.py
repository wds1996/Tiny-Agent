from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal


FailureCode = Literal[
    "invalid_arguments",
    "unknown_tool",
    "permission_denied",
    "approval_required",
    "timeout",
    "transient_error",
    "permanent_error",
    "budget_exceeded",
    "loop_detected",
    "internal_error",
]


class SafeToolError(Exception):
    """Base exception whose message is explicitly safe to expose to a model.

    Do not put secrets, connection strings, raw provider payloads, stack traces,
    or other sensitive internals in ``safe_message``.
    """

    code: FailureCode = "permanent_error"
    retryable: bool = False

    def __init__(self, safe_message: str) -> None:
        if not isinstance(safe_message, str) or not safe_message.strip():
            raise ValueError("safe_message must be a non-empty string")
        super().__init__(safe_message)
        self.safe_message = safe_message


class ToolInputError(SafeToolError):
    code: FailureCode = "invalid_arguments"


class UnknownToolError(SafeToolError):
    code: FailureCode = "unknown_tool"


class ToolPermissionError(SafeToolError):
    code: FailureCode = "permission_denied"


class ToolApprovalRequired(SafeToolError):
    code: FailureCode = "approval_required"


class ToolTimeoutError(SafeToolError):
    code: FailureCode = "timeout"
    retryable = True


class TransientToolError(SafeToolError):
    code: FailureCode = "transient_error"
    retryable = True


class PermanentToolError(SafeToolError):
    code: FailureCode = "permanent_error"


class BudgetExceededError(SafeToolError):
    code: FailureCode = "budget_exceeded"


class ToolLoopDetectedError(SafeToolError):
    code: FailureCode = "loop_detected"


@dataclass(frozen=True, slots=True)
class ToolFailure:
    """Model-safe failure plus minimal internal classification metadata."""

    code: FailureCode
    safe_message: str
    retryable: bool = False
    internal_exception_type: str | None = None

    def observation(self) -> str:
        return f"ToolFailure[{self.code}]: {self.safe_message}"


def failure_from_exception(exc: Exception) -> ToolFailure:
    """Convert arbitrary exceptions into a model-safe failure.

    Only ``SafeToolError`` messages cross the model boundary. Unexpected
    exception messages are intentionally discarded.
    """

    if isinstance(exc, SafeToolError):
        return ToolFailure(
            code=exc.code,
            safe_message=exc.safe_message,
            retryable=exc.retryable,
            internal_exception_type=type(exc).__name__,
        )
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        # Python 3.10 still exposes asyncio.TimeoutError for wait_for(); newer
        # Python aliases it to the built-in TimeoutError.
        return ToolFailure(
            code="timeout",
            safe_message="Tool execution exceeded its time limit.",
            retryable=True,
            internal_exception_type=type(exc).__name__,
        )
    return ToolFailure(
        code="internal_error",
        safe_message="Tool execution failed.",
        retryable=False,
        internal_exception_type=type(exc).__name__,
    )


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Small inspectable retry policy used before introducing Tenacity."""

    max_attempts: int = 1
    base_delay_seconds: float = 0.0
    max_delay_seconds: float = 30.0
    jitter_ratio: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays must be non-negative")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must be >= base_delay_seconds")
        if not 0.0 <= self.jitter_ratio <= 1.0:
            raise ValueError("jitter_ratio must be between 0 and 1")

    def delay_for_retry(self, retry_number: int, *, random_unit: float = 0.5) -> float:
        """Return delay before retry ``retry_number`` (first retry is 1)."""

        if retry_number <= 0:
            raise ValueError("retry_number must be positive")
        if not 0.0 <= random_unit <= 1.0:
            raise ValueError("random_unit must be between 0 and 1")

        raw = min(
            self.max_delay_seconds,
            self.base_delay_seconds * (2 ** (retry_number - 1)),
        )
        if raw == 0 or self.jitter_ratio == 0:
            return raw

        spread = raw * self.jitter_ratio
        # random_unit=0 -> -spread, 0.5 -> 0, 1 -> +spread.
        return max(0.0, raw + ((2 * random_unit) - 1) * spread)


@dataclass(frozen=True, slots=True)
class ExecutionBudget:
    max_tool_calls: int = 16
    max_retry_attempts: int = 8
    max_elapsed_seconds: float | None = 120.0
    max_tokens: int | None = None
    max_cost_usd: float | None = None

    def __post_init__(self) -> None:
        if self.max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if self.max_retry_attempts < 0:
            raise ValueError("max_retry_attempts must be non-negative")
        if self.max_elapsed_seconds is not None and self.max_elapsed_seconds <= 0:
            raise ValueError("max_elapsed_seconds must be positive when provided")
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive when provided")
        if self.max_cost_usd is not None and self.max_cost_usd <= 0:
            raise ValueError("max_cost_usd must be positive when provided")


@dataclass(slots=True)
class BudgetLedger:
    limits: ExecutionBudget = field(default_factory=ExecutionBudget)
    clock: Callable[[], float] = time.monotonic
    tool_calls: int = 0
    retry_attempts: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    _started_at: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._started_at = self.clock()

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, self.clock() - self._started_at)

    def check_time(self) -> None:
        limit = self.limits.max_elapsed_seconds
        if limit is not None and self.elapsed_seconds > limit:
            raise BudgetExceededError("Execution time budget has been exhausted.")

    def consume_tool_call(self) -> None:
        self.check_time()
        if self.tool_calls + 1 > self.limits.max_tool_calls:
            raise BudgetExceededError("Tool-call budget has been exhausted.")
        self.tool_calls += 1

    def consume_retry(self) -> None:
        self.check_time()
        if self.retry_attempts + 1 > self.limits.max_retry_attempts:
            raise BudgetExceededError("Retry budget has been exhausted.")
        self.retry_attempts += 1

    def record_tokens(self, count: int) -> None:
        if count < 0:
            raise ValueError("token count must be non-negative")
        if self.limits.max_tokens is not None and self.tokens + count > self.limits.max_tokens:
            raise BudgetExceededError("Token budget has been exhausted.")
        self.tokens += count

    def record_cost(self, amount_usd: float) -> None:
        if amount_usd < 0:
            raise ValueError("cost must be non-negative")
        if (
            self.limits.max_cost_usd is not None
            and self.cost_usd + amount_usd > self.limits.max_cost_usd
        ):
            raise BudgetExceededError("Cost budget has been exhausted.")
        self.cost_usd += amount_usd


def canonical_tool_call(tool_name: str, arguments: dict[str, Any]) -> str:
    if not isinstance(tool_name, str) or not tool_name.strip():
        raise ValueError("tool_name must be a non-empty string")
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    try:
        payload = json.dumps(
            arguments,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ToolInputError("Tool arguments must be JSON-serializable.") from exc
    return f"{tool_name.strip()}:{payload}"


def tool_call_fingerprint(tool_name: str, arguments: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_tool_call(tool_name, arguments).encode("utf-8")).hexdigest()


class RepeatedToolCallDetector:
    """Detect exact repeated tool calls before the global budget is exhausted."""

    def __init__(self, max_identical_calls: int = 3) -> None:
        if max_identical_calls <= 0:
            raise ValueError("max_identical_calls must be positive")
        self.max_identical_calls = max_identical_calls
        self._counts: dict[str, int] = {}

    def observe(self, tool_name: str, arguments: dict[str, Any]) -> None:
        fingerprint = tool_call_fingerprint(tool_name, arguments)
        count = self._counts.get(fingerprint, 0) + 1
        self._counts[fingerprint] = count
        if count > self.max_identical_calls:
            raise ToolLoopDetectedError(
                f"Repeated identical call to tool {tool_name!r} exceeded the loop threshold."
            )

    def reset(self) -> None:
        self._counts.clear()

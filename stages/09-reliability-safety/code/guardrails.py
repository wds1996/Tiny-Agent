from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
import time
from typing import Any, Callable, Mapping


class ValidationError(ValueError):
    pass


class PermissionDenied(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


class DeadlineExceeded(RuntimeError):
    pass


class ToolFailure(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class Principal:
    id: str
    roles: frozenset[str]


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    deadline_monotonic: float | None = None
    idempotency_key: str | None = None

    def check_deadline(self) -> None:
        if self.deadline_monotonic is not None and time.monotonic() >= self.deadline_monotonic:
            raise DeadlineExceeded("execution deadline exceeded")


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    required: Mapping[str, type]
    handler: Callable[..., Any]
    safe_to_retry: bool = False

    def validate(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        expected = set(self.required)
        actual = set(arguments)
        missing = expected - actual
        unknown = actual - expected
        if missing:
            raise ValidationError(f"missing fields: {sorted(missing)}")
        if unknown:
            raise ValidationError(f"unknown fields: {sorted(unknown)}")
        normalized = dict(arguments)
        for key, expected_type in self.required.items():
            if not isinstance(normalized[key], expected_type):
                raise ValidationError(
                    f"{key} must be {expected_type.__name__}, got {type(normalized[key]).__name__}"
                )
        return normalized


class PermissionPolicy:
    def __init__(self, grants: Mapping[str, set[str]]) -> None:
        self._grants = {role: set(tools) for role, tools in grants.items()}

    def authorize(self, principal: Principal, tool_name: str) -> None:
        allowed = set()
        for role in principal.roles:
            allowed.update(self._grants.get(role, set()))
        if tool_name not in allowed:
            raise PermissionDenied(
                f"principal {principal.id!r} is not allowed to use {tool_name!r}"
            )


@dataclass(slots=True)
class ExecutionBudget:
    max_tool_calls: int = 8
    max_retries: int = 2
    max_same_call: int = 2
    tool_calls: int = 0
    retries: int = 0
    fingerprints: dict[str, int] = field(default_factory=dict)

    def before_call(self, tool_name: str, arguments: Mapping[str, Any]) -> None:
        if self.tool_calls >= self.max_tool_calls:
            raise BudgetExceeded("tool-call budget exhausted")
        canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(
            f"{tool_name}:{canonical}".encode("utf-8")
        ).hexdigest()
        count = self.fingerprints.get(fingerprint, 0) + 1
        self.fingerprints[fingerprint] = count
        if count > self.max_same_call:
            raise BudgetExceeded("same-call repetition budget exhausted")
        self.tool_calls += 1

    def record_retry(self) -> None:
        if self.retries >= self.max_retries:
            raise BudgetExceeded("retry budget exhausted")
        self.retries += 1


_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)(password\s*=\s*)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key\s*=\s*)[^\s,;]+"),
)


def redact_error(message: str) -> str:
    sanitized = message
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
    return sanitized


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    ok: bool
    value: Any = None
    error: str | None = None
    attempts: int = 0


class GuardedExecutor:
    def __init__(self, tools: list[ToolSpec], *, permissions: PermissionPolicy) -> None:
        self._tools = {tool.name: tool for tool in tools}
        if len(self._tools) != len(tools):
            raise ValueError("tool names must be unique")
        self._permissions = permissions

    def execute(
        self,
        *,
        principal: Principal,
        tool_name: str,
        arguments: Mapping[str, Any],
        budget: ExecutionBudget,
        context: ExecutionContext | None = None,
    ) -> ExecutionResult:
        context = context or ExecutionContext()
        tool = self._tools.get(tool_name)
        if tool is None:
            return ExecutionResult(False, error="unknown tool", attempts=0)
        try:
            normalized = tool.validate(arguments)
            self._permissions.authorize(principal, tool_name)
        except (ValidationError, PermissionDenied) as exc:
            return ExecutionResult(False, error=redact_error(str(exc)), attempts=0)

        attempts = 0
        while True:
            try:
                budget.before_call(tool_name, normalized)
                context.check_deadline()
                attempts += 1
                value = tool.handler(context=context, **normalized)
                context.check_deadline()
                return ExecutionResult(True, value=value, attempts=attempts)
            except DeadlineExceeded as exc:
                return ExecutionResult(False, error=redact_error(str(exc)), attempts=attempts)
            except ToolFailure as exc:
                can_retry = exc.retryable and (
                    tool.safe_to_retry or context.idempotency_key is not None
                )
                if not can_retry:
                    return ExecutionResult(False, error=redact_error(str(exc)), attempts=attempts)
                try:
                    budget.record_retry()
                except BudgetExceeded as budget_error:
                    return ExecutionResult(
                        False, error=redact_error(str(budget_error)), attempts=attempts
                    )
            except BudgetExceeded as exc:
                return ExecutionResult(False, error=redact_error(str(exc)), attempts=attempts)
            except Exception:
                return ExecutionResult(False, error="tool execution failed", attempts=attempts)

from __future__ import annotations

from typing import Any

from .governance import ApprovalGrant, Principal
from .guarded_runtime import GuardedRunState, GuardedToolExecutor, GuardedToolResult
from .observability import Tracer


class ObservedGuardedToolExecutor:
    """Add trace spans around the Stage 07 deterministic execution boundary.

    The wrapped executor still owns validation, authorization, approval,
    budgets, retries, and timeout behavior. This adapter only observes the
    result; observability must not become a second policy engine.
    """

    def __init__(self, executor: GuardedToolExecutor, tracer: Tracer) -> None:
        self.executor = executor
        self.tracer = tracer

    async def execute(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        principal: Principal,
        run_state: GuardedRunState,
        approval: ApprovalGrant | None = None,
    ) -> GuardedToolResult:
        with self.tracer.span(
            f"execute_tool {tool_name}",
            kind="tool",
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "tool.name": tool_name,
            },
        ) as span:
            # The default TraceCapturePolicy intentionally drops raw arguments.
            span.record_input(arguments)
            result = await self.executor.execute(
                tool_name=tool_name,
                arguments=arguments,
                principal=principal,
                run_state=run_state,
                approval=approval,
            )
            span.set_attribute("tiny_agent.tool.attempts", result.attempts)
            span.set_attribute("tiny_agent.tool.status", result.status)

            if result.failure is not None:
                span.set_attribute("error.type", result.failure.code)
                span.set_status("error", error_type=result.failure.code)
                # If output capture is explicitly enabled, record only the
                # already-redacted model-safe observation, never the raw exception.
                span.record_output(result.failure.observation())
            else:
                span.record_output(result.value)

            return result

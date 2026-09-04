"""Stage 09 example 7: the complete guarded Tool execution pipeline."""

import asyncio

from tiny_agent import (
    AllowlistPermissionPolicy,
    BudgetLedger,
    ExecutionBudget,
    GuardedRunState,
    GuardedToolExecutor,
    Principal,
    RetryPolicy,
    Tool,
    ToolExecutionPolicy,
    ToolPermissionRule,
    ToolRegistry,
    TransientToolError,
)
from tiny_agent.validators.jsonschema import JsonSchemaToolArgumentsValidator


async def main() -> None:
    attempts = 0

    async def fetch_status(service: str) -> dict[str, str]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TransientToolError("Status service is temporarily unavailable.")
        return {"service": service, "status": "healthy"}

    tool = Tool(
        name="fetch_status",
        description="Read service health status.",
        parameters={
            "type": "object",
            "properties": {"service": {"type": "string", "minLength": 1}},
            "required": ["service"],
            "additionalProperties": False,
        },
        handler=fetch_status,
    )

    executor = GuardedToolExecutor(
        tools=ToolRegistry([tool]),
        validator=JsonSchemaToolArgumentsValidator(),
        permission_policy=AllowlistPermissionPolicy(
            [
                ToolPermissionRule(
                    tool_name="fetch_status",
                    allowed_roles=frozenset({"operator"}),
                    risk="low",
                )
            ]
        ),
        tool_policies={
            "fetch_status": ToolExecutionPolicy(
                timeout_seconds=1.0,
                retry_policy=RetryPolicy(
                    max_attempts=2,
                    base_delay_seconds=0.01,
                    max_delay_seconds=0.01,
                ),
                retry_safe=True,
            )
        },
    )

    run_state = GuardedRunState(
        budget=BudgetLedger(
            ExecutionBudget(
                max_tool_calls=4,
                max_retry_attempts=2,
                max_elapsed_seconds=5,
            )
        )
    )

    result = await executor.execute(
        tool_name="fetch_status",
        arguments={"service": "api"},
        principal=Principal("operator-1", frozenset({"operator"})),
        run_state=run_state,
    )

    print("status  =", result.status)
    print("attempts=", result.attempts)
    print("value   =", result.value)


if __name__ == "__main__":
    asyncio.run(main())

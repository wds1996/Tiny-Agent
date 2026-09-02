"""Stage 08 example 3: trace the real Stage 07 guarded Tool executor."""

import asyncio

from tiny_agent import (
    AllowlistPermissionPolicy,
    BudgetLedger,
    ExecutionBudget,
    GuardedRunState,
    GuardedToolExecutor,
    InMemorySpanSink,
    LocalTracer,
    ObservedGuardedToolExecutor,
    Principal,
    Tool,
    ToolPermissionRule,
    ToolRegistry,
    trace_tree_lines,
)


async def main() -> None:
    tool = Tool(
        name="double",
        description="Double an integer.",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        handler=lambda value: value * 2,
    )
    guarded = GuardedToolExecutor(
        tools=ToolRegistry([tool]),
        permission_policy=AllowlistPermissionPolicy(
            [
                ToolPermissionRule(
                    tool_name="double",
                    allowed_roles=frozenset({"operator"}),
                    risk="low",
                )
            ]
        ),
    )
    sink = InMemorySpanSink()
    tracer = LocalTracer(sink)
    observed = ObservedGuardedToolExecutor(guarded, tracer)

    with tracer.span("tiny-agent run", kind="agent"):
        result = await observed.execute(
            tool_name="double",
            arguments={"value": 21},
            principal=Principal("demo-user", frozenset({"operator"})),
            run_state=GuardedRunState(
                BudgetLedger(ExecutionBudget(max_elapsed_seconds=None))
            ),
        )

    print("Tool result:", result.value)
    print("\nTrace:")
    for line in trace_tree_lines(sink.spans):
        print(line)


if __name__ == "__main__":
    asyncio.run(main())

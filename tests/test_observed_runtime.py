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
)


SCHEMA = {
    "type": "object",
    "properties": {"value": {"type": "integer"}},
    "required": ["value"],
    "additionalProperties": False,
}


def _executor(handler):
    tool = Tool("work", "Do small work.", SCHEMA, handler)
    return GuardedToolExecutor(
        tools=ToolRegistry([tool]),
        permission_policy=AllowlistPermissionPolicy(
            [
                ToolPermissionRule(
                    tool_name="work",
                    allowed_roles=frozenset({"operator"}),
                    risk="low",
                )
            ]
        ),
    )


def test_observed_guarded_executor_records_tool_span_without_raw_arguments():
    sink = InMemorySpanSink()
    tracer = LocalTracer(sink)
    observed = ObservedGuardedToolExecutor(_executor(lambda value: value * 2), tracer)

    async def run():
        with tracer.span("agent run", kind="agent"):
            return await observed.execute(
                tool_name="work",
                arguments={"value": 21},
                principal=Principal("u1", frozenset({"operator"})),
                run_state=GuardedRunState(
                    BudgetLedger(ExecutionBudget(max_elapsed_seconds=None))
                ),
            )

    result = asyncio.run(run())
    assert result.value == 42

    tool_span = next(span for span in sink.spans if span.kind == "tool")
    agent_span = next(span for span in sink.spans if span.kind == "agent")
    assert tool_span.parent_span_id == agent_span.span_id
    assert tool_span.attributes["tool.name"] == "work"
    assert tool_span.attributes["tiny_agent.tool.attempts"] == 1
    assert tool_span.status == "ok"
    assert tool_span.input_data is None
    assert tool_span.output_data is None


def test_observed_guarded_executor_records_safe_failure_classification():
    def explode(value):
        raise RuntimeError(f"secret-{value}")

    sink = InMemorySpanSink()
    tracer = LocalTracer(sink)
    observed = ObservedGuardedToolExecutor(_executor(explode), tracer)

    result = asyncio.run(
        observed.execute(
            tool_name="work",
            arguments={"value": 7},
            principal=Principal("u1", frozenset({"operator"})),
            run_state=GuardedRunState(
                BudgetLedger(ExecutionBudget(max_elapsed_seconds=None))
            ),
        )
    )

    assert result.failure.code == "internal_error"
    tool_span = sink.spans[0]
    assert tool_span.status == "error"
    assert tool_span.attributes["error.type"] == "internal_error"
    assert tool_span.error_type == "internal_error"
    assert "secret-7" not in str(tool_span.attributes)

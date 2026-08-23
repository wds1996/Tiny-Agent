import asyncio

from tiny_agent import (
    AllowlistPermissionPolicy,
    ApprovalGrant,
    BudgetLedger,
    ExecutionBudget,
    GuardedRunState,
    GuardedToolExecutor,
    Principal,
    RepeatedToolCallDetector,
    RetryPolicy,
    Tool,
    ToolExecutionPolicy,
    ToolPermissionRule,
    ToolRegistry,
    TransientToolError,
)


SCHEMA = {
    "type": "object",
    "properties": {"value": {"type": "integer"}},
    "required": ["value"],
    "additionalProperties": False,
}


def make_permission(*, approval: bool = False) -> AllowlistPermissionPolicy:
    return AllowlistPermissionPolicy(
        [
            ToolPermissionRule(
                tool_name="work",
                allowed_roles=frozenset({"operator"}),
                requires_approval=approval,
                risk="high" if approval else "low",
            )
        ]
    )


def make_run_state(**budget_kwargs) -> GuardedRunState:
    return GuardedRunState(
        budget=BudgetLedger(
            ExecutionBudget(max_elapsed_seconds=None, **budget_kwargs)
        )
    )


def run(coro):
    return asyncio.run(coro)


def test_invalid_arguments_are_blocked_before_handler_runs():
    called = False

    def handler(value):
        nonlocal called
        called = True
        return value

    executor = GuardedToolExecutor(
        tools=ToolRegistry([Tool("work", "work", SCHEMA, handler)]),
        permission_policy=make_permission(),
    )
    result = run(
        executor.execute(
            tool_name="work",
            arguments={"value": "not-an-int"},
            principal=Principal("u1", frozenset({"operator"})),
            run_state=make_run_state(),
        )
    )

    assert result.ok is False
    assert result.failure.code == "invalid_arguments"
    assert result.attempts == 0
    assert called is False


def test_permission_denial_blocks_handler():
    executor = GuardedToolExecutor(
        tools=ToolRegistry([Tool("work", "work", SCHEMA, lambda value: value)]),
        permission_policy=make_permission(),
    )
    result = run(
        executor.execute(
            tool_name="work",
            arguments={"value": 1},
            principal=Principal("u1", frozenset({"viewer"})),
            run_state=make_run_state(),
        )
    )

    assert result.failure.code == "permission_denied"
    assert result.attempts == 0


def test_approval_must_match_exact_arguments():
    executor = GuardedToolExecutor(
        tools=ToolRegistry([Tool("work", "work", SCHEMA, lambda value: value)]),
        permission_policy=make_permission(approval=True),
    )
    principal = Principal("u1", frozenset({"operator"}))
    grant = ApprovalGrant.issue(
        tool_name="work",
        arguments={"value": 1},
        reviewer_id="reviewer",
    )

    result = run(
        executor.execute(
            tool_name="work",
            arguments={"value": 2},
            principal=principal,
            approval=grant,
            run_state=make_run_state(),
        )
    )

    assert result.failure.code == "approval_required"


def test_retryable_failure_retries_only_when_policy_marks_operation_retry_safe():
    calls = 0

    def flaky(value):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TransientToolError("Temporary upstream failure.")
        return value * 2

    async def no_sleep(_delay):
        return None

    ledger = BudgetLedger(
        ExecutionBudget(
            max_tool_calls=3,
            max_retry_attempts=2,
            max_elapsed_seconds=None,
        )
    )
    executor = GuardedToolExecutor(
        tools=ToolRegistry([Tool("work", "work", SCHEMA, flaky)]),
        permission_policy=make_permission(),
        tool_policies={
            "work": ToolExecutionPolicy(
                retry_policy=RetryPolicy(max_attempts=2),
                retry_safe=True,
            )
        },
        sleep=no_sleep,
    )

    result = run(
        executor.execute(
            tool_name="work",
            arguments={"value": 4},
            principal=Principal("u1", frozenset({"operator"})),
            run_state=GuardedRunState(budget=ledger),
        )
    )

    assert result.ok is True
    assert result.value == 8
    assert result.attempts == 2
    assert ledger.retry_attempts == 1


def test_retry_policy_rejects_unsafe_duplicate_side_effects_at_configuration_time():
    try:
        ToolExecutionPolicy(
            retry_policy=RetryPolicy(max_attempts=2),
            retry_safe=False,
        )
    except ValueError as exc:
        assert "retry_safe" in str(exc)
    else:
        raise AssertionError("unsafe retry policy should have been rejected")


def test_async_tool_timeout_returns_safe_failure():
    async def slow(value):
        await asyncio.sleep(0.05)
        return value

    executor = GuardedToolExecutor(
        tools=ToolRegistry([Tool("work", "work", SCHEMA, slow)]),
        permission_policy=make_permission(),
        tool_policies={"work": ToolExecutionPolicy(timeout_seconds=0.005)},
    )
    result = run(
        executor.execute(
            tool_name="work",
            arguments={"value": 1},
            principal=Principal("u1", frozenset({"operator"})),
            run_state=make_run_state(),
        )
    )

    assert result.failure.code == "timeout"
    assert result.failure.retryable is True
    assert "0.05" not in result.observation()


def test_unexpected_tool_exception_is_redacted_from_model_observation():
    def explode(value):
        raise RuntimeError("secret-token=abc123")

    executor = GuardedToolExecutor(
        tools=ToolRegistry([Tool("work", "work", SCHEMA, explode)]),
        permission_policy=make_permission(),
    )
    result = run(
        executor.execute(
            tool_name="work",
            arguments={"value": 1},
            principal=Principal("u1", frozenset({"operator"})),
            run_state=make_run_state(),
        )
    )

    assert result.failure.code == "internal_error"
    assert "abc123" not in result.observation()
    assert result.failure.internal_exception_type == "RuntimeError"


def test_loop_detector_stops_repeated_calls_within_one_run():
    executor = GuardedToolExecutor(
        tools=ToolRegistry([Tool("work", "work", SCHEMA, lambda value: value)]),
        permission_policy=make_permission(),
    )
    principal = Principal("u1", frozenset({"operator"}))
    run_state = GuardedRunState(
        budget=BudgetLedger(
            ExecutionBudget(max_tool_calls=3, max_elapsed_seconds=None)
        ),
        loop_detector=RepeatedToolCallDetector(max_identical_calls=1),
    )

    first = run(
        executor.execute(
            tool_name="work",
            arguments={"value": 1},
            principal=principal,
            run_state=run_state,
        )
    )
    second = run(
        executor.execute(
            tool_name="work",
            arguments={"value": 1},
            principal=principal,
            run_state=run_state,
        )
    )

    assert first.ok is True
    assert second.failure.code == "loop_detected"
    assert second.attempts == 0


def test_loop_history_does_not_leak_between_agent_runs():
    executor = GuardedToolExecutor(
        tools=ToolRegistry([Tool("work", "work", SCHEMA, lambda value: value)]),
        permission_policy=make_permission(),
    )
    principal = Principal("u1", frozenset({"operator"}))

    first_run = GuardedRunState(
        budget=BudgetLedger(ExecutionBudget(max_elapsed_seconds=None)),
        loop_detector=RepeatedToolCallDetector(max_identical_calls=1),
    )
    second_run = GuardedRunState(
        budget=BudgetLedger(ExecutionBudget(max_elapsed_seconds=None)),
        loop_detector=RepeatedToolCallDetector(max_identical_calls=1),
    )

    first = run(
        executor.execute(
            tool_name="work",
            arguments={"value": 1},
            principal=principal,
            run_state=first_run,
        )
    )
    second = run(
        executor.execute(
            tool_name="work",
            arguments={"value": 1},
            principal=principal,
            run_state=second_run,
        )
    )

    assert first.ok is True
    assert second.ok is True

import asyncio

import pytest

from tiny_agent import (
    BudgetExceededError,
    BudgetLedger,
    ExecutionBudget,
    RepeatedToolCallDetector,
    RetryPolicy,
    ToolInputError,
    ToolLoopDetectedError,
    TransientToolError,
    failure_from_exception,
    tool_call_fingerprint,
)


def test_unexpected_exception_message_is_redacted():
    failure = failure_from_exception(RuntimeError("postgres://user:secret@db/internal"))

    assert failure.code == "internal_error"
    assert failure.safe_message == "Tool execution failed."
    assert "secret" not in failure.observation()
    assert failure.internal_exception_type == "RuntimeError"


def test_asyncio_timeout_is_classified_as_retryable_timeout_across_python_versions():
    failure = failure_from_exception(asyncio.TimeoutError())

    assert failure.code == "timeout"
    assert failure.retryable is True


def test_explicit_safe_tool_error_can_cross_model_boundary():
    failure = failure_from_exception(TransientToolError("Upstream service is temporarily unavailable."))

    assert failure.code == "transient_error"
    assert failure.retryable is True
    assert "temporarily unavailable" in failure.observation()


def test_retry_policy_uses_bounded_exponential_backoff():
    policy = RetryPolicy(
        max_attempts=4,
        base_delay_seconds=1.0,
        max_delay_seconds=3.0,
        jitter_ratio=0.0,
    )

    assert policy.delay_for_retry(1) == 1.0
    assert policy.delay_for_retry(2) == 2.0
    assert policy.delay_for_retry(3) == 3.0


def test_budget_ledger_enforces_tool_and_retry_budgets():
    ledger = BudgetLedger(
        ExecutionBudget(
            max_tool_calls=1,
            max_retry_attempts=1,
            max_elapsed_seconds=None,
        )
    )

    ledger.consume_tool_call()
    ledger.consume_retry()

    with pytest.raises(BudgetExceededError):
        ledger.consume_tool_call()
    with pytest.raises(BudgetExceededError):
        ledger.consume_retry()


def test_budget_tracks_tokens_and_cost_when_provider_usage_is_available():
    ledger = BudgetLedger(
        ExecutionBudget(
            max_tool_calls=2,
            max_retry_attempts=0,
            max_elapsed_seconds=None,
            max_tokens=100,
            max_cost_usd=1.0,
        )
    )

    ledger.record_tokens(40)
    ledger.record_cost(0.25)
    assert ledger.tokens == 40
    assert ledger.cost_usd == 0.25

    with pytest.raises(BudgetExceededError):
        ledger.record_tokens(61)
    with pytest.raises(BudgetExceededError):
        ledger.record_cost(0.8)


def test_tool_call_fingerprint_is_key_order_independent():
    assert tool_call_fingerprint("search", {"q": "agent", "k": 3}) == tool_call_fingerprint(
        "search", {"k": 3, "q": "agent"}
    )


def test_non_json_tool_arguments_are_rejected_before_fingerprinting():
    with pytest.raises(ToolInputError):
        tool_call_fingerprint("bad", {"value": object()})


def test_repeated_call_detector_stops_exact_loops_before_global_budget():
    detector = RepeatedToolCallDetector(max_identical_calls=2)
    detector.observe("search", {"q": "same"})
    detector.observe("search", {"q": "same"})

    with pytest.raises(ToolLoopDetectedError, match="Repeated identical call"):
        detector.observe("search", {"q": "same"})

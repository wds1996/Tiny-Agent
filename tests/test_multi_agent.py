import asyncio
import threading

import pytest

from tiny_agent.multi_agent import (
    AgentInput,
    AgentSpec,
    ContextEnvelope,
    ContextPolicy,
    CoordinationBudget,
    CoordinationBudgetExceeded,
    CoordinationState,
    DelegationDeniedError,
    DelegationPolicy,
    HandoffLoopError,
    TeamRuntime,
    UnknownAgentError,
    coordination_metrics,
)


def _run(awaitable):
    return asyncio.run(awaitable)


def _agent(name, handler=None):
    return AgentSpec(
        name=name,
        description=f"{name} specialist",
        handler=handler or (lambda payload: f"{name}:{payload.task}"),
    )


def test_delegation_keeps_manager_active_and_projects_context():
    seen = {}

    def research(payload: AgentInput) -> str:
        seen.update(payload.context)
        return "research result"

    runtime = TeamRuntime(
        [_agent("manager"), _agent("research", research)],
        delegation_policy=DelegationPolicy(
            {"manager": frozenset({"research"})}
        ),
        context_policy=ContextPolicy(
            {"research": frozenset({"tenant_id"})}
        ),
    )
    state = CoordinationState(active_agent="manager")
    context = ContextEnvelope(
        shared={"tenant_id": "t-1", "api_key": "secret"},
        private_by_agent={
            "research": {"scratchpad": "r-only"},
            "manager": {"manager_secret": "m-only"},
        },
    )

    result = _run(
        runtime.delegate(
            source="manager",
            target="research",
            task="Find evidence",
            context=context,
            state=state,
        )
    )

    assert result.ok
    assert result.output == "research result"
    assert state.active_agent == "manager"
    assert seen == {
        "shared": {"tenant_id": "t-1"},
        "private": {"scratchpad": "r-only"},
    }


def test_handoff_changes_active_agent_only_after_success():
    runtime = TeamRuntime(
        [_agent("triage"), _agent("refund")],
        delegation_policy=DelegationPolicy(
            {"triage": frozenset({"refund"})}
        ),
    )
    state = CoordinationState(active_agent="triage")

    result = _run(
        runtime.handoff(
            source="triage",
            target="refund",
            task="Handle refund",
            context=ContextEnvelope(),
            state=state,
        )
    )

    assert result.ok
    assert state.active_agent == "refund"
    assert state.handoffs == 1


def test_failed_handoff_keeps_control_redacts_error_and_consumes_attempt_budget():
    def fail(_payload: AgentInput) -> str:
        raise RuntimeError("database_password=do-not-leak")

    runtime = TeamRuntime(
        [_agent("triage"), _agent("refund", fail)],
        delegation_policy=DelegationPolicy(
            {"triage": frozenset({"refund"})}
        ),
    )
    state = CoordinationState(active_agent="triage")

    result = _run(
        runtime.handoff(
            source="triage",
            target="refund",
            task="Handle refund",
            context=ContextEnvelope(),
            state=state,
        )
    )

    assert not result.ok
    assert result.output is None
    assert result.error_type == "RuntimeError"
    assert state.active_agent == "triage"
    assert state.agent_calls == 1
    assert state.handoffs == 1
    assert "do-not-leak" not in repr(result)


def test_delegation_policy_is_default_deny():
    runtime = TeamRuntime(
        [_agent("manager"), _agent("research")],
        delegation_policy=DelegationPolicy(),
    )
    state = CoordinationState(active_agent="manager")

    with pytest.raises(DelegationDeniedError):
        _run(
            runtime.delegate(
                source="manager",
                target="research",
                task="work",
                context=ContextEnvelope(),
                state=state,
            )
        )
    assert state.agent_calls == 0


def test_only_active_agent_can_initiate_coordination():
    runtime = TeamRuntime(
        [_agent("manager"), _agent("research")],
        delegation_policy=DelegationPolicy(
            {"research": frozenset({"manager"})}
        ),
    )
    state = CoordinationState(active_agent="manager")

    with pytest.raises(DelegationDeniedError):
        _run(
            runtime.delegate(
                source="research",
                target="manager",
                task="work",
                context=ContextEnvelope(),
                state=state,
            )
        )


def test_repeated_handoff_edge_is_bounded():
    runtime = TeamRuntime(
        [_agent("a"), _agent("b")],
        delegation_policy=DelegationPolicy(
            {
                "a": frozenset({"b"}),
                "b": frozenset({"a"}),
            }
        ),
    )
    state = CoordinationState(
        active_agent="a",
        budget=CoordinationBudget(max_handoffs=4, max_same_handoff_edge=1),
    )

    assert _run(runtime.handoff(source="a", target="b", task="1", context=ContextEnvelope(), state=state)).ok
    assert _run(runtime.handoff(source="b", target="a", task="2", context=ContextEnvelope(), state=state)).ok

    with pytest.raises(HandoffLoopError):
        _run(runtime.handoff(source="a", target="b", task="3", context=ContextEnvelope(), state=state))


def test_parallel_fan_out_preserves_assignment_order():
    async def slow(payload: AgentInput) -> str:
        await asyncio.sleep(0.01)
        return f"slow:{payload.task}"

    async def fast(payload: AgentInput) -> str:
        await asyncio.sleep(0)
        return f"fast:{payload.task}"

    runtime = TeamRuntime(
        [_agent("manager"), _agent("slow", slow), _agent("fast", fast)],
        delegation_policy=DelegationPolicy(
            {"manager": frozenset({"slow", "fast"})}
        ),
    )
    state = CoordinationState(active_agent="manager")

    results = _run(
        runtime.fan_out(
            source="manager",
            assignments=(("slow", "A"), ("fast", "B")),
            context=ContextEnvelope(),
            state=state,
        )
    )

    assert [item.target for item in results] == ["slow", "fast"]
    assert [item.output for item in results] == ["slow:A", "fast:B"]
    assert state.active_agent == "manager"


def test_sync_agent_handler_runs_off_event_loop_thread():
    main_thread = threading.get_ident()

    def sync_worker(_payload: AgentInput) -> str:
        return str(threading.get_ident())

    runtime = TeamRuntime(
        [_agent("manager"), _agent("worker", sync_worker)],
        delegation_policy=DelegationPolicy(
            {"manager": frozenset({"worker"})}
        ),
    )
    state = CoordinationState(active_agent="manager")

    result = _run(
        runtime.delegate(
            source="manager",
            target="worker",
            task="work",
            context=ContextEnvelope(),
            state=state,
        )
    )

    assert result.ok
    assert int(result.output) != main_thread


def test_parallel_batch_failure_does_not_partially_consume_budget():
    runtime = TeamRuntime(
        [_agent("manager"), _agent("allowed"), _agent("denied")],
        delegation_policy=DelegationPolicy(
            {"manager": frozenset({"allowed"})}
        ),
    )
    state = CoordinationState(active_agent="manager")

    with pytest.raises(DelegationDeniedError):
        _run(
            runtime.fan_out(
                source="manager",
                assignments=(("allowed", "A"), ("denied", "B")),
                context=ContextEnvelope(),
                state=state,
            )
        )
    assert state.agent_calls == 0
    assert state.interactions == []


def test_parallel_limit_is_checked_before_execution():
    runtime = TeamRuntime(
        [_agent("manager"), _agent("a"), _agent("b")],
        delegation_policy=DelegationPolicy(
            {"manager": frozenset({"a", "b"})}
        ),
    )
    state = CoordinationState(
        active_agent="manager",
        budget=CoordinationBudget(max_parallel=1),
    )

    with pytest.raises(CoordinationBudgetExceeded):
        _run(
            runtime.fan_out(
                source="manager",
                assignments=(("a", "A"), ("b", "B")),
                context=ContextEnvelope(),
                state=state,
            )
        )
    assert state.agent_calls == 0


def test_unknown_agent_does_not_consume_budget():
    runtime = TeamRuntime(
        [_agent("manager"), _agent("known")],
        delegation_policy=DelegationPolicy(
            {"manager": frozenset({"missing"})}
        ),
    )
    state = CoordinationState(active_agent="manager")

    with pytest.raises(UnknownAgentError):
        _run(
            runtime.delegate(
                source="manager",
                target="missing",
                task="work",
                context=ContextEnvelope(),
                state=state,
            )
        )
    assert state.agent_calls == 0


def test_non_text_agent_output_is_model_safe_failure():
    runtime = TeamRuntime(
        [_agent("manager"), _agent("bad", lambda _payload: {"secret": "value"})],
        delegation_policy=DelegationPolicy(
            {"manager": frozenset({"bad"})}
        ),
    )
    state = CoordinationState(active_agent="manager")

    result = _run(
        runtime.delegate(
            source="manager",
            target="bad",
            task="work",
            context=ContextEnvelope(),
            state=state,
        )
    )

    assert result.status == "failed"
    assert result.error_type == "AgentOutputError"
    assert result.output is None


def test_coordination_metrics_separate_attempts_from_successful_handoffs():
    def fail(_payload: AgentInput) -> str:
        raise RuntimeError("hidden")

    runtime = TeamRuntime(
        [_agent("manager"), _agent("research"), _agent("broken", fail)],
        delegation_policy=DelegationPolicy(
            {
                "manager": frozenset({"research", "broken"}),
                "research": frozenset({"manager"}),
            }
        ),
    )
    state = CoordinationState(active_agent="manager")
    _run(runtime.delegate(source="manager", target="research", task="work", context=ContextEnvelope(), state=state))
    _run(runtime.handoff(source="manager", target="broken", task="fail", context=ContextEnvelope(), state=state))

    assert coordination_metrics(state) == {
        "agent_call_attempts": 2.0,
        "handoff_attempts": 1.0,
        "successful_handoffs": 0.0,
        "unique_agents": 3.0,
        "failed_agent_calls": 1.0,
    }

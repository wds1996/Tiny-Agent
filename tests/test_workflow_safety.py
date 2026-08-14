from tiny_agent.workflows import (
    Plan,
    PlanExecutorWorkflow,
    PlanStep,
    StepFailure,
)


class StaticPlanner:
    def __init__(self, plan):
        self.plan_value = plan

    def plan(self, task):
        return self.plan_value


class SafeFailureRunner:
    def run(self, *, task, step, completed):
        raise StepFailure("Primary evidence source is unavailable; use a fallback.")


class UnexpectedFailureRunner:
    def run(self, *, task, step, completed):
        raise RuntimeError("secret-internal-path=/srv/private/data")


def _single_step_plan():
    return Plan(
        objective="Demonstrate safe failure handling",
        steps=(PlanStep("inspect", "Inspect one source."),),
    )


def test_expected_step_failure_keeps_explicit_model_safe_message():
    workflow = PlanExecutorWorkflow(
        planner=StaticPlanner(_single_step_plan()),
        step_runner=SafeFailureRunner(),
        max_replans=0,
    )

    result = workflow.run("Demonstrate expected failure")

    assert result.success is False
    assert result.failure_reason == (
        "StepFailure: Primary evidence source is unavailable; use a fallback."
    )


def test_unexpected_exception_redacts_internal_message_from_workflow_state():
    workflow = PlanExecutorWorkflow(
        planner=StaticPlanner(_single_step_plan()),
        step_runner=UnexpectedFailureRunner(),
        max_replans=0,
    )

    result = workflow.run("Demonstrate unexpected failure")

    assert result.success is False
    assert result.failure_reason == "RuntimeError"
    assert "secret-internal-path" not in result.failure_reason

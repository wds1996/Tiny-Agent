import pytest

from tiny_agent.workflows import Plan, PlanExecutorWorkflow, PlanStep


class StaticPlanner:
    def __init__(self, plan):
        self.plan_value = plan

    def plan(self, task):
        return self.plan_value


class SuccessRunner:
    def run(self, *, task, step, completed):
        return f"done:{step.id}"


def test_workflow_rejects_plan_longer_than_application_budget():
    plan = Plan(
        objective="Too many steps",
        steps=(
            PlanStep("a", "A"),
            PlanStep("b", "B"),
            PlanStep("c", "C"),
        ),
    )
    workflow = PlanExecutorWorkflow(
        planner=StaticPlanner(plan),
        step_runner=SuccessRunner(),
        max_plan_steps=2,
    )

    with pytest.raises(ValueError, match="max_plan_steps=2"):
        workflow.run("Bound the plan")


def test_workflow_rejects_duplicate_step_ids():
    plan = Plan(
        objective="Duplicate ids",
        steps=(
            PlanStep("same", "First"),
            PlanStep("same", "Second"),
        ),
    )
    workflow = PlanExecutorWorkflow(
        planner=StaticPlanner(plan),
        step_runner=SuccessRunner(),
    )

    with pytest.raises(ValueError, match="step ids must be unique"):
        workflow.run("Reject duplicate ids")


def test_total_step_budget_stops_execution_even_when_steps_would_succeed():
    plan = Plan(
        objective="Three steps",
        steps=(
            PlanStep("a", "A"),
            PlanStep("b", "B"),
            PlanStep("c", "C"),
        ),
    )
    workflow = PlanExecutorWorkflow(
        planner=StaticPlanner(plan),
        step_runner=SuccessRunner(),
        max_plan_steps=3,
        max_total_steps=2,
    )

    result = workflow.run("Stop after two steps")

    assert result.success is False
    assert [item.step.id for item in result.results] == ["a", "b"]
    assert result.failure_reason == "Execution exceeded max_total_steps=2"

from tiny_agent.workflows import (
    LLMRouter,
    Plan,
    PlanExecutorWorkflow,
    PlanStep,
    RouteDecision,
    RoutingWorkflow,
    RuleRouter,
)


class FakeDecisionModel:
    def __init__(self, decisions):
        self._decisions = iter(decisions)

    def decide(self, **kwargs):
        return next(self._decisions)


class StaticPlanner:
    def __init__(self, plan):
        self._plan = plan

    def plan(self, task):
        return self._plan


class RecordingRunner:
    def __init__(self, *, fail_on=None):
        self.fail_on = fail_on
        self.calls = []

    def run(self, *, task, step, completed):
        self.calls.append((step.id, tuple(result.step.id for result in completed)))
        if step.id == self.fail_on:
            raise RuntimeError(f"step {step.id} failed")
        return f"completed {step.id}"


class OneShotReplanner:
    def __init__(self, plan):
        self.plan = plan
        self.calls = 0

    def replan(self, *, task, completed, failure):
        self.calls += 1
        return self.plan


def test_rule_router_uses_deterministic_rule_before_fallback():
    router = RuleRouter(
        [
            ("billing", lambda request: "refund" in request.lower()),
            ("technical", lambda request: "crash" in request.lower()),
        ],
        fallback="general",
    )

    assert router.route("Please refund my order").route == "billing"
    assert router.route("The app crashes").route == "technical"
    assert router.route("What are your opening hours?").route == "general"


def test_llm_router_uses_structured_decision_and_validates_route():
    router = LLMRouter(
        FakeDecisionModel(
            [{"route": "technical", "reason": "The user reports a crash."}]
        ),
        routes={
            "billing": "Refunds, invoices, and payment problems.",
            "technical": "Bugs, errors, and product failures.",
            "general": "General product questions.",
        },
    )

    decision = router.route("The desktop app crashes after login.")

    assert decision == RouteDecision(
        route="technical",
        reason="The user reports a crash.",
    )


def test_routing_workflow_keeps_dispatch_deterministic_after_decision():
    class FixedRouter:
        def route(self, request):
            return RouteDecision(route="technical", reason="test")

    workflow = RoutingWorkflow(
        FixedRouter(),
        handlers={
            "technical": lambda request: f"TECH: {request}",
            "general": lambda request: f"GENERAL: {request}",
        },
    )

    result = workflow.run("App crashes")

    assert result.decision.route == "technical"
    assert result.output == "TECH: App crashes"


def test_plan_executor_runs_fixed_plan_without_replanning_on_success():
    plan = Plan(
        objective="Prepare an incident brief",
        steps=(
            PlanStep("health", "Inspect current service health."),
            PlanStep("deploys", "Inspect recent deployments."),
            PlanStep("brief", "Draft the incident brief."),
        ),
    )
    runner = RecordingRunner()
    workflow = PlanExecutorWorkflow(
        planner=StaticPlanner(plan),
        step_runner=runner,
        max_plan_steps=4,
        max_total_steps=6,
        max_replans=1,
    )

    result = workflow.run("Prepare an incident brief")

    assert result.success is True
    assert result.replans == 0
    assert [item.step.id for item in result.results] == [
        "health",
        "deploys",
        "brief",
    ]
    assert runner.calls == [
        ("health", ()),
        ("deploys", ("health",)),
        ("brief", ("health", "deploys")),
    ]


def test_plan_executor_replans_only_after_failure_and_executes_remaining_plan():
    initial = Plan(
        objective="Prepare an incident brief",
        steps=(
            PlanStep("health", "Inspect current service health."),
            PlanStep("primary_logs", "Read the primary log service."),
            PlanStep("brief", "Draft the incident brief."),
        ),
    )
    remaining = Plan(
        objective="Finish the incident brief using a fallback source",
        steps=(
            PlanStep("fallback_logs", "Read the fallback log archive."),
            PlanStep("brief_after_fallback", "Draft the incident brief."),
        ),
    )
    runner = RecordingRunner(fail_on="primary_logs")
    replanner = OneShotReplanner(remaining)
    workflow = PlanExecutorWorkflow(
        planner=StaticPlanner(initial),
        step_runner=runner,
        replanner=replanner,
        max_plan_steps=4,
        max_total_steps=6,
        max_replans=1,
    )

    result = workflow.run("Prepare an incident brief")

    assert result.success is True
    assert result.replans == 1
    assert replanner.calls == 1
    assert [item.step.id for item in result.results] == [
        "health",
        "primary_logs",
        "fallback_logs",
        "brief_after_fallback",
    ]


def test_plan_executor_stops_when_replanning_budget_is_zero():
    plan = Plan(
        objective="Do a bounded task",
        steps=(PlanStep("fail", "This step fails."),),
    )
    workflow = PlanExecutorWorkflow(
        planner=StaticPlanner(plan),
        step_runner=RecordingRunner(fail_on="fail"),
        replanner=OneShotReplanner(plan),
        max_plan_steps=2,
        max_total_steps=2,
        max_replans=0,
    )

    result = workflow.run("Do a bounded task")

    assert result.success is False
    assert result.replans == 0
    assert "RuntimeError" in result.failure_reason

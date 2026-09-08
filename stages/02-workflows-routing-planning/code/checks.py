from __future__ import annotations

import unittest
from types import SimpleNamespace

from pydantic import ValidationError

from planning import (
    Operation,
    Plan,
    PlanExecutor,
    PlanStep,
    ScriptedPlanner,
    StepFailure,
    run_with_replanning,
)
from deepseek_decisions import DeepSeekPlanner
from routing import (
    HybridRouter,
    Route,
    RouteDecision,
    SemanticRouter,
    dispatch,
)


class FailIfCalledRouter(SemanticRouter):
    def decide(self, request: str) -> RouteDecision:
        raise AssertionError(f"semantic router should not be called: {request}")


class FixedSemanticRouter(SemanticRouter):
    def __init__(self, route: Route) -> None:
        self.route_value = route
        self.calls = 0

    def decide(self, request: str) -> RouteDecision:
        self.calls += 1
        return RouteDecision(
            route=self.route_value,
            reason=f"fixed semantic decision for: {request}",
        )


class PlannerResponsesAPI:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def parse(self, **request: object) -> object:
        self.requests.append(request)
        if len(self.requests) == 1:
            return SimpleNamespace(
                status="completed",
                output_parsed=Plan.model_validate(
                    {
                        "goal": "weather",
                        "steps": [
                            {
                                "step_id": "weather",
                                "operation": "read_primary_weather",
                                "city": "Tokyo",
                            },
                            {
                                "step_id": "convert",
                                "operation": "convert_temperature",
                                "depends_on": ["weather"],
                                "source_step": "weather",
                            },
                            {
                                "step_id": "brief",
                                "operation": "write_brief",
                                "depends_on": ["weather", "convert"],
                                "source_step": "weather",
                                "conversion_step": "convert",
                                "city": "Tokyo",
                            },
                        ],
                    }
                ),
            )

        return SimpleNamespace(
            status="completed",
            output_parsed=ScriptedPlanner().make_plan("weather"),
        )


class Stage02Checks(unittest.TestCase):
    def test_deepseek_planner_retries_a_schema_invalid_plan_once(self) -> None:
        responses = PlannerResponsesAPI()
        planner = DeepSeekPlanner(
            client=SimpleNamespace(responses=responses), model="test-model"
        )

        plan = planner.make_plan("weather")

        self.assertEqual(plan.steps[-1].step_id, "brief")
        self.assertEqual(len(responses.requests), 2)
        self.assertIn(
            "previous plan was rejected",
            str(responses.requests[1]["instructions"]),
        )

    def test_explicit_rule_bypasses_semantic_router(self) -> None:
        router = HybridRouter(FailIfCalledRouter())
        result = router.route("weather: Tokyo")

        self.assertEqual(result.route, Route.WEATHER)
        self.assertEqual(result.source, "rule")

    def test_ambiguous_language_uses_semantic_router(self) -> None:
        semantic = FixedSemanticRouter(Route.ACCOUNT)
        router = HybridRouter(semantic)

        result = router.route("I think there is something wrong with my invoice.")

        self.assertEqual(result.route, Route.ACCOUNT)
        self.assertEqual(result.source, "semantic")
        self.assertEqual(semantic.calls, 1)

    def test_dispatch_is_deterministic_after_route_decision(self) -> None:
        semantic = FixedSemanticRouter(Route.GENERAL)
        router = HybridRouter(semantic)

        request = "Help me rewrite this sentence."
        result = router.route(request)
        output = dispatch(request, result)

        self.assertEqual(
            output,
            "general handler received: Help me rewrite this sentence.",
        )

    def test_plan_rejects_forward_references(self) -> None:
        with self.assertRaises(ValidationError):
            Plan(
                goal="bad plan",
                steps=[
                    PlanStep(
                        step_id="convert",
                        operation=Operation.CONVERT_TEMPERATURE,
                        depends_on=["weather"],
                        source_step="weather",
                    ),
                    PlanStep(
                        step_id="weather",
                        operation=Operation.READ_BACKUP_WEATHER,
                        city="Tokyo",
                    ),
                ],
            )

    def test_plan_rejects_duplicate_step_ids(self) -> None:
        with self.assertRaises(ValidationError):
            Plan(
                goal="duplicate IDs",
                steps=[
                    PlanStep(
                        step_id="same",
                        operation=Operation.READ_BACKUP_WEATHER,
                        city="Tokyo",
                    ),
                    PlanStep(
                        step_id="same",
                        operation=Operation.READ_BACKUP_WEATHER,
                        city="Paris",
                    ),
                ],
            )

    def test_failure_stops_when_replanning_is_disabled(self) -> None:
        with self.assertRaises(StepFailure):
            run_with_replanning(
                "weather",
                planner=ScriptedPlanner(),
                executor=PlanExecutor(primary_available=False),
                max_replans=0,
            )

    def test_one_bounded_replan_recovers_from_observed_failure(self) -> None:
        answer = run_with_replanning(
            "weather",
            planner=ScriptedPlanner(),
            executor=PlanExecutor(primary_available=False),
            max_replans=1,
        )

        self.assertEqual(answer, "Tokyo: 18.0°C / 64.4°F, cloudy.")

    def test_execution_budget_is_enforced_by_application(self) -> None:
        plan = ScriptedPlanner().make_plan(
            "weather",
            failure=StepFailure(
                step_id="weather",
                operation=Operation.READ_PRIMARY_WEATHER,
                message="primary unavailable",
            ),
        )

        executor = PlanExecutor(
            primary_available=False,
            max_execution_steps=2,
        )

        with self.assertRaises(RuntimeError):
            executor.execute(plan)


if __name__ == "__main__":
    unittest.main(verbosity=2)

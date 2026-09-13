"""Deterministic behavior checks. No test sends a paid model request."""
from __future__ import annotations

from dataclasses import replace
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from deepseek_decisions import (
    DeepSeekPlanner, DeepSeekSemanticRouter, ProviderDecisionError, StructuredClient, create_client,
)
from planning import (
    Failure, Plan, PlanExecutor, PlanRejected, PlanRun, PlanStep, ScriptedPlanner,
    run_with_replanning, validate_plan,
)
from routing import (
    EXAMPLES, HybridRouter, RouteDecision, ScriptedSemanticRouter, dispatch, validate_for_request,
)
from workflow import Reading, WeatherService, WeatherTask, convert_temperature, render_brief, run_workflow


def task(cities=("Tokyo", "Paris"), fahrenheit=True, language="en"):
    return WeatherTask(cities=cities, fahrenheit=fahrenheit, language=language)


def plan_for(request=None, completed=None, failures=()):
    return ScriptedPlanner().make_plan(request or task(), completed=completed or {}, failures=failures)


def changed_step(plan, index, **changes):
    data = plan.model_dump()
    steps = list(data["steps"])
    steps[index] = {**steps[index], **changes}
    data["steps"] = tuple(steps)
    return Plan.model_validate(data)


class FixedRouter:
    def __init__(self, decision):
        self.decision = decision
        self.calls = 0

    def decide(self, request):
        self.calls += 1
        if isinstance(self.decision, Exception):
            raise self.decision
        return self.decision


class FixedPlanner:
    def __init__(self, plan):
        self.plan = plan
        self.calls = 0

    def make_plan(self, request, *, completed, failures):
        self.calls += 1
        if isinstance(self.plan, Exception):
            raise self.plan
        return self.plan


class FakeResponses:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.requests = []

    def parse(self, **request):
        self.requests.append(request)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


def response(parsed=None, status="completed", output=()):
    return SimpleNamespace(status=status, output=list(output), output_parsed=parsed)


def model_with(*outputs, max_calls=3):
    api = FakeResponses(*outputs)
    model = StructuredClient(client=SimpleNamespace(responses=api), model="test-model", max_calls=max_calls)
    return model, api


class WorkflowChecks(unittest.TestCase):
    def test_form_reads_and_converts_actual_data(self):
        service = WeatherService()
        self.assertIn("64.4°F", run_workflow(task(("Tokyo",)), service))
        self.assertEqual(service.calls, [("primary", "Tokyo")])

    def test_checkbox_off_does_not_convert(self):
        with patch("workflow.convert_temperature", side_effect=AssertionError("must not convert")):
            answer = run_workflow(task(("Paris",), False), WeatherService())
        self.assertIn("12.0°C", answer)
        self.assertNotIn("°F", answer)

    def test_changed_record_changes_both_units(self):
        service = WeatherService()
        service.records["Tokyo"] = (22.0, "cloudy")
        text = run_workflow(task(("Tokyo",)), service)
        self.assertIn("22.0°C / 71.6°F", text)
        self.assertNotIn("64.4", text)

    def test_two_city_order_and_difference(self):
        text = run_workflow(task(("Paris", "Tokyo")), WeatherService())
        self.assertTrue(text.startswith("Paris:"))
        self.assertIn("Tokyo is warmer by 6.0°C", text)

    def test_equal_temperatures_do_not_pick_a_winner(self):
        service = WeatherService()
        service.records["Paris"] = (18.0, "light rain")
        self.assertIn("temperatures are equal", run_workflow(task(), service))

    def test_task_rejects_duplicate_unsupported_and_wrong_boolean(self):
        for fields in ({"cities": ("Tokyo", "Tokyo")}, {"cities": ("Rome",)},
                       {"cities": ("Tokyo",), "fahrenheit": "false"}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                WeatherTask(**fields)

    def test_bypassed_model_construction_is_revalidated(self):
        bad = WeatherTask.model_construct(cities=("Rome",), fahrenheit=False, language="en")
        service = WeatherService()
        with self.assertRaises(ValidationError):
            run_workflow(bad, service)
        self.assertEqual(service.calls, [])

    def test_nonfinite_source_never_reaches_report(self):
        for value in (float("nan"), float("inf"), True, "18", 200):
            with self.subTest(value=value):
                service = WeatherService()
                service.records["Tokyo"] = (value, "cloudy")
                with self.assertRaises(ValueError):
                    run_workflow(task(("Tokyo",)), service)

    def test_snapshot_and_unit_mismatch_rejected(self):
        tokyo = Reading("Tokyo", 18.0, "cloudy", "primary")
        paris = Reading("Paris", 12.0, "rain", "backup", snapshot="different")
        with self.assertRaises(ValueError):
            render_brief(task(fahrenheit=False), (tokyo, paris))
        with self.assertRaises(ValueError):
            render_brief(task(("Tokyo",)), (tokyo,))

    def test_conversion_keeps_source_record_unchanged(self):
        reading = WeatherService().read("Tokyo")
        converted = convert_temperature(reading)
        self.assertIsNone(reading.temperature_f)
        self.assertEqual(converted.temperature_f, 64.4)
        self.assertEqual(converted.snapshot, reading.snapshot)


class RoutingChecks(unittest.TestCase):
    def test_validated_form_never_calls_semantic_router(self):
        model = FixedRouter(AssertionError("must not call"))
        result = HybridRouter(model).route(form=task(("Tokyo",)))
        self.assertEqual(result.source, "form")
        self.assertEqual(model.calls, 0)

    def test_invalid_form_does_not_fall_back_to_model(self):
        model = FixedRouter(AssertionError("must not call"))
        bad = WeatherTask.model_construct(cities=("Rome",), fahrenheit=False, language="en")
        with self.assertRaises(ValidationError):
            HybridRouter(model).route(form=bad)
        self.assertEqual(model.calls, 0)

    def test_ambiguous_input_channels_are_rejected(self):
        router = HybridRouter(ScriptedSemanticRouter())
        for kwargs in ({}, {"request": "hello", "form": task()}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                router.route(**kwargs)

    def test_blank_long_and_nontext_requests_do_not_call_model(self):
        model = FixedRouter(None)
        for request in (" ", "x" * 1001, 123):
            with self.subTest(request=str(request)[:10]), self.assertRaises(ValueError):
                HybridRouter(model).route(request=request)
        self.assertEqual(model.calls, 0)

    def test_fixture_route_actually_produces_weather(self):
        for language in EXAMPLES:
            for example in ("weather", "compare"):
                with self.subTest(language=language, example=example):
                    result = HybridRouter(ScriptedSemanticRouter()).route(request=EXAMPLES[language][example])
                    service = WeatherService()
                    answer = dispatch(result, service, language=language)
                    self.assertIn("64.4°F", answer)
                    self.assertEqual(len(service.calls), 1 if example == "weather" else 2)

    def test_help_and_clarify_do_not_read_weather(self):
        for example in ("help", "clarify"):
            result = HybridRouter(ScriptedSemanticRouter()).route(request=EXAMPLES["en"][example])
            service = WeatherService()
            self.assertTrue(dispatch(result, service, language="en"))
            self.assertEqual(service.calls, [])

    def test_route_cannot_invent_an_extra_city(self):
        decision = RouteDecision(route="compare", cities=("Tokyo", "Paris"), reason="compare")
        with self.assertRaises(ValueError):
            validate_for_request(decision, "Read only Tokyo.")

    def test_inconsistent_and_unknown_destinations_rejected(self):
        for fields in ({"route": "shell"}, {"route": "weather"},
                       {"route": "help", "cities": ("Tokyo",)},
                       {"route": "clarify", "fahrenheit": True}, {"route": "help", "reason": " "}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                RouteDecision(**({"reason": "test"} | fields))

    def test_schema_is_not_a_semantic_oracle(self):
        # A valid weather decision can still misread an unrelated Tokyo request.
        decision = RouteDecision(route="weather", cities=("Tokyo",), reason="wrong interpretation")
        self.assertEqual(validate_for_request(decision, "Write a poem about Tokyo."), decision)

    def test_offline_router_does_not_pretend_to_understand_new_text(self):
        with self.assertRaises(ValueError):
            ScriptedSemanticRouter().decide("arbitrary new wording")


class PlanningChecks(unittest.TestCase):
    def assert_rejected_before_execution(self, plan):
        service = WeatherService()
        result = run_with_replanning(task(), planner=FixedPlanner(plan), executor=PlanExecutor(service))
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.execution_steps, 0)
        self.assertEqual(service.calls, [])

    def test_plan_structure_uses_only_references(self):
        plan = plan_for()
        expected = PlanStep(
            step_id="fahrenheit_tokyo",
            operation="convert_temperature",
            inputs=("weather_tokyo",),
        )
        self.assertEqual(plan.steps[2], expected)
        self.assertNotIn("temperature_c", plan.model_dump_json())

    def test_all_requested_city_unit_variants(self):
        for cities in (("Tokyo",), ("Paris",), ("Tokyo", "Paris"), ("Paris", "Tokyo")):
            for fahrenheit in (False, True):
                with self.subTest(cities=cities, fahrenheit=fahrenheit):
                    request = task(cities, fahrenheit)
                    run = run_with_replanning(request, planner=ScriptedPlanner(), executor=PlanExecutor(WeatherService()))
                    self.assertEqual(run.status, "completed")
                    self.assertEqual(run.answer, run_workflow(request, WeatherService()))
                    self.assertEqual(run.execution_steps, len(cities) * (2 if fahrenheit else 1) + 1)

    def test_replanning_reuses_the_completed_tokyo_read(self):
        service = WeatherService(unavailable=(("primary", "Paris"),))
        run = run_with_replanning(task(), planner=ScriptedPlanner(), executor=PlanExecutor(service))
        self.assertEqual(run.status, "completed")
        self.assertEqual((run.plan_calls, run.execution_steps), (2, 6))
        self.assertEqual(service.calls, [("primary", "Tokyo"), ("primary", "Paris"), ("backup", "Paris")])
        self.assertEqual(run.completed["weather_tokyo"].source, "primary")
        self.assertIn("53.6°F", run.answer)

    def test_replanning_uses_changed_observations_not_hardcoded_numbers(self):
        service = WeatherService(unavailable=(("primary", "Paris"),))
        service.records["Tokyo"] = (22.0, "cloudy")
        run = run_with_replanning(task(), planner=ScriptedPlanner(), executor=PlanExecutor(service))
        self.assertIn("71.6°F", run.answer)
        self.assertIn("10.0°C", run.answer)

    def test_replanning_off_preserves_successful_prefix(self):
        service = WeatherService(unavailable=(("primary", "Paris"),))
        run = run_with_replanning(task(), planner=ScriptedPlanner(), executor=PlanExecutor(service), max_replans=0)
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.error, "SourceUnavailable")
        self.assertIsNone(run.answer)
        self.assertEqual(set(run.completed), {"weather_tokyo"})
        self.assertEqual((run.plan_calls, run.execution_steps), (1, 2))

    def test_both_sources_fail_without_partial_success_claim(self):
        service = WeatherService(unavailable=(("primary", "Paris"), ("backup", "Paris")))
        run = run_with_replanning(task(), planner=ScriptedPlanner(), executor=PlanExecutor(service))
        self.assertEqual(run.status, "failed")
        self.assertIsNone(run.answer)
        self.assertEqual(len(run.failures), 2)
        self.assertEqual(run.execution_steps, 3)

    def test_more_replans_do_not_authorize_known_failed_sources(self):
        service = WeatherService(unavailable=(("primary", "Paris"), ("backup", "Paris")))
        run = run_with_replanning(task(), planner=ScriptedPlanner(), executor=PlanExecutor(service), max_replans=2)
        self.assertEqual(run.error, "PlanRejected")
        self.assertEqual(run.plan_calls, 3)
        self.assertEqual(len(service.calls), 3)

    def test_execution_budget_is_shared_across_replans(self):
        service = WeatherService(unavailable=(("primary", "Paris"),))
        run = run_with_replanning(task(), planner=ScriptedPlanner(), executor=PlanExecutor(service), max_execution_steps=3)
        self.assertEqual(run.error, "ExecutionBudgetExceeded")
        self.assertEqual(run.execution_steps, 3)
        self.assertEqual(set(run.completed), {"weather_tokyo", "weather_paris"})
        self.assertIsNone(run.answer)

    def test_no_extra_plan_when_execution_budget_is_already_empty(self):
        service = WeatherService(unavailable=(("primary", "Paris"),))
        run = run_with_replanning(task(), planner=ScriptedPlanner(), executor=PlanExecutor(service), max_execution_steps=2)
        self.assertEqual(run.plan_calls, 1)
        self.assertEqual(run.error, "ExecutionBudgetExceeded")

    def test_zero_budget_never_calls_planner(self):
        planner = FixedPlanner(AssertionError("not called"))
        run = run_with_replanning(task(), planner=planner, executor=PlanExecutor(WeatherService()), max_execution_steps=0)
        self.assertEqual(planner.calls, 0)
        self.assertEqual(run.execution_steps, 0)

    def test_limits_reject_bool_fraction_and_negative(self):
        for field in ("max_replans", "max_execution_steps"):
            for value in (True, 1.5, -1):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    run_with_replanning(task(), planner=ScriptedPlanner(), executor=PlanExecutor(WeatherService()), **{field: value})

    def test_forward_reference_rejected_before_any_read(self):
        plan = plan_for()
        steps = list(plan.steps)
        steps[0], steps[2] = steps[2], steps[0]
        self.assert_rejected_before_execution(Plan(goal="bad order", steps=tuple(steps)))

    def test_cyclic_reference_rejected(self):
        self.assert_rejected_before_execution(changed_step(plan_for(), 2, inputs=("fahrenheit_paris",)))

    def test_duplicate_step_ids_rejected(self):
        with self.assertRaises(ValidationError):
            changed_step(plan_for(), 1, step_id="weather_tokyo")

    def test_missing_final_brief_rejected_before_any_read(self):
        plan = plan_for()
        self.assert_rejected_before_execution(Plan(goal="unfinished", steps=plan.steps[:-1]))

    def test_wrong_unit_in_final_brief_rejected(self):
        self.assert_rejected_before_execution(changed_step(plan_for(), 4, inputs=("weather_tokyo", "weather_paris")))

    def test_missing_city_in_final_brief_rejected(self):
        self.assert_rejected_before_execution(changed_step(plan_for(), 4, inputs=("fahrenheit_tokyo",)))

    def test_conversion_cannot_consume_another_conversion(self):
        self.assert_rejected_before_execution(changed_step(plan_for(), 3, inputs=("fahrenheit_tokyo",)))

    def test_backup_needs_a_real_failure_for_that_city(self):
        plan = changed_step(plan_for(), 0, source="backup")
        self.assert_rejected_before_execution(plan)
        with self.assertRaises(PlanRejected):
            validate_plan(plan, task(), {}, (Failure("x", "Paris", "primary"),))

    def test_unrequested_city_rejected(self):
        with self.assertRaises(PlanRejected):
            validate_plan(plan_for(), task(("Tokyo",)), {}, ())

    def test_completed_result_cannot_be_overwritten(self):
        completed = {"weather_tokyo": WeatherService().read("Tokyo")}
        with self.assertRaises(PlanRejected):
            validate_plan(plan_for(), task(), completed, ())

    def test_completed_results_are_not_reread_under_a_new_id(self):
        completed = {"old_tokyo": WeatherService().read("Tokyo")}
        with self.assertRaises(PlanRejected):
            validate_plan(plan_for(), task(), completed, ())

    def test_plan_step_does_not_accept_invented_temperature(self):
        with self.assertRaises(ValidationError):
            PlanStep(step_id="convert", operation="convert_temperature", inputs=("weather",), temperature_c=99)

    def test_unknown_operations_are_not_executable(self):
        with self.assertRaises(ValidationError):
            PlanStep(step_id="hack", operation="run_shell")

    def test_plan_length_is_bounded(self):
        with self.assertRaises(ValidationError):
            Plan(goal="too many", steps=plan_for().steps + (PlanStep(step_id="extra", operation="write_brief", inputs=("weather_tokyo",)),))

    def test_unchecked_plan_objects_are_revalidated(self):
        step = PlanStep.model_construct(step_id="x", operation="run_shell", inputs=(), city=None, source=None)
        self.assert_rejected_before_execution(Plan.model_construct(goal="invalid", steps=(step,)))

    def test_unexpected_step_error_is_not_replanned(self):
        service = WeatherService()
        service.records["Paris"] = (float("nan"), "rain")
        run = run_with_replanning(task(), planner=ScriptedPlanner(), executor=PlanExecutor(service))
        self.assertEqual(run.plan_calls, 1)
        self.assertEqual(run.error, "ValueError")
        self.assertEqual(set(run.completed), {"weather_tokyo"})

    def test_planner_exception_is_not_retried_or_echoed(self):
        planner = FixedPlanner(RuntimeError("secret-token-example"))
        run = run_with_replanning(task(), planner=planner, executor=PlanExecutor(WeatherService()))
        self.assertEqual(planner.calls, 1)
        self.assertEqual(run.error, "RuntimeError")
        self.assertNotIn("secret", str(run))

    def test_runs_do_not_share_results_or_counters(self):
        executor = PlanExecutor(WeatherService())
        first = run_with_replanning(task(), planner=ScriptedPlanner(), executor=executor)
        second = run_with_replanning(task(("Paris",), False), planner=ScriptedPlanner(), executor=executor)
        self.assertEqual(second.execution_steps, 2)
        self.assertEqual(set(second.completed), {"weather_paris"})
        self.assertEqual(first.execution_steps, 5)


class AdapterChecks(unittest.TestCase):
    def test_router_uses_the_expected_schema_and_one_call(self):
        decision = RouteDecision(route="help", reason="page help")
        model, api = model_with(response(decision))
        self.assertEqual(DeepSeekSemanticRouter(model).decide("help"), decision)
        request = api.requests[0]
        self.assertIs(request["text_format"], RouteDecision)
        self.assertEqual(request["max_output_tokens"], 4096)
        self.assertNotIn("tools", request)
        self.assertEqual(model.calls, 1)

    def test_replan_receives_actual_completed_results_and_failures(self):
        done = {"weather_tokyo": Reading("Tokyo", 22.0, "cloudy", "primary")}
        failures = (Failure("weather_paris", "Paris", "primary"),)
        model, api = model_with(response(plan_for(completed=done, failures=failures)))
        DeepSeekPlanner(model).make_plan(task(), completed=done, failures=failures)
        payload = json.loads(api.requests[0]["input"])
        self.assertEqual(payload["completed"]["weather_tokyo"]["temperature_c"], 22.0)
        self.assertEqual(payload["failures"][0]["city"], "Paris")
        self.assertNotIn("previous_response_id", api.requests[0])

    def test_incomplete_and_missing_decisions_are_rejected(self):
        for output in (response(status="incomplete"), response(), response(plan_for())):
            model, _ = model_with(output)
            with self.subTest(output=output.status), self.assertRaises(ProviderDecisionError):
                DeepSeekSemanticRouter(model).decide("help")

    def test_unexpected_function_call_is_not_treated_as_a_plan(self):
        model, _ = model_with(response(plan_for(), output=[SimpleNamespace(type="function_call")]))
        with self.assertRaises(ProviderDecisionError):
            DeepSeekPlanner(model).make_plan(task(), completed={}, failures=())

    def test_shared_model_budget_includes_failed_requests(self):
        model, api = model_with(RuntimeError("network unavailable"), max_calls=1)
        with self.assertRaises(RuntimeError):
            DeepSeekSemanticRouter(model).decide("help")
        with self.assertRaises(ProviderDecisionError):
            DeepSeekPlanner(model).make_plan(task(), completed={}, failures=())
        self.assertEqual(len(api.requests), 1)
        self.assertEqual(model.calls, 1)

    def test_entire_fake_model_route_and_replan_path(self):
        route = RouteDecision(route="compare", cities=("Tokyo", "Paris"), fahrenheit=True, reason="compare")
        done = {"weather_tokyo": WeatherService().read("Tokyo")}
        failures = (Failure("weather_paris", "Paris", "primary"),)
        model, api = model_with(response(route), response(plan_for()), response(plan_for(completed=done, failures=failures)))
        HybridRouter(DeepSeekSemanticRouter(model)).route(request=EXAMPLES["en"]["compare"])
        run = run_with_replanning(task(), planner=DeepSeekPlanner(model),
                                  executor=PlanExecutor(WeatherService(unavailable=(("primary", "Paris"),))))
        self.assertEqual(run.status, "completed")
        self.assertEqual(model.calls, 3)
        self.assertEqual(len(api.requests), 3)

    def test_configuration_fails_without_exposing_a_credential(self):
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": " "}):
            with self.assertRaisesRegex(RuntimeError, "DEEPSEEK_API_KEY"):
                create_client()

    def test_json_mode_supports_tuple_based_contracts(self):
        restored = Plan.model_validate_json(plan_for().model_dump_json())
        self.assertEqual(restored, plan_for())
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate_json('{"route":"help","fahrenheit":"false","reason":"x"}')

    def test_real_sdk_with_mock_http_only(self):
        try:
            import httpx
            from openai import OpenAI
        except ImportError:
            self.skipTest("OpenAI SDK unavailable; no live request is made")
        captured = []
        def handler(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, json={
                "id": "resp_test", "object": "response", "created_at": 0,
                "status": "completed", "model": "test-model", "error": None,
                "incomplete_details": None, "instructions": None, "parallel_tool_calls": False,
                "tools": [], "tool_choice": "auto", "output": [{
                    "type": "message", "id": "msg_test", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "annotations": [],
                                 "text": '{"route":"help","cities":[],"fahrenheit":false,"reason":"page help"}'}],
                }],
            })
        with OpenAI(api_key="test-only", base_url="https://example.test", max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(handler))) as client:
            model = StructuredClient(client=client, model="test-model")
            self.assertEqual(DeepSeekSemanticRouter(model).decide("help").route, "help")
        self.assertEqual(captured[0]["text"]["format"]["type"], "json_schema")


if __name__ == "__main__":
    unittest.main(verbosity=2)

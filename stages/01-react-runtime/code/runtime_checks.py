"""Offline checks: observe execution and failure boundaries without API credentials."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from deepseek_runtime import DeepSeekResponsesModel, ProviderResponseError, parse_arguments
from runtime import (
    AgentRuntime, InvalidModelTurnError, MaxStepsExceeded, ModelTurn,
    ScriptedWeatherModel, TEACHING_WEATHER, TemperatureArguments, Tool,
    ToolArgumentsError, ToolBudgetExceeded, ToolCall, ToolExecutionError,
    ToolRegistry, UnknownToolError, WeatherArguments, build_tools,
    celsius_to_fahrenheit, format_transcript, request_for,
)

try:
    import httpx
    from openai import OpenAI
except ImportError:
    OpenAI = None


class SequenceModel:
    def __init__(self, *turns):
        self.turns = iter(turns)
        self.inputs = []

    def generate(self, messages, tools):
        self.inputs.append(deepcopy(messages))
        value = next(self.turns)
        if isinstance(value, Exception):
            raise value
        return value


def weather_call(call_id="weather", city="Tokyo"):
    return ToolCall(call_id, "get_teaching_weather", {"city": city})


def call_turn(*calls):
    return ModelTurn(tool_calls=tuple(calls))


class OutputItem(SimpleNamespace):
    def model_dump(self, **kwargs):
        return deepcopy(vars(self))


def response(*items, text="", status="completed"):
    return SimpleNamespace(status=status, output=list(items), output_text=text)


def function_item(call_id="weather", name="get_teaching_weather", arguments='{"city":"Tokyo"}'):
    return OutputItem(type="function_call", call_id=call_id, name=name, arguments=arguments)


def final_response(text="done"):
    return response(OutputItem(type="message", role="assistant", content=[{"type": "output_text", "text": text}]), text=text)


class FakeResponsesAPI:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.requests = []

    def create(self, **request):
        self.requests.append(deepcopy(request))
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result


def adapter_for(*responses):
    api = FakeResponsesAPI(*responses)
    return DeepSeekResponsesModel("test-model", client=SimpleNamespace(responses=api)), api


class RuntimeChecks(unittest.TestCase):
    def run_script(self, city="Tokyo", task="convert", **limits):
        return AgentRuntime(
            ScriptedWeatherModel(city=city, task=task, language="en"), build_tools(),
            verbose=False, **limits,
        ).run(request_for(city, task, "en"))

    def test_tokyo_trace_and_counts(self):
        result = self.run_script()
        self.assertEqual((result.model_turns, result.tool_executions), (3, 2))
        self.assertIn("64.4°F", result.answer)
        self.assertEqual([m["role"] for m in result.messages], ["user", "assistant", "tool", "assistant", "tool", "assistant"])
        call = result.messages[3]["tool_calls"][0]
        self.assertEqual(call["arguments"], {"temperature_c": 18.0})
        self.assertEqual(result.messages[4]["tool_call_id"], call["call_id"])

    def test_paris_uses_paris_values(self):
        result = self.run_script(city="Paris")
        self.assertIn("Paris", result.answer)
        self.assertIn("12.0°C / 53.6°F", result.answer)
        self.assertIn("light rain", result.answer)
        self.assertNotIn("18.0", result.answer)

    def test_weather_only_takes_two_turns(self):
        result = self.run_script(task="weather")
        self.assertEqual((result.model_turns, result.tool_executions), (2, 1))
        self.assertNotIn("°F", result.answer)

    def test_greeting_executes_no_tool(self):
        result = self.run_script(task="greet", max_tool_calls=0)
        self.assertEqual((result.model_turns, result.tool_executions), (1, 0))

    def test_changed_record_propagates_to_conversion_and_answer(self):
        with patch.dict(TEACHING_WEATHER, Tokyo={"temperature_c": 22.0, "condition": "cloudy"}):
            result = self.run_script()
        self.assertIn("22.0°C / 71.6°F", result.answer)
        self.assertEqual(result.messages[3]["tool_calls"][0]["arguments"]["temperature_c"], 22.0)

    def test_celsius_math(self):
        for celsius, fahrenheit in ((0, 32), (-40, -40), (100, 212)):
            with self.subTest(celsius=celsius):
                args = TemperatureArguments.model_validate({"temperature_c": celsius})
                self.assertEqual(celsius_to_fahrenheit(args)["temperature_f"], fahrenheit)

    def test_empty_or_ambiguous_turn_is_rejected(self):
        for kwargs in ({}, {"final_text": " "}, {"final_text": 42}, {"final_text": "done", "tool_calls": (weather_call(),)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(InvalidModelTurnError):
                ModelTurn(**kwargs)

    def test_call_shape_and_tuple_contract(self):
        for args in (("", "tool", {}), ("x", "", {}), ("x", "tool", [])):
            with self.subTest(args=args), self.assertRaises(InvalidModelTurnError):
                ToolCall(*args)
        with self.assertRaises(InvalidModelTurnError):
            ModelTurn(tool_calls=[weather_call()])
        with self.assertRaises(InvalidModelTurnError):
            ModelTurn(final_text="done", provider_items=("invalid",))

    def test_duplicate_ids_in_a_turn(self):
        with self.assertRaises(InvalidModelTurnError):
            call_turn(weather_call(), weather_call())

    def test_wrong_model_result_is_rejected(self):
        runtime = AgentRuntime(SequenceModel("not a ModelTurn"), build_tools(), verbose=False)
        with self.assertRaises(InvalidModelTurnError) as raised:
            runtime.run("x")
        self.assertEqual(raised.exception.tool_executions, 0)

    def test_unknown_tool_never_executes(self):
        runtime = AgentRuntime(SequenceModel(call_turn(ToolCall("x", "move_the_moon", {}))), build_tools(), verbose=False)
        with self.assertRaises(UnknownToolError) as raised:
            runtime.run("x")
        self.assertEqual(raised.exception.tool_executions, 0)
        self.assertFalse(any(m["role"] == "tool" for m in raised.exception.messages))

    def test_weather_arguments_reject_missing_extra_and_wrong_city(self):
        tool = build_tools()[0]
        for arguments in ({}, {"city": "Atlantis"}, {"city": 5}, {"city": "Tokyo", "extra": True}):
            with self.subTest(arguments=arguments), self.assertRaises(ToolArgumentsError):
                tool.validate(arguments)

    def test_temperature_rejects_string_bool_and_nonfinite(self):
        tool = build_tools()[1]
        for value in ("18", True, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ToolArgumentsError):
                tool.validate({"temperature_c": value})

    def test_bad_second_request_stops_the_whole_batch_before_execution(self):
        calls = []
        tool = Tool("get_teaching_weather", "spy", WeatherArguments, lambda args: calls.append(args.city))
        runtime = AgentRuntime(SequenceModel(call_turn(weather_call("a"), weather_call("b", "Atlantis"))), [tool], verbose=False)
        with self.assertRaises(ToolArgumentsError):
            runtime.run("x")
        self.assertEqual(calls, [])

    def test_duplicate_registration_is_rejected(self):
        with self.assertRaises(ValueError):
            ToolRegistry([build_tools()[0], build_tools()[0]])

    def test_handler_failure_keeps_cause_without_printing_its_message(self):
        secret_error = ValueError("pretend-secret-do-not-print")
        calls = []
        def fail(args):
            calls.append(args.city)
            raise secret_error
        runtime = AgentRuntime(SequenceModel(call_turn(weather_call())), [Tool("get_teaching_weather", "fail", WeatherArguments, fail)], verbose=False)
        with self.assertRaises(ToolExecutionError) as raised:
            runtime.run("x")
        self.assertIs(raised.exception.__cause__, secret_error)
        self.assertNotIn("pretend-secret", str(raised.exception))
        self.assertEqual(calls, ["Tokyo"])
        self.assertEqual(raised.exception.tool_executions, 1)

    def test_later_failure_does_not_undo_earlier_handler(self):
        executed = []
        def handle(args):
            executed.append(args.city)
            if args.city == "Paris":
                raise RuntimeError("failed")
            return {"city": args.city}
        model = SequenceModel(call_turn(weather_call("a"), weather_call("b", "Paris"), weather_call("c")))
        runtime = AgentRuntime(model, [Tool("get_teaching_weather", "spy", WeatherArguments, handle)], verbose=False)
        with self.assertRaises(ToolExecutionError) as raised:
            runtime.run("x")
        self.assertEqual(executed, ["Tokyo", "Paris"])
        self.assertEqual(sum(m["role"] == "tool" for m in raised.exception.messages), 1)
        self.assertEqual(len(model.inputs), 1)

    def test_invalid_tool_output_is_not_converted_to_misleading_text(self):
        for output in (object(), {"x": float("nan")}):
            with self.subTest(output_type=type(output).__name__):
                tool = Tool("get_teaching_weather", "bad output", WeatherArguments, lambda args: output)
                runtime = AgentRuntime(SequenceModel(call_turn(weather_call())), [tool], verbose=False)
                with self.assertRaises(ToolExecutionError) as raised:
                    runtime.run("x")
                self.assertFalse(any(m["role"] == "tool" for m in raised.exception.messages))

    def test_duplicate_id_across_turns_stops_second_execution(self):
        runtime = AgentRuntime(SequenceModel(call_turn(weather_call()), call_turn(weather_call())), build_tools(), verbose=False)
        with self.assertRaises(InvalidModelTurnError) as raised:
            runtime.run("x")
        self.assertEqual(raised.exception.tool_executions, 1)

    def test_same_arguments_with_new_id_can_run_again(self):
        model = SequenceModel(call_turn(weather_call("a")), call_turn(weather_call("b")), ModelTurn(final_text="done"))
        result = AgentRuntime(model, build_tools(), verbose=False).run("x")
        self.assertEqual(result.tool_executions, 2)

    def test_multiple_calls_are_sequential_and_keep_pairing(self):
        model = SequenceModel(call_turn(weather_call("a"), weather_call("b", "Paris")), ModelTurn(final_text="done"))
        result = AgentRuntime(model, build_tools(), verbose=False).run("x")
        observations = [m for m in result.messages if m["role"] == "tool"]
        self.assertEqual([m["tool_call_id"] for m in observations], ["a", "b"])
        self.assertEqual([json.loads(m["content"])["city"] for m in observations], ["Tokyo", "Paris"])
        self.assertEqual((result.model_turns, result.tool_executions), (2, 2))

    def test_step_limit_preserves_both_successful_observations(self):
        with self.assertRaises(MaxStepsExceeded) as raised:
            self.run_script(max_steps=2)
        self.assertEqual((raised.exception.model_turns, raised.exception.tool_executions), (2, 2))
        self.assertIn("64.4", raised.exception.messages[-1]["content"])
        self.assertEqual(raised.exception.messages[-1]["role"], "tool")

    def test_tool_limit_stops_before_conversion(self):
        with self.assertRaises(ToolBudgetExceeded) as raised:
            self.run_script(max_tool_calls=1)
        self.assertEqual(raised.exception.tool_executions, 1)

    def test_batch_cannot_partly_consume_remaining_budget(self):
        model = SequenceModel(call_turn(weather_call("a"), weather_call("b", "Paris")))
        runtime = AgentRuntime(model, build_tools(), max_tool_calls=1, verbose=False)
        with self.assertRaises(ToolBudgetExceeded) as raised:
            runtime.run("x")
        self.assertEqual(raised.exception.tool_executions, 0)

    def test_nonfinishing_model_is_bounded(self):
        turns = [call_turn(weather_call(str(i))) for i in range(4)]
        model = SequenceModel(*turns)
        runtime = AgentRuntime(model, build_tools(), max_steps=2, verbose=False)
        with self.assertRaises(MaxStepsExceeded) as raised:
            runtime.run("x")
        self.assertEqual(len(model.inputs), 2)
        self.assertEqual(raised.exception.tool_executions, 2)

    def test_budget_configuration_is_not_silently_coerced(self):
        for kwargs in ({"max_steps": 0}, {"max_steps": True}, {"max_steps": 1.5}, {"max_tool_calls": -1}, {"max_tool_calls": False}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                AgentRuntime(ScriptedWeatherModel(), build_tools(), **kwargs)

    def test_blank_request_is_rejected(self):
        for value in ("", " ", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                AgentRuntime(ScriptedWeatherModel(), build_tools()).run(value)

    def test_runs_do_not_share_history_or_call_id_set(self):
        runtime = AgentRuntime(ScriptedWeatherModel(), build_tools(), verbose=False)
        first, second = runtime.run("first"), runtime.run("second")
        self.assertEqual(first.messages[0]["content"], "first")
        self.assertEqual(second.messages[0]["content"], "second")
        self.assertEqual(len(first.messages), len(second.messages))

    def test_model_receives_a_copy_of_history(self):
        class MutatingModel:
            def generate(self, messages, tools):
                messages[0]["content"] = "changed"
                return ModelTurn(final_text="done")
        result = AgentRuntime(MutatingModel(), [], verbose=False).run("original")
        self.assertEqual(result.messages[0]["content"], "original")

    def test_runtime_does_not_claim_to_verify_final_facts(self):
        model = SequenceModel(ModelTurn(final_text="Tokyo is 99 degrees; I guessed."))
        result = AgentRuntime(model, build_tools(), verbose=False).run("weather")
        self.assertIn("99", result.answer)
        self.assertEqual(result.tool_executions, 0)


class AdapterChecks(unittest.TestCase):
    def test_full_three_turn_history_and_raw_continuation(self):
        opaque = OutputItem(type="reasoning", content=[{"type": "reasoning_text", "text": "opaque-transport-only"}])
        adapter, api = adapter_for(
            response(opaque, function_item()),
            response(function_item("convert", "celsius_to_fahrenheit", '{"temperature_c":18.0}')),
            final_response("18°C / 64.4°F, teaching only"),
        )
        result = AgentRuntime(adapter, build_tools(), verbose=False).run("Tokyo please")
        self.assertEqual((result.model_turns, result.tool_executions), (3, 2))
        self.assertEqual(api.requests[1]["input"][1], opaque.model_dump())
        third = api.requests[2]["input"]
        self.assertEqual([i["call_id"] for i in third if i.get("type") == "function_call_output"], ["weather", "convert"])
        self.assertEqual(third[0], {"role": "user", "content": "Tokyo please"})
        self.assertNotIn("opaque-transport-only", format_transcript(result.messages))
        for req in api.requests:
            self.assertEqual(req["tool_choice"], "auto")
            self.assertEqual(req["instructions"], adapter.instructions)
            self.assertNotIn("previous_response_id", req)
            self.assertNotIn("parallel_tool_calls", req)
            self.assertNotIn("max_tool_calls", req)

    def test_text_accompanying_a_call_is_not_final(self):
        adapter, _ = adapter_for(response(function_item(), text="I am about to look it up."))
        turn = adapter.generate([{"role": "user", "content": "x"}], [])
        self.assertIsNone(turn.final_text)
        self.assertEqual(len(turn.tool_calls), 1)

    def test_incomplete_response_executes_nothing(self):
        adapter, _ = adapter_for(response(function_item(), status="incomplete"))
        with self.assertRaises(ProviderResponseError) as raised:
            AgentRuntime(adapter, build_tools(), verbose=False).run("x")
        self.assertEqual(raised.exception.tool_executions, 0)

    def test_empty_or_unsupported_provider_output(self):
        for value in (response(), response(OutputItem(type="unexpected")), SimpleNamespace(status="completed", output=None)):
            with self.subTest(value=value), self.assertRaises(ProviderResponseError):
                adapter, _ = adapter_for(value)
                adapter.generate([{"role": "user", "content": "x"}], [])

    def test_json_shape_duplicates_size_and_nonfinite(self):
        for raw in ("{", "[]", "null", '{"city":"Tokyo","city":"Paris"}', '{"x":NaN}', " " * 16_001, None):
            with self.subTest(raw_type=type(raw).__name__), self.assertRaises(ProviderResponseError):
                parse_arguments(raw)
        self.assertEqual(parse_arguments('{"city":"Tokyo"}'), {"city": "Tokyo"})

    def test_bad_call_identity_or_duplicate_ids(self):
        for value in (response(function_item(call_id="")), response(function_item(), function_item())):
            with self.subTest(value=value), self.assertRaises((ProviderResponseError, InvalidModelTurnError)):
                adapter, _ = adapter_for(value)
                adapter.generate([{"role": "user", "content": "x"}], [])

    def test_failed_individual_call_is_rejected(self):
        item = function_item()
        item.status = "incomplete"
        adapter, _ = adapter_for(response(item))
        with self.assertRaises(ProviderResponseError):
            adapter.generate([{"role": "user", "content": "x"}], [])

    def test_scripted_history_can_be_translated(self):
        result = AgentRuntime(ScriptedWeatherModel(), build_tools(), verbose=False).run("x")
        items = DeepSeekResponsesModel._to_deepseek_input(list(result.messages))
        self.assertEqual(sum(i.get("type") == "function_call" for i in items), 2)
        self.assertEqual(sum(i.get("type") == "function_call_output" for i in items), 2)

    def test_unknown_role_or_empty_history_is_rejected(self):
        for messages in ([], [{"role": "system", "content": "not an internal role"}]):
            with self.subTest(messages=messages), self.assertRaises(ProviderResponseError):
                DeepSeekResponsesModel._to_deepseek_input(messages)

    def test_adapter_reuse_does_not_mix_runs(self):
        adapter, api = adapter_for(final_response("one"), final_response("two"))
        runtime = AgentRuntime(adapter, build_tools(), verbose=False)
        runtime.run("first")
        runtime.run("second")
        self.assertEqual(api.requests[1]["input"], [{"role": "user", "content": "second"}])

    def test_network_failure_has_no_retry_and_preserves_prior_tool(self):
        adapter, api = adapter_for(response(function_item()), OSError("pretend-secret"))
        with self.assertRaises(ProviderResponseError) as raised:
            AgentRuntime(adapter, build_tools(), verbose=False).run("x")
        self.assertEqual(len(api.requests), 2)
        self.assertEqual(raised.exception.tool_executions, 1)
        self.assertEqual(sum(m["role"] == "tool" for m in raised.exception.messages), 1)
        self.assertNotIn("pretend-secret", str(raised.exception))

    def test_only_local_function_tools_are_sent(self):
        schemas = [DeepSeekResponsesModel._to_deepseek_tool(t.schema()) for t in build_tools()]
        self.assertEqual([s["type"] for s in schemas], ["function", "function"])
        self.assertEqual(schemas[0]["parameters"]["additionalProperties"], False)

    @unittest.skipUnless(OpenAI is not None, "Optional OpenAI SDK is unavailable; fake-client checks still run.")
    def test_real_sdk_over_mock_http_not_the_live_service(self):
        observed = []
        def transport(request):
            observed.append(json.loads(request.content))
            if len(observed) == 1:
                output = [{"type": "function_call", "id": "fc_1", "status": "completed", "call_id": "weather", "name": "get_teaching_weather", "arguments": '{"city":"Tokyo"}'}]
            else:
                output = [{"type": "message", "id": "msg_2", "status": "completed", "role": "assistant", "content": [{"type": "output_text", "text": "18 degrees, teaching only", "annotations": []}]}]
            return httpx.Response(200, json={"id": f"resp_{len(observed)}", "object": "response", "created_at": 0, "status": "completed", "model": "test-model", "output": output})
        with OpenAI(api_key="fake-not-a-secret", base_url="https://example.invalid", max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(transport))) as client:
            result = AgentRuntime(DeepSeekResponsesModel("test-model", client=client), build_tools(), verbose=False).run("Tokyo")
        self.assertEqual(result.tool_executions, 1)
        self.assertEqual(observed[1]["input"][-1]["call_id"], "weather")


class CommandLineChecks(unittest.TestCase):
    def invoke(self, script, *args):
        env = {k: v for k, v in os.environ.items() if k not in {"DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "PYTHONPATH"}}
        return subprocess.run([sys.executable, str(Path(__file__).with_name(script)), *args], capture_output=True, text=True, encoding="utf-8", env=env, timeout=15)

    def test_paris_english_entry(self):
        run = self.invoke("runtime.py", "--city", "Paris", "--language", "en")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("53.6°F", run.stdout)
        self.assertIn("no API request", run.stdout)

    def test_budget_stop_is_a_nonzero_exit_with_observations(self):
        run = self.invoke("runtime.py", "--max-steps", "2", "--show-transcript")
        self.assertEqual(run.returncode, 1)
        self.assertIn("MaxStepsExceeded", run.stdout)
        self.assertIn("64.4", run.stdout)
        self.assertNotIn("[3] FINAL", run.stdout)

    def test_live_entry_requires_configuration(self):
        run = self.invoke("deepseek_runtime.py")
        self.assertEqual(run.returncode, 1)
        self.assertIn("DEEPSEEK_MODEL", run.stdout)

    def test_help_needs_no_credentials(self):
        for script in ("runtime.py", "deepseek_runtime.py"):
            run = self.invoke(script, "--help")
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("--task", run.stdout)

    def test_unknown_city_is_rejected_by_cli(self):
        run = self.invoke("runtime.py", "--city", "Atlantis")
        self.assertEqual(run.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

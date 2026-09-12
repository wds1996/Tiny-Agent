"""Offline boundary checks; no API key or external HTTP request is used."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pydantic import ValidationError

import common
import first_llm_call
import structured_output
import tool_calling
from structured_output import TaskCard


class Item(SimpleNamespace):
    def model_dump(self, **kwargs):
        return deepcopy(vars(self))


def function_call(**changes):
    fields = dict(type="function_call", name="get_teaching_weather",
                  arguments='{"city":"Tokyo"}', call_id="call-1")
    fields.update(changes)
    return Item(**fields)


def response(*, output=None, text="", status="completed", parsed=None):
    return SimpleNamespace(status=status, output=output or [], output_text=text,
                           output_parsed=parsed, id="response-1", model="test-model", usage=None)


class FakeClient:
    def __init__(self, *responses):
        self.pending = list(responses)
        self.requests = []
        self.responses = self

    def _next(self, kind, kwargs):
        self.requests.append((kind, deepcopy(kwargs)))
        if not self.pending:
            raise AssertionError("Unexpected additional model request")
        item = self.pending.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def create(self, **kwargs):
        return self._next("create", kwargs)

    def parse(self, **kwargs):
        return self._next("parse", kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def valid_card(**changes):
    fields = dict(goal="Read the teaching record", city="Tokyo",
                  needs_external_data=True, reason="The record is not in the input.")
    fields.update(changes)
    return fields


class Stage00Checks(unittest.TestCase):
    def test_missing_environment_value_fails_without_echoing_credentials(self):
        with patch.dict(os.environ, {"STAGE00_TEST": " "}):
            with self.assertRaisesRegex(RuntimeError, "STAGE00_TEST"):
                common.required_env("STAGE00_TEST")

    def test_environment_value_is_trimmed(self):
        with patch.dict(os.environ, {"STAGE00_TEST": "  example  "}):
            self.assertEqual(common.required_env("STAGE00_TEST"), "example")

    def test_both_languages_keep_the_same_requested_city(self):
        for city in common.CITIES:
            for language in common.LANGUAGES:
                self.assertIn(city, common.request_for(city, language))

    def test_unsupported_request_is_rejected_before_network(self):
        for city, language in [("London", "en"), ("Tokyo", "fr")]:
            with self.assertRaises(ValueError):
                common.request_for(city, language)

    def test_first_request_has_no_weather_data_or_tools(self):
        client = FakeClient(response(text="Please provide the teaching record."))
        first_llm_call.ask_without_record(client, "test", "Tokyo", "en")
        body = client.requests[0][1]
        self.assertNotIn("tools", body)
        self.assertNotIn("18.0", json.dumps(body))
        self.assertEqual(body["input"], common.request_for("Tokyo", "en"))

    def test_first_request_does_not_retry_failed_client(self):
        client = FakeClient(RuntimeError("simulated transport failure"))
        with self.assertRaises(RuntimeError):
            first_llm_call.ask_without_record(client, "test", "Tokyo", "en")
        self.assertEqual(len(client.requests), 1)

    def test_noncompleted_text_is_rejected(self):
        for status in ("incomplete", "failed", "in_progress"):
            with self.assertRaises(RuntimeError):
                common.require_text(response(text="partial", status=status))

    def test_missing_or_blank_text_is_rejected(self):
        for text in (None, "", " \n"):
            with self.assertRaises(RuntimeError):
                common.require_text(response(text=text))

    def test_new_tool_request_is_not_accepted_as_final_answer(self):
        with self.assertRaises(RuntimeError):
            common.require_text(response(output=[function_call()], text="not final"))

    def test_unknown_usage_is_not_printed_as_zero(self):
        client = FakeClient(response(text="Need the record."))
        out = io.StringIO()
        with patch.object(first_llm_call, "create_client", return_value=client), \
             patch.object(first_llm_call, "required_env", return_value="test"), \
             patch.object(first_llm_call, "parse_args", return_value=SimpleNamespace(city="Tokyo", language="en")), \
             redirect_stdout(out):
            first_llm_call.main()
        self.assertIn("not reported", out.getvalue())
        self.assertNotIn("input_tokens: 0", out.getvalue())

    def test_card_parses_to_ordinary_fields(self):
        card = TaskCard.model_validate_json(json.dumps(valid_card()))
        self.assertEqual(card.city, "Tokyo")
        self.assertIs(card.needs_external_data, True)

    def test_card_rejects_extra_fields(self):
        with self.assertRaises(ValidationError):
            TaskCard(**valid_card(temperature_c=18))

    def test_card_rejects_missing_field(self):
        fields = valid_card()
        del fields["city"]
        with self.assertRaises(ValidationError):
            TaskCard(**fields)

    def test_card_rejects_unknown_city(self):
        with self.assertRaises(ValidationError):
            TaskCard(**valid_card(city="Atlantis"))

    def test_card_rejects_coercion_of_boolean(self):
        for value in ("true", "false", 0, 1, None):
            with self.assertRaises(ValidationError):
                TaskCard(**valid_card(needs_external_data=value))

    def test_card_rejects_blank_or_oversized_explanations(self):
        for fields in (valid_card(goal=" "), valid_card(reason=""), valid_card(reason="x" * 301)):
            with self.assertRaises(ValidationError):
                TaskCard(**fields)

    def test_schema_alone_does_not_check_request_meaning(self):
        for fields in (valid_card(city="Paris"), valid_card(needs_external_data=False)):
            card = TaskCard(**fields)  # Both objects satisfy the schema.
            with self.assertRaises(RuntimeError):
                structured_output.validate_card_for_request(card, "Tokyo")

    def test_structured_request_uses_the_same_task_and_schema(self):
        client = FakeClient(response(parsed=TaskCard(**valid_card())))
        card = structured_output.make_task_card(client, "test", "Tokyo", "en")
        self.assertEqual(card.city, "Tokyo")
        body = client.requests[0][1]
        self.assertIs(body["text_format"], TaskCard)
        self.assertEqual(body["input"], common.request_for("Tokyo", "en"))

    def test_missing_or_incomplete_parsed_output_stops(self):
        for item in (response(), response(parsed=TaskCard(**valid_card()), status="incomplete")):
            with self.assertRaises(RuntimeError):
                structured_output.make_task_card(FakeClient(item), "test", "Tokyo", "en")

    def test_local_weather_returns_a_copy_with_source(self):
        result = tool_calling.get_teaching_weather("Tokyo")
        self.assertEqual(result["temperature_c"], 18.0)
        self.assertIn("teaching", result["source"])
        result["temperature_c"] = 99
        self.assertEqual(tool_calling.get_teaching_weather("Tokyo")["temperature_c"], 18.0)

    def test_local_weather_rejects_unsupported_city(self):
        with self.assertRaises(ValueError):
            tool_calling.get_teaching_weather("Atlantis")

    def test_json_syntax_and_object_type_are_checked(self):
        for raw in ('{"city":', "[]", "null", "true", '"Tokyo"', None):
            with self.assertRaises(RuntimeError):
                tool_calling.parse_arguments(raw)

    def test_arguments_check_exact_fields_and_values(self):
        for args in ({}, {"city": "Tokyo", "unit": "F"}, {"city": 42}, {"city": "Atlantis"}):
            with self.assertRaises(RuntimeError):
                tool_calling.validate_weather_arguments(args)

    def test_invalid_call_never_reaches_handler(self):
        invalid = [
            response(),
            response(output=[function_call(), function_call(call_id="call-2")]),
            response(output=[function_call(name="delete_files")]),
            response(output=[function_call(call_id=" ")]),
            response(output=[function_call(call_id=None)]),
            response(output=[function_call(arguments='{"city":"Paris"}')]),
            response(output=[function_call(arguments='{"city":42}')]),
            response(output=[function_call()], status="incomplete"),
        ]
        for item in invalid:
            with self.subTest(item=item), patch.object(tool_calling, "get_teaching_weather") as handler:
                client = FakeClient(item)
                with self.assertRaises(RuntimeError), redirect_stdout(io.StringIO()):
                    tool_calling.run_round_trip(client, "test", "Tokyo", "en")
                handler.assert_not_called()
                self.assertEqual(len(client.requests), 1)

    def test_round_trip_replays_full_output_and_matching_call_id(self):
        reasoning = Item(type="reasoning", content=[{"type": "reasoning_text", "text": "test protocol item"}])
        call = function_call()
        client = FakeClient(response(output=[reasoning, call]), response(text="Tokyo teaching record: 18 C, cloudy."))
        with redirect_stdout(io.StringIO()):
            result, answer = tool_calling.run_round_trip(client, "test", "Tokyo", "en")
        self.assertEqual(len(client.requests), 2)
        first, final = (request[1] for request in client.requests)
        self.assertEqual(len(first["input"]), 1)
        self.assertEqual(final["input"][1], reasoning.model_dump())
        self.assertEqual(final["input"][2], call.model_dump())
        receipt = final["input"][3]
        self.assertEqual(receipt["call_id"], "call-1")
        self.assertEqual(json.loads(receipt["output"]), result)
        self.assertEqual(final["tool_choice"], "none")
        self.assertNotIn("previous_response_id", final)
        self.assertNotIn("parallel_tool_calls", first)
        self.assertIn("18", answer)

    def test_paris_follows_the_same_data_path(self):
        client = FakeClient(response(output=[function_call(arguments='{"city":"Paris"}')]),
                            response(text="Paris teaching record: 12 C, light rain."))
        with redirect_stdout(io.StringIO()):
            result, _ = tool_calling.run_round_trip(client, "test", "Paris", "en")
        self.assertEqual(result["temperature_c"], 12.0)
        self.assertEqual(result["condition"], "light rain")

    def test_final_failure_does_not_undo_or_repeat_lookup(self):
        client = FakeClient(response(output=[function_call()]), response(status="failed"))
        with patch.object(tool_calling, "get_teaching_weather", wraps=tool_calling.get_teaching_weather) as handler:
            with self.assertRaises(RuntimeError), redirect_stdout(io.StringIO()):
                tool_calling.run_round_trip(client, "test", "Tokyo", "en")
            handler.assert_called_once_with("Tokyo")
        self.assertEqual(len(client.requests), 2)

    def test_final_prose_is_not_automatically_fact_checked(self):
        client = FakeClient(response(output=[function_call()]), response(text="Tokyo is 99 C."))
        with redirect_stdout(io.StringIO()):
            result, answer = tool_calling.run_round_trip(client, "test", "Tokyo", "en")
        self.assertEqual(result["temperature_c"], 18.0)
        self.assertIn("99", answer)  # Explicitly documents the limit of require_text().

    @unittest.skipUnless(importlib.util.find_spec("openai"), "optional openai SDK is not installed")
    def test_real_sdk_serializes_and_parses_without_network(self):
        import httpx
        from openai import OpenAI

        requests = []
        def handler(request):
            body = json.loads(request.content)
            requests.append(body)
            output = [{"type": "message", "id": "msg-1", "role": "assistant",
                       "status": "completed", "content": [{"type": "output_text",
                       "annotations": [], "text": json.dumps(valid_card())}]}]
            return httpx.Response(200, json={
                "id": "resp-1", "object": "response", "created_at": 1,
                "status": "completed", "model": "test", "output": output,
                "error": None, "incomplete_details": None,
            })
        with OpenAI(api_key="offline-test-only", base_url="https://example.invalid",
                    http_client=httpx.Client(transport=httpx.MockTransport(handler))) as client:
            card = structured_output.make_task_card(client, "test", "Tokyo", "en")
        self.assertEqual(card.city, "Tokyo")
        self.assertEqual(requests[0]["text"]["format"]["type"], "json_schema")
        self.assertEqual(set(requests[0]["text"]["format"]["schema"]["required"]),
                         {"goal", "city", "needs_external_data", "reason"})


if __name__ == "__main__":
    unittest.main(verbosity=2)

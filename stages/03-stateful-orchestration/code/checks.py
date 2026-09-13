"""Offline behavior checks. Optional SDK tests never contact model services."""
from __future__ import annotations

from copy import deepcopy
from importlib.util import find_spec
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from agent_graph import (ModelTurn, ScriptedModel, ToolCall, build_agent_graph,
                         initial_state as agent_initial, make_nodes)
from langgraph_deepseek_agent import DeepSeekModel, ProviderResponseError, parse_response, to_input
from state_graph import (END, START, GraphExecutionError, GraphLimitError,
                         MiniStateGraph, append_events, merge_update)
from workflow import (NOTICES, ReportNodes, TEACHING_WEATHER, build_mini_workflow,
                      fahrenheit, initial_state, review_issues, run_plain)


def linear(*nodes, reducers=None):
    builder = MiniStateGraph(reducers=reducers)
    previous = START
    for name, function in nodes:
        builder.add_node(name, function)
        builder.add_edge(previous, name)
        previous = name
    builder.add_edge(previous, END)
    return builder


class GraphChecks(unittest.TestCase):
    def test_partial_update_keeps_other_fields(self):
        state = linear(("write", lambda s: {"draft": "new"})).compile().invoke({"question": "q"}).state
        self.assertEqual(state, {"question": "q", "draft": "new"})

    def test_explicit_none_replaces_old_review(self):
        self.assertEqual(merge_update({"review": "accepted"}, {"review": None}, {}), {"review": None})

    def test_reducer_accumulates_only_deltas(self):
        graph = linear(("one", lambda s: {"events": ["one"]}), ("two", lambda s: {"events": ["two"]}),
                       reducers={"events": append_events}).compile()
        self.assertEqual(graph.invoke({"events": []}).state["events"], ["one", "two"])

    def test_returning_full_history_duplicates_old_events(self):
        self.assertEqual(merge_update({"events": ["one"]}, {"events": ["one", "two"]},
                                     {"events": append_events})["events"], ["one", "one", "two"])

    def test_failed_reducer_does_not_commit_half_update(self):
        state = {"draft": "old", "events": []}
        def fail(a, b):
            a.append("mutated")
            raise ValueError("failed")
        with self.assertRaises(ValueError):
            merge_update(state, {"draft": "new", "events": ["bad"]}, {"events": fail})
        self.assertEqual(state, {"draft": "old", "events": []})

    def test_node_mutation_is_not_an_update(self):
        def mutate(s):
            s["nested"]["values"].append(2)
            return {"answer": "done"}
        source = {"nested": {"values": [1]}}
        result = linear(("mutate", mutate)).compile().invoke(source)
        self.assertEqual(source["nested"]["values"], [1])
        self.assertEqual(result.state["nested"]["values"], [1])

    def test_invalid_update_preserves_previous_snapshot(self):
        graph = linear(("one", lambda s: {"ok": True}), ("bad", lambda s: "not a mapping")).compile()
        with self.assertRaises(GraphExecutionError) as caught:
            graph.invoke({})
        self.assertEqual(caught.exception.node, "bad")
        self.assertEqual(caught.exception.state, {"ok": True})
        self.assertEqual(caught.exception.trace, ("one",))

    def test_unknown_update_key_types_are_rejected(self):
        with self.assertRaises(TypeError):
            merge_update({}, {1: "bad"}, {})

    def test_route_reads_merged_state(self):
        b = MiniStateGraph()
        b.add_node("choose", lambda s: {"choice": "ok"})
        b.add_edge(START, "choose")
        b.add_conditional_edges("choose", lambda s: s["choice"], {"ok": END})
        self.assertEqual(b.compile().invoke({}).trace, ("choose",))

    def test_router_mutation_does_not_change_state(self):
        def route(s):
            s["events"].append("hidden")
            return "done"
        b = linear(("one", lambda s: {}))
        del b.edges["one"]
        b.add_conditional_edges("one", route, {"done": END})
        self.assertEqual(b.compile().invoke({"events": []}).state["events"], [])

    def test_unknown_route_fails_after_recording_node(self):
        b = MiniStateGraph()
        b.add_node("one", lambda s: {"answer": 1})
        b.add_edge(START, "one")
        b.add_conditional_edges("one", lambda s: "surprise", {"done": END})
        with self.assertRaises(GraphExecutionError) as caught:
            b.compile().invoke({})
        self.assertEqual(caught.exception.trace, ("one",))

    def test_possible_exit_does_not_prove_termination(self):
        b = MiniStateGraph()
        b.add_node("tick", lambda s: {"count": s.get("count", 0) + 1})
        b.add_edge(START, "tick")
        b.add_conditional_edges("tick", lambda s: "again", {"again": "tick", "done": END})
        with self.assertRaises(GraphLimitError) as caught:
            b.compile().invoke({}, max_steps=3)
        self.assertEqual(caught.exception.state["count"], 3)

    def test_limit_stops_before_next_node(self):
        later = Mock(return_value={})
        with self.assertRaises(GraphLimitError):
            linear(("first", lambda s: {}), ("later", later)).compile().invoke({}, max_steps=1)
        later.assert_not_called()

    def test_snapshot_is_detached_from_live_state(self):
        graph = linear(("one", lambda s: {"items": [1]}), ("two", lambda s: {"total": sum(s["items"])})).compile()
        stream = graph.stream({})
        first = next(stream)
        first.state["items"].append(99)
        self.assertEqual(next(stream).state["total"], 1)

    def test_compile_rejects_missing_start(self):
        with self.assertRaises(ValueError):
            MiniStateGraph().compile()

    def test_compile_rejects_unknown_destination(self):
        b = linear(("one", lambda s: {}))
        b.edges["one"] = "missing"
        with self.assertRaises(ValueError):
            b.compile()

    def test_compile_rejects_unreachable_node(self):
        b = linear(("one", lambda s: {}))
        b.add_node("orphan", lambda s: {})
        b.add_edge("orphan", END)
        with self.assertRaises(ValueError):
            b.compile()

    def test_compile_rejects_loop_without_possible_exit(self):
        b = linear(("one", lambda s: {}))
        b.edges["one"] = "one"
        with self.assertRaises(ValueError):
            b.compile()

    def test_duplicate_and_reserved_nodes_are_rejected(self):
        b = linear(("one", lambda s: {}))
        for name in ("one", START, END, " "):
            with self.subTest(name=name), self.assertRaises(ValueError):
                b.add_node(name, lambda s: {})

    def test_second_outgoing_rule_is_rejected(self):
        b = linear(("one", lambda s: {}))
        with self.assertRaises(ValueError):
            b.add_conditional_edges("one", lambda s: "done", {"done": END})

    def test_compiled_routes_do_not_follow_builder_edits(self):
        b = linear(("one", lambda s: {"done": True}))
        graph = b.compile()
        b.edges["one"] = "missing"
        self.assertTrue(graph.invoke({}).state["done"])

    def test_limit_rejects_boolean_and_nonpositive_values(self):
        graph = linear().compile()
        for value in (True, 0, -1, 1.2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                graph.invoke({}, max_steps=value)


class ReportChecks(unittest.TestCase):
    def test_cli_step_limit_reports_last_completed_nodes(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("state_graph.py")), "--max-steps", "2"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("stopped before: check_draft", result.stdout)
        self.assertIn("write_draft", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_notice_is_repaired_then_checked(self):
        run = build_mini_workflow().invoke(initial_state())
        self.assertEqual(run.trace, ("collect", "write_draft", "check_draft", "revise_draft", "check_draft", "publish"))
        self.assertEqual(run.state["revisions"], 1)
        self.assertEqual(run.steps[2].state["review"]["issues"], ["missing_fixed_data_notice"])
        self.assertIn("53.6°F", run.state["answer"])

    def test_good_first_draft_needs_no_revision(self):
        run = build_mini_workflow(draft_style="complete").invoke(initial_state())
        self.assertNotIn("revise_draft", run.trace)
        self.assertEqual(run.state["revisions"], 0)

    def test_stubborn_draft_is_held_not_published(self):
        state = build_mini_workflow(draft_style="stubborn", max_revisions=2).invoke(initial_state()).state
        self.assertEqual(state["status"], "needs_attention")
        self.assertEqual(state["revisions"], 2)
        self.assertIsNone(state["answer"])
        self.assertIsNotNone(state["draft"])

    def test_zero_revision_budget_still_checks_initial_draft(self):
        run = build_mini_workflow(max_revisions=0).invoke(initial_state())
        self.assertEqual(run.trace[-2:], ("check_draft", "hold"))
        self.assertEqual(run.state["revisions"], 0)

    def test_check_uses_content_not_revision_count(self):
        state = run_plain(initial_state(), ReportNodes())
        state["draft"]["notice"] = ""
        state["revisions"] = 100
        self.assertIn("missing_fixed_data_notice", review_issues(state))

    def test_plain_and_graph_paths_match(self):
        for style in ("missing-notice", "complete", "stubborn"):
            with self.subTest(style=style):
                expected = run_plain(initial_state(), ReportNodes(draft_style=style))
                self.assertEqual(build_mini_workflow(draft_style=style).invoke(initial_state()).state, expected)

    def test_changed_source_changes_checked_numbers(self):
        with patch.dict(TEACHING_WEATHER, {"Tokyo": {"temperature_c": 22.0, "condition": "cloudy"}}):
            state = build_mini_workflow().invoke(initial_state()).state
        self.assertIn("22.0°C / 71.6°F", state["answer"])

    def test_single_city_and_celsius_only(self):
        state = build_mini_workflow().invoke(initial_state(["Paris"], False, "en")).state
        self.assertNotIn("Tokyo", state["answer"])
        self.assertNotIn("°F", state["answer"])
        self.assertIn(NOTICES["en"], state["answer"])

    def test_revision_does_not_query_again(self):
        reader = Mock(side_effect=lambda city: {"city": city, **TEACHING_WEATHER[city], "source": "fixed teaching record"})
        build_mini_workflow(reader=reader).invoke(initial_state())
        self.assertEqual(reader.call_count, 2)

    def test_accepted_review_cannot_publish_changed_draft(self):
        state = build_mini_workflow().invoke(initial_state()).state
        state["draft"]["rows"][0]["temperature_c"] = 99
        with self.assertRaises(ValueError):
            ReportNodes().publish(state)

    def test_unchecked_draft_cannot_publish(self):
        nodes = ReportNodes(draft_style="complete")
        state = initial_state()
        state.update(nodes.collect(state))
        state.update(nodes.write_draft(state))
        with self.assertRaises(ValueError):
            nodes.publish(state)

    def test_each_node_leaves_input_unchanged(self):
        nodes = ReportNodes()
        state = initial_state()
        for node in (nodes.collect, nodes.write_draft, nodes.check_draft, nodes.revise_draft):
            original = deepcopy(state)
            update = node(state)
            self.assertEqual(state, original)
            state = merge_update(state, update, {"events": append_events})

    def test_bad_request_is_rejected_before_nodes(self):
        for cities, switch in ((["Moon"], True), (["Tokyo", "Tokyo"], True), ([], True), (["Tokyo"], "false")):
            with self.subTest(cities=cities, switch=switch), self.assertRaises(ValueError):
                initial_state(cities, switch)

    def test_failed_collection_does_not_create_a_draft(self):
        with self.assertRaises(GraphExecutionError) as caught:
            build_mini_workflow(reader=Mock(side_effect=OSError("fake failure"))).invoke(initial_state())
        self.assertIsNone(caught.exception.state["draft"])
        self.assertEqual(caught.exception.node, "collect")

    def test_finite_numeric_contract(self):
        for value in (True, "18", float("inf"), float("nan"), 10 ** 1000):
            with self.subTest(value=type(value)), self.assertRaises(ValueError):
                fahrenheit(value)


class AgentChecks(unittest.TestCase):
    def run_model(self, model, **options):
        return build_agent_graph(model=model, engine="mini", **options).invoke(agent_initial("teaching request")).state

    def test_weather_conversion_has_real_feedback(self):
        state = self.run_model(ScriptedModel())
        self.assertEqual((state["model_steps"], state["tool_calls"]), (3, 2))
        self.assertEqual(state["messages"][3]["tool_calls"][0]["arguments"], {"temperature_c": 18.0})
        self.assertEqual(state["pending_tool_calls"], [])
        self.assertIn("64.4°F", state["final_answer"])

    def test_weather_only_and_greeting_end_earlier(self):
        for task, counts in (("weather", (2, 1)), ("greet", (1, 0))):
            state = self.run_model(ScriptedModel(task=task))
            self.assertEqual((state["model_steps"], state["tool_calls"]), counts)

    def test_model_limit_keeps_completed_tool_result(self):
        state = self.run_model(ScriptedModel(), max_model_steps=1)
        self.assertEqual(state["model_steps"], 1)
        self.assertEqual(state["messages"][-1]["role"], "tool")
        self.assertEqual(state["error"], "model_budget_exhausted")
        self.assertIsNone(state["final_answer"])

    def test_zero_tool_budget_executes_nothing(self):
        executor = Mock()
        state = self.run_model(ScriptedModel(), max_tool_calls=0, executor=executor)
        executor.assert_not_called()
        self.assertEqual(state["error"], "tool_budget_exhausted")

    def test_entire_batch_validated_before_any_handler(self):
        model = Mock()
        model.generate.return_value = ModelTurn(tool_calls=(ToolCall("a", "get_teaching_weather", {"city": "Tokyo"}),
                                                          ToolCall("b", "get_teaching_weather", {"city": "Moon"})))
        executor = Mock()
        state = self.run_model(model, executor=executor)
        executor.assert_not_called()
        self.assertTrue(state["error"].startswith("invalid_tool_request"))

    def test_partial_execution_failure_keeps_prior_observation(self):
        model = Mock()
        model.generate.return_value = ModelTurn(tool_calls=(ToolCall("a", "get_teaching_weather", {"city": "Tokyo"}),
                                                          ToolCall("b", "get_teaching_weather", {"city": "Paris"})))
        executor = Mock(side_effect=[{"temperature_c": 18.0}, OSError("private diagnostic")])
        state = self.run_model(model, executor=executor)
        self.assertEqual(state["tool_calls"], 2)
        self.assertEqual(len([m for m in state["messages"] if m["role"] == "tool"]), 2)
        self.assertNotIn("private diagnostic", str(state))
        self.assertEqual(model.generate.call_count, 1)

    def test_repeat_id_rejected_before_repeat_execution(self):
        model = Mock()
        model.generate.return_value = ModelTurn(tool_calls=(ToolCall("same", "get_teaching_weather", {"city": "Tokyo"}),))
        state = self.run_model(model)
        self.assertEqual(state["tool_calls"], 1)
        self.assertTrue(state["error"].startswith("model_failed"))

    def test_provider_failure_is_counted_without_fake_answer(self):
        model = Mock()
        model.generate.side_effect = TimeoutError("private request text")
        state = self.run_model(model)
        self.assertEqual(state["model_steps"], 1)
        self.assertNotIn("private request text", str(state))
        self.assertIsNone(state["final_answer"])

    def test_reusing_graph_does_not_share_run_messages(self):
        graph = build_agent_graph(model=ScriptedModel(), engine="mini")
        first = graph.invoke(agent_initial("one")).state
        second = graph.invoke(agent_initial("two")).state
        self.assertEqual(len(first["messages"]), len(second["messages"]))
        self.assertEqual(second["messages"][0]["content"], "two")

    def test_model_sees_messages_not_control_state(self):
        model = Mock()
        model.generate.return_value = ModelTurn(final_answer="done")
        self.run_model(model)
        self.assertEqual(model.generate.call_args.args[0], [{"role": "user", "content": "teaching request"}])

    def test_model_mutation_does_not_rewrite_history(self):
        def mutate(messages):
            messages[0]["content"] = "changed"
            return ModelTurn(final_answer="done")
        model = SimpleNamespace(generate=mutate)
        self.assertEqual(self.run_model(model)["messages"][0]["content"], "teaching request")

    def test_contract_is_not_answer_truth(self):
        model = Mock()
        model.generate.return_value = ModelTurn(final_answer="Tokyo is 99 degrees.")
        state = self.run_model(model)
        self.assertIsNone(state["error"])
        self.assertEqual(state["tool_calls"], 0)
        self.assertIn("99", state["final_answer"])

    def test_invalid_turn_forms_rejected(self):
        for kwargs in ({}, {"final_answer": " "}, {"final_answer": "ok", "tool_calls": (ToolCall("a", "x", {}),)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ModelTurn(**kwargs)

    def test_duplicate_ids_in_one_turn_rejected(self):
        with self.assertRaises(ValueError):
            ModelTurn(tool_calls=(ToolCall("a", "x", {}), ToolCall("a", "x", {})))

    def test_nonfinite_arguments_rejected(self):
        with self.assertRaises(ValueError):
            ToolCall("a", "celsius_to_fahrenheit", {"temperature_c": float("nan")} )

    def test_invalid_limit_types_rejected(self):
        for options in ({"max_model_steps": True}, {"max_model_steps": 0}, {"max_tool_calls": -1}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                make_nodes(ScriptedModel(), **options)


class Item(SimpleNamespace):
    def model_dump(self, **kwargs):
        return deepcopy(vars(self))


def response(*items, text="", status="completed"):
    return SimpleNamespace(output=list(items), output_text=text, status=status)


class ProviderChecks(unittest.TestCase):
    def test_invalid_handler_output_stops_without_final_answer(self):
        model = Mock()
        model.generate.return_value = ModelTurn(tool_calls=(
            ToolCall("one", "get_teaching_weather", {"city": "Tokyo"}),
        ))
        state = build_agent_graph(model=model, engine="mini", executor=lambda call: ["bad"]
                                  ).invoke(agent_initial("weather")).state
        self.assertEqual(state["error"], "tool_failed:ValueError")
        self.assertIsNone(state["final_answer"])
        self.assertEqual(state["tool_calls"], 1)
        self.assertEqual(model.generate.call_count, 1)

    def test_full_provider_items_survive_next_request(self):
        items = [Item(type="reasoning", id="reasoning-1", summary=[]),
                 Item(type="function_call", call_id="weather-1", name="get_teaching_weather", arguments='{"city":"Tokyo"}')]
        api = Mock()
        api.create.side_effect = [response(*items), response(text="done")]
        model = DeepSeekModel(client=SimpleNamespace(responses=api), model="test-model")
        state = build_agent_graph(model=model, engine="mini").invoke(agent_initial("weather")).state
        request = api.create.call_args_list[1].kwargs
        self.assertEqual(request["input"][1:3], [i.model_dump() for i in items])
        self.assertEqual(request["input"][3]["call_id"], "weather-1")
        self.assertNotIn("previous_response_id", request)
        self.assertNotIn("diagnostic_tag", json.dumps(request))
        self.assertEqual(state["model_steps"], 2)

    def test_bad_provider_status_or_empty_final_rejected(self):
        for value in (response(status="incomplete"), response(text=" ")):
            with self.subTest(value=value), self.assertRaises(ProviderResponseError):
                parse_response(value)

    def test_bad_json_and_nonobject_rejected(self):
        for raw in ("bad json", "[]", '{"temperature_c": NaN}'):
            with self.subTest(raw=raw), self.assertRaises(ProviderResponseError):
                parse_response(response(Item(type="function_call", call_id="a", name="x", arguments=raw)))

    def test_calls_take_precedence_over_intermediate_text(self):
        turn = parse_response(response(Item(type="function_call", call_id="a", name="get_teaching_weather", arguments='{"city":"Tokyo"}'), text="Let me check."))
        self.assertIsNone(turn.final_answer)
        self.assertEqual(len(turn.tool_calls), 1)

    def test_live_entry_closes_client_after_failure(self):
        import langgraph_deepseek_agent as live
        client = Mock()
        with patch.object(live, "parse_agent_args", return_value=SimpleNamespace()), \
             patch.object(live, "required_env", return_value="test-model"), \
             patch.object(live, "create_client", return_value=client), \
             patch.object(live, "run_demo", side_effect=RuntimeError("failed")), \
             patch("builtins.print"):
            with self.assertRaises(RuntimeError):
                live.main()
        client.close.assert_called_once_with()

    def test_to_input_copies_provider_items(self):
        messages = [{"role": "assistant", "provider_items": [{"type": "reasoning", "summary": []}]}]
        items = to_input(messages)
        items[0]["summary"].append("change")
        self.assertEqual(messages[0]["provider_items"][0]["summary"], [])


@unittest.skipUnless(find_spec("langgraph"), "LangGraph is not installed; no framework execution claimed")
class RealLangGraphChecks(unittest.TestCase):
    def test_actual_framework_matches_plain_and_mini(self):
        from langgraph_workflow import build_graph
        for style in ("missing-notice", "complete", "stubborn"):
            with self.subTest(style=style):
                actual = build_graph(draft_style=style).invoke(initial_state(), config={"recursion_limit": 30})
                self.assertEqual(actual, run_plain(initial_state(), ReportNodes(draft_style=style)))

    def test_stream_consumes_only_one_run(self):
        from langgraph_workflow import build_graph, run_stream
        reader = Mock(side_effect=lambda city: {"city": city, **TEACHING_WEATHER[city], "source": "fixed teaching record"})
        state = run_stream(build_graph(reader=reader), initial_state())
        self.assertEqual(reader.call_count, 2)
        self.assertEqual(state["status"], "completed")

    def test_update_deltas_differ_from_accumulated_values(self):
        from langgraph_workflow import build_graph
        chunks = list(build_graph().stream(initial_state(), stream_mode=["updates", "values"]))
        updates = [next(iter(data.values())) for mode, data in chunks if mode == "updates"]
        values = [data for mode, data in chunks if mode == "values"]
        self.assertTrue(all(len(update["events"]) == 1 for update in updates))
        self.assertEqual(len(values[-1]["events"]), 6)

    def test_framework_recursion_guard_stops_execution(self):
        from langgraph.errors import GraphRecursionError
        from langgraph_workflow import build_graph
        with self.assertRaises(GraphRecursionError):
            build_graph().invoke(initial_state(), config={"recursion_limit": 1})

    def test_actual_model_tool_graph_matches_mini(self):
        initial = agent_initial("weather")
        actual = build_agent_graph(model=ScriptedModel()).invoke(initial, config={"recursion_limit": 20})
        expected = build_agent_graph(model=ScriptedModel(), engine="mini").invoke(initial).state
        self.assertEqual(actual, expected)


@unittest.skipUnless(find_spec("openai"), "OpenAI SDK is not installed; real SDK mock-HTTP test skipped")
class RealSDKChecks(unittest.TestCase):
    def test_actual_sdk_response_objects_without_network(self):
        import httpx
        from openai import OpenAI
        def serve(request):
            return httpx.Response(200, json={"id": "resp_test", "object": "response", "created_at": 1,
                "model": "test", "status": "completed", "output": [{"type": "message", "id": "msg_test",
                "status": "completed", "role": "assistant", "content": [{"type": "output_text", "text": "Hello.", "annotations": []}]}]})
        with OpenAI(api_key="not-a-secret", base_url="https://example.invalid", max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(serve))) as client:
            self.assertEqual(DeepSeekModel(client=client, model="test").generate([{"role": "user", "content": "hello"}]).final_answer, "Hello.")


if __name__ == "__main__":
    unittest.main(verbosity=2)

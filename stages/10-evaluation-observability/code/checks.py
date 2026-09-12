"""Offline checks for the measuring tools as well as the measured workflow."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import replace
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from cases import default_cases
from contracts import AgentRun, Answer, Order, Request, ToolRecord, json_object
from deepseek_observability import dispatch_tool_call, run_agent
from evaluation import (evaluate, percentile, recall_at_k, reciprocal_rank,
                        regression_gate, score_case, report_dict)
from regression import compare, save_bundle
from scenario import BudgetExceeded, SupportSession, run_offline
from tracing import CapturePolicy, Trace, Tracer, format_trace, trace_dict

HERE = Path(__file__).resolve().parent


def call(name="lookup_order", args='{"order_id":"ORDER-42"}', ident="c1"):
    return NS(id=ident, type="function", function=NS(name=name, arguments=args))


def response(*, calls=None, answer=None, finish=None, usage=True):
    message = NS(content=answer, tool_calls=calls, reasoning_content=None)
    return NS(choices=[NS(message=message, finish_reason=finish or ("tool_calls" if calls else "stop"))],
              usage=NS(prompt_tokens=10, completion_tokens=3) if usage else None)


def final_answer(decision="eligible", evidence=("order:ORDER-42", "refund-policy-v1")):
    return json.dumps({"decision": decision, "text": "A teaching-policy explanation.", "evidence_ids": evidence})


class FakeClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []
        self.chat = NS(completions=self)

    def create(self, **kwargs):
        self.requests.append(deepcopy(kwargs))
        item = next(self.replies)
        if isinstance(item, Exception):
            raise item
        return item


def happy_client():
    return FakeClient([
        response(calls=[call()]),
        response(calls=[call("search_refund_policy", "{}", "c2")]),
        response(answer=final_answer()),
    ])


class TraceChecks(unittest.TestCase):
    def test_parent_links_and_start_order(self):
        trace = Trace("run")
        tracer = Tracer(trace)
        with tracer.span("root"):
            with tracer.span("first"):
                pass
            with tracer.span("second"):
                pass
        root = next(s for s in trace.spans if s.name == "root")
        self.assertTrue(all(s.parent_span_id == root.span_id for s in trace.spans if s != root))
        text = format_trace(trace)
        self.assertLess(text.index("first"), text.index("second"))

    def test_elapsed_time_uses_injected_monotonic_clock(self):
        times = iter((10.0, 10.025))
        trace = Trace("run")
        with Tracer(trace, clock=lambda: next(times)).span("step"):
            pass
        self.assertAlmostEqual(trace.spans[0].duration_ms, 25)
        self.assertGreater(trace.spans[0].started_at, 1000000000)

    def test_exception_is_reraised_without_message_capture(self):
        trace = Trace("run")
        error = RuntimeError("secret-password")
        try:
            with Tracer(trace).span("step"):
                raise error
        except RuntimeError as caught:
            self.assertIs(caught, error)
        self.assertEqual(trace.spans[0].status, "error")
        self.assertNotIn("secret-password", json.dumps(trace_dict(trace)))

    def test_handled_denial_is_not_a_whole_run_exception(self):
        run = run_offline(default_cases()[6].request)
        root = next(s for s in run.trace.spans if s.name == "agent.run")
        self.assertEqual(root.status, "ok")
        self.assertTrue(any(s.name == "tool.authorize" and s.status == "error" for s in run.trace.spans))
        self.assertTrue(score_case(default_cases()[6], run).passed)

    def test_policy_drops_strings_and_nested_secrets(self):
        safe = CapturePolicy().sanitize({"prompt": "secret", "metadata": {"password": "secret"},
                                         "result": ["secret"], "found_count": 2, "outcome": "ok"})
        self.assertEqual(safe, {"found_count": 2, "outcome": "ok"})

    def test_known_key_does_not_allow_wrong_type_or_unknown_label(self):
        safe = CapturePolicy().sanitize({"found_count": {"secret": "x"}, "outcome": "secret",
                                         "tool": "arbitrary-input", "prompt_tokens": float("nan")})
        self.assertEqual(safe, {})

    def test_recorded_attributes_are_a_snapshot(self):
        trace = Trace("run")
        with Tracer(trace).span("step") as attrs:
            attrs["found_count"] = 2
        attrs["found_count"] = 500
        self.assertEqual(trace.spans[0].attributes["found_count"], 2)

    def test_failing_filter_does_not_mask_business_exception(self):
        class Broken:
            def sanitize(self, attrs):
                raise RuntimeError("telemetry-broke")
        trace = Trace("run")
        with self.assertRaisesRegex(ValueError, "business"):
            with Tracer(trace, capture_policy=Broken()).span("step"):
                raise ValueError("business")
        self.assertEqual(trace.telemetry_errors, 1)
        self.assertIn("INCOMPLETE", format_trace(trace))

    def test_capacity_is_visible(self):
        trace = Trace("run")
        tracer = Tracer(trace, max_spans=1)
        with tracer.span("root"):
            with tracer.span("discarded"):
                pass
        self.assertEqual(len(trace.spans), 1)
        self.assertEqual(trace.dropped_spans, 1)
        self.assertIn("INCOMPLETE", format_trace(trace))

    def test_interleaved_async_scopes_do_not_share_a_stack(self):
        async def exercise():
            trace = Trace("async")
            tracer = Tracer(trace)
            ready, proceed = asyncio.Event(), asyncio.Event()
            async def left():
                with tracer.span("left"):
                    ready.set()
                    await proceed.wait()
                    with tracer.span("left-child"):
                        pass
            async def right():
                await ready.wait()
                with tracer.span("right"):
                    proceed.set()
                    await asyncio.sleep(0)
                    with tracer.span("right-child"):
                        pass
            await asyncio.gather(left(), right())
            return trace
        records = {s.name: s for s in asyncio.run(exercise()).spans}
        self.assertIsNone(records["right"].parent_span_id)
        self.assertEqual(records["left-child"].parent_span_id, records["left"].span_id)
        self.assertEqual(records["right-child"].parent_span_id, records["right"].span_id)

    def test_two_traces_do_not_inherit_each_others_parent(self):
        a, b = Trace("a"), Trace("b")
        with Tracer(a).span("a"):
            with Tracer(b).span("b"):
                pass
        self.assertIsNone(b.spans[0].parent_span_id)
        self.assertNotEqual(a.trace_id, b.trace_id)


class WorkflowChecks(unittest.TestCase):
    def test_baseline_and_fixed_pass_all_cases(self):
        for version in ("baseline", "fixed"):
            report = evaluate(default_cases(), lambda r: run_offline(r, version=version), variant=version)
            self.assertEqual(report.pass_rate, 1)

    def test_candidate_loses_exactly_three_cases(self):
        _, candidate, gate = compare("candidate")
        self.assertEqual(candidate.pass_rate, 5 / 8)
        self.assertEqual([s.case_id for s in candidate.scores if not s.passed],
                         ["within-window", "boundary-30", "outside-window"])
        self.assertFalse(gate.accepted)

    def test_green_spans_do_not_imply_correct_answer(self):
        case = default_cases()[1]
        run = run_offline(case.request, version="candidate")
        self.assertTrue(all(s.status == "ok" for s in run.trace.spans))
        self.assertFalse(score_case(case, run).passed)
        self.assertIn("refund-policy-v1", run.retrieved_ids)
        self.assertNotIn("refund-policy-v1", run.visible_ids)

    def test_trace_and_measurements_come_from_same_execution(self):
        run = run_offline(default_cases()[1].request)
        self.assertEqual(run.run_id, run.trace.run_id)
        self.assertEqual(len(run.calls), sum(s.name == "tool.request" for s in run.trace.spans))
        self.assertGreaterEqual(run.latency_ms, next(s.duration_ms for s in run.trace.spans if s.name == "agent.run"))

    def test_boundary_days(self):
        for days, decision in ((0, "eligible"), (30, "eligible"), (31, "ineligible")):
            self.assertEqual(run_offline(Request("Can ORDER-42 be refunded?", orders=(Order(delivered_days=days),))).answer.decision,
                             decision)

    def test_no_evidence_does_not_mean_ineligible(self):
        run = run_offline(default_cases()[4].request)
        self.assertEqual(run.answer.decision, "insufficient_evidence")
        self.assertEqual(run.answer.evidence_ids, ())

    def test_denied_order_is_never_executed_or_exposed(self):
        run = run_offline(default_cases()[6].request)
        self.assertFalse(any(s.name == "tool.execute" for s in run.trace.spans))
        self.assertEqual(run.retrieved_ids, ())
        self.assertEqual(run.answer.decision, "access_denied")

    def test_wrong_arguments_rejected_before_execution(self):
        session = SupportSession(Request("q"), version="baseline")
        result = session.dispatch("lookup_order", {"order_id": 42})
        self.assertFalse(result["ok"])
        self.assertEqual(session.calls[0].outcome, "rejected")
        self.assertFalse(any(s.name == "tool.execute" for s in session.trace.spans))

    def test_unknown_tool_cannot_execute_and_is_not_in_span_name(self):
        session = SupportSession(Request("q"), version="baseline")
        result = session.dispatch("secret-name", {})
        self.assertEqual(result["error"], "unknown_tool")
        self.assertNotIn("secret-name", json.dumps(trace_dict(session.trace)))

    def test_budget_counts_rejections_too(self):
        session = SupportSession(Request("q"), version="baseline", max_tools=1)
        session.dispatch("unknown", {})
        with self.assertRaises(BudgetExceeded):
            session.dispatch("search_refund_policy", {})

    def test_fixed_run_does_not_depend_on_candidate_state(self):
        request = default_cases()[1].request
        run_offline(request, version="candidate")
        self.assertEqual(run_offline(request, version="fixed").answer.decision, "eligible")


class GraderChecks(unittest.TestCase):
    def setUp(self):
        self.case = default_cases()[1]
        self.run = run_offline(self.case.request)

    def test_lucky_answer_without_actions_does_not_pass(self):
        changed = replace(self.run, calls=(), retrieved_ids=(), visible_ids=())
        score = score_case(self.case, changed)
        self.assertTrue(score.decision_ok)
        self.assertFalse(score.trajectory_ok)
        self.assertFalse(score.evidence_ok)

    def test_either_permitted_tool_order_is_valid(self):
        self.assertTrue(score_case(self.case, replace(self.run, calls=tuple(reversed(self.run.calls)))).passed)

    def test_wrong_argument_fails_even_with_correct_tool_names(self):
        calls = (ToolRecord.of("lookup_order", {"order_id": "ORDER-99"}), self.run.calls[1])
        self.assertFalse(score_case(self.case, replace(self.run, calls=calls)).trajectory_ok)

    def test_duplicate_tool_request_is_not_ignored(self):
        self.assertFalse(score_case(self.case, replace(self.run, calls=self.run.calls * 2)).trajectory_ok)

    def test_failed_call_is_not_mistaken_for_success(self):
        calls = (replace(self.run.calls[0], outcome="failed"), self.run.calls[1])
        self.assertFalse(score_case(self.case, replace(self.run, calls=calls)).trajectory_ok)

    def test_invented_citation_fails(self):
        answer = replace(self.run.answer, evidence_ids=("invented",))
        self.assertFalse(score_case(self.case, replace(self.run, answer=answer)).evidence_ok)

    def test_retrieved_but_not_visible_citation_fails(self):
        self.assertFalse(score_case(self.case, replace(self.run, visible_ids=())).evidence_ok)

    def test_truncated_diagnostics_fail_closed_in_this_eval(self):
        self.run.trace.dropped_spans = 1
        self.assertFalse(score_case(self.case, self.run).diagnostics_ok)

    def test_runner_receives_no_expected_answer(self):
        def runner(request):
            self.assertIsInstance(request, Request)
            self.assertFalse(hasattr(request, "expected_decision"))
            return run_offline(request)
        evaluate([self.case], runner, variant="probe")

    def test_crash_stays_in_denominator_and_next_case_runs(self):
        def runner(request):
            if request.question == "hello":
                raise RuntimeError("secret")
            return run_offline(request)
        report = evaluate(default_cases()[:2], runner, variant="fault")
        self.assertEqual(len(report.scores), 2)
        self.assertEqual(report.pass_rate, .5)
        self.assertEqual(report.runs[0].error, "runner_error")
        self.assertNotIn("secret", json.dumps(report_dict(report)))

    def test_empty_and_duplicate_cases_rejected(self):
        for cases in ([], [self.case, self.case]):
            with self.assertRaises(ValueError):
                evaluate(cases, run_offline, variant="bad")

    def test_each_trial_has_unique_ids(self):
        report = evaluate(default_cases(), run_offline, variant="baseline")
        self.assertEqual(len({r.run_id for r in report.runs}), 8)
        with self.assertRaises(ValueError):
            evaluate(default_cases()[:2], lambda _: self.run, variant="reused")

    def test_changed_labels_cannot_be_compared(self):
        before = evaluate([self.case], run_offline, variant="b")
        after = evaluate([replace(self.case, expected_decision="ineligible")], run_offline, variant="a")
        with self.assertRaises(ValueError):
            regression_gate(before, after)

    def test_equal_overall_score_can_still_hide_a_regression(self):
        base = evaluate(default_cases()[:2], run_offline, variant="base")
        failed0 = replace(base.scores[0], decision_ok=False)
        failed1 = replace(base.scores[1], decision_ok=False)
        before = replace(base, scores=(failed0, base.scores[1]))
        after = replace(base, scores=(base.scores[0], failed1))
        self.assertEqual(before.pass_rate, after.pass_rate)
        self.assertFalse(regression_gate(before, after, minimum_pass_rate=.5).accepted)

    def test_critical_failure_rejected_even_if_not_a_new_regression(self):
        base = evaluate(default_cases(), run_offline, variant="base")
        bad = tuple(replace(s, decision_ok=False) if s.case_id == "foreign-order" else s for s in base.scores)
        report = replace(base, scores=bad)
        gate = regression_gate(report, report, minimum_pass_rate=0)
        self.assertIn("critical_failed:foreign-order", gate.reasons)

    def test_fixed_gate_accepts(self):
        self.assertTrue(compare("fixed")[2].accepted)

    def test_unknown_price_is_not_zero_cost(self):
        report = evaluate([self.case], run_offline, variant="local")
        self.assertIsNone(report.metrics()["total_estimated_cost_usd"])
        self.assertEqual(report.metrics()["cost_coverage"], 0)
        self.assertEqual(report.metrics()["model_calls"], 0)

    def test_percentile_is_nearest_rank_not_a_claim_about_population(self):
        self.assertEqual(percentile([1, 2, 3, 100]), 100)
        self.assertEqual(percentile(list(range(1, 101))), 95)
        for values in ([], [float("nan")], [-1]):
            with self.assertRaises(ValueError):
                percentile(values)

    def test_recall_rr_and_unlabeled_query(self):
        self.assertEqual(recall_at_k(["a", "a", "b"], {"a", "b"}, k=2), .5)
        self.assertEqual(reciprocal_rank(["x", "a"], {"a", "b"}), .5)
        self.assertEqual(reciprocal_rank(["x"], {"a"}), 0)
        self.assertIsNone(recall_at_k(["x"], set(), k=1))
        self.assertIsNone(reciprocal_rank([], set()))
        for k in (-1, 0, True):
            with self.assertRaises(ValueError):
                recall_at_k(["a"], {"a"}, k=k)

    def test_free_prose_quality_is_not_claimed_by_contract_grader(self):
        # A known blind spot: matching decision/citations does not verify every sentence.
        changed = replace(self.run, answer=replace(self.run.answer, text="Contradictory prose requiring human review."))
        self.assertTrue(score_case(self.case, changed).passed)


class ModelAdapterChecks(unittest.TestCase):
    def test_valid_json_contract_and_rejection_of_ambiguous_json(self):
        self.assertEqual(Answer.parse(final_answer()).decision, "eligible")
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '[]', ''):
            with self.assertRaises(ValueError):
                json_object(raw)
        for raw in ('{"decision":"greeting","text":"hi","evidence_ids":[],"extra":1}',
                    '{"decision":"nonsense","text":"hi","evidence_ids":[]}',
                    '{"decision":"greeting","text":"","evidence_ids":[]}',
                    '{"decision":"greeting","text":"hi","evidence_ids":[1]}'):
            with self.assertRaises(ValueError):
                Answer.parse(raw)

    def test_success_records_actual_model_calls_and_tokens(self):
        run = run_agent(default_cases()[1].request, model="fake", client=happy_client())
        self.assertIsNone(run.error)
        self.assertTrue(score_case(default_cases()[1], run).passed)
        self.assertEqual(run.model_calls, 3)
        self.assertEqual((run.prompt_tokens, run.completion_tokens), (30, 9))
        self.assertEqual(sum(s.name == "model.generate" for s in run.trace.spans), 3)

    def test_next_request_contains_assistant_call_and_corresponding_result(self):
        client = happy_client()
        run_agent(default_cases()[1].request, model="fake", client=client)
        messages = client.requests[1]["messages"]
        self.assertEqual(messages[-2]["tool_calls"][0]["id"], "c1")
        self.assertEqual(messages[-1]["tool_call_id"], "c1")
        self.assertEqual(messages[-1]["role"], "tool")

    def test_model_sees_tool_data_not_reference_label_or_fixture_store(self):
        client = happy_client()
        run_agent(default_cases()[1].request, model="fake", client=client)
        first = json.dumps(client.requests[0])
        self.assertNotIn("expected_decision", first)
        self.assertNotIn("delivered_days", first)
        self.assertNotIn("alice", first)

    def test_missing_usage_remains_unknown(self):
        client = FakeClient([response(calls=[call()], usage=False), response(answer=final_answer())])
        run = run_agent(default_cases()[1].request, model="fake", client=client)
        self.assertIsNone(run.prompt_tokens)
        self.assertIsNone(run.completion_tokens)

    def test_provider_failure_returns_an_observable_failed_trial(self):
        run = run_agent(Request("hello"), model="fake", client=FakeClient([RuntimeError("api_key=secret")]))
        self.assertEqual(run.error, "provider_error")
        self.assertEqual(run.model_calls, 1)
        self.assertIsNone(run.prompt_tokens)
        self.assertNotIn("secret", json.dumps(trace_dict(run.trace)))
        self.assertTrue(any(s.status == "error" for s in run.trace.spans))

    def test_truncated_or_empty_answer_is_not_graded_as_completed(self):
        for reply in (response(answer=final_answer(), finish="length"), response(answer=""), NS(choices=[], usage=None)):
            run = run_agent(Request("hello"), model="fake", client=FakeClient([reply]))
            self.assertEqual(run.error, "invalid_provider_response")
            self.assertIsNone(run.answer)

    def test_invalid_json_tool_arguments_never_execute(self):
        session = SupportSession(Request("q"), version="live")
        out = dispatch_tool_call(call("search_refund_policy", "not-json"), session=session)
        self.assertFalse(json.loads(out)["ok"])
        self.assertEqual(session.calls[0].outcome, "rejected")
        self.assertFalse(session.documents)

    def test_extra_fields_are_rejected(self):
        session = SupportSession(Request("q"), version="live")
        out = dispatch_tool_call(call(args='{"order_id":"ORDER-42","user_id":"bob"}'), session=session)
        self.assertEqual(json.loads(out)["error"], "invalid_arguments")

    def test_repeated_call_id_is_rejected_before_second_execution(self):
        client = FakeClient([response(calls=[call()]), response(calls=[call()])])
        run = run_agent(Request("q"), model="fake", client=client)
        self.assertEqual(run.error, "invalid_provider_response")
        self.assertEqual(len(run.calls), 1)

    def test_over_budget_batch_executes_nothing(self):
        client = FakeClient([response(calls=[call(ident="a"), call(ident="b")])])
        run = run_agent(Request("q"), model="fake", client=client, max_tools=1)
        self.assertEqual(run.error, "budget_exceeded")
        self.assertEqual(run.calls, ())

    def test_model_round_limit_is_bounded(self):
        run = run_agent(Request("q"), model="fake", client=FakeClient([response(calls=[call()])]), max_rounds=1)
        self.assertEqual(run.error, "budget_exceeded")
        self.assertEqual(run.model_calls, 1)

    def test_reasoning_is_forwarded_only_as_protocol_not_telemetry(self):
        reply = response(calls=[call()])
        reply.choices[0].message.reasoning_content = "private-reasoning-marker"
        client = FakeClient([reply, response(answer=final_answer())])
        run = run_agent(Request("q"), model="fake", client=client)
        self.assertEqual(client.requests[1]["messages"][2]["reasoning_content"], "private-reasoning-marker")
        self.assertNotIn("private-reasoning-marker", json.dumps(trace_dict(run.trace)))


class EntryPointChecks(unittest.TestCase):
    def test_regression_exit_codes(self):
        for variant, expected in (("candidate", 1), ("fixed", 0)):
            result = subprocess.run([sys.executable, str(HERE / "regression.py"), "--candidate", variant],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_default_demo_runs_and_explains_failure(self):
        result = subprocess.run([sys.executable, str(HERE / "demo.py")], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("passed: False", result.stdout)
        self.assertIn("selected_count=1", result.stdout)

    def test_export_is_correlated_minimized_and_no_overwrite(self):
        before, after, gate = compare("fixed")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result"
            save_bundle(path, before, after, gate)
            data = json.loads((path / "candidate.json").read_text(encoding="utf-8"))
            self.assertEqual(data["suite_fingerprint"], after.suite_fingerprint)
            run_id = data["cases"][0]["run_id"]
            self.assertTrue((path / f"{run_id}.trace.json").is_file())
            exported = "".join(p.read_text(encoding="utf-8") for p in path.iterdir())
            self.assertNotIn("Can ORDER-42", exported)
            self.assertNotIn('"arguments_json"', exported)
            with self.assertRaises(FileExistsError):
                save_bundle(path, before, after, gate)

    def test_optional_real_otel_sdk_emits_parent_and_child(self):
        try:
            from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        except ImportError:
            self.skipTest("optional OpenTelemetry SDK not installed")
        from otel_demo import run_demo
        exporter = InMemorySpanExporter()
        self.assertTrue(run_demo(exporter)["ok"])
        spans = exporter.get_finished_spans()
        self.assertEqual(len(spans), 2)
        root = next(s for s in spans if s.name == "support.inspect")
        child = next(s for s in spans if s.name == "tool.lookup_order")
        self.assertEqual(child.parent.span_id, root.context.span_id)
        self.assertEqual(child.context.trace_id, root.context.trace_id)
        self.assertEqual(child.attributes["evidence.count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

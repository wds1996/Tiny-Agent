"""Offline behavior checks: no SDK import, network call, credentials or paid model."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
from threading import Barrier, Event, Lock
from types import SimpleNamespace as NS
import unittest

from deepseek_team import DeepSeekSpecialist, ModelGateway, ProviderError, parse_call, run_live
from evaluation import evaluate
from scenario import ASSIGNMENTS, CONTEXT_KEYS, build_team, combine, from_messages, make_context, operations, risk
from team import (AgentMessage, AgentSpec, BudgetExceeded, Finding, InvalidResult,
                  OwnershipError, PolicyDenied, Principal, TeamLimits, TeamPolicy,
                  TeamRuntime, json_copy, project_context, validate_finding)


def ok(task, view):
    return Finding("ok", "accepted", {"seen": view})


def fake_call(target="operations", *, rid="call-1", name="ask_specialist", extra=None):
    args = {"specialist": target, **(extra or {})}
    return NS(id=rid, type="function", function=NS(name=name, arguments=json.dumps(args)))


def response(content="done", calls=None, finish=None):
    return NS(choices=[NS(finish_reason=finish or ("tool_calls" if calls else "stop"),
                          message=NS(content=content, tool_calls=calls))],
              usage=NS(total_tokens=42))


def finding_response(fn, name, context):
    finding = fn(ASSIGNMENTS[name], project_context(context, CONTEXT_KEYS[name]))
    return response(json.dumps(asdict(finding)))


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kwargs):
        self.requests.append(json_copy(kwargs, limit=100_000))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def live_client(*, real_data=False):
    context = make_context(real_data=real_data)
    return FakeClient([
        response(None, [fake_call(), fake_call("risk", rid="call-2")]),
        finding_response(operations, "operations", context),
        finding_response(risk, "risk", context),
        response("A proposed pilot is not measured success."),
    ])


class TeamChecks(unittest.TestCase):
    def test_projection_selects_and_deep_copies(self):
        source = {"nested": {"n": 1}, "secret": "do-not-copy"}
        view = project_context(source, ("nested", "absent"))
        view["nested"]["n"] = 2
        self.assertEqual(source["nested"]["n"], 1)
        self.assertEqual(set(view), {"nested"})

    def test_context_snapshot_is_not_changed_by_caller(self):
        context = make_context()
        runtime = build_team(context)
        context["operations_note"]["staff"] = 999
        message = runtime.delegate(caller="coordinator", target="operations")
        self.assertEqual(message.finding.facts["staff"], 20)

    def test_assignment_and_context_are_chosen_by_host(self):
        captured = []
        def capture(task, view):
            captured.append((task, view))
            return operations(task, view)
        runtime = build_team(make_context(), handlers={"operations": capture})
        runtime.delegate(caller="coordinator", target="operations")
        self.assertEqual(captured[0][0], ASSIGNMENTS["operations"])
        self.assertEqual(set(captured[0][1]), {"brief", "operations_note"})

    def test_principal_and_edge_are_both_checked(self):
        runtime = build_team(make_context(), principal=Principal("guest", frozenset({"guest"})))
        with self.assertRaises(PolicyDenied):
            runtime.delegate(caller="coordinator", target="operations")
        self.assertEqual(runtime.calls_used, 0)
        self.assertEqual(runtime.events[0].error_code, "policy_denied")

    def test_authorized_target_does_not_authorize_other_operation(self):
        runtime = build_team(make_context())
        with self.assertRaises(PolicyDenied):
            runtime.handoff(caller="coordinator", target="operations")
        self.assertEqual(runtime.owner, "coordinator")

    def test_unknown_target_never_runs(self):
        runtime = build_team(make_context())
        with self.assertRaises(PolicyDenied):
            runtime.delegate(caller="coordinator", target="deploy")
        self.assertEqual(runtime.calls_used, 0)

    def test_self_delegation_is_rejected(self):
        with self.assertRaises(OwnershipError):
            build_team(make_context()).delegate(caller="coordinator", target="coordinator")

    def test_wrong_caller_is_rejected(self):
        with self.assertRaises(OwnershipError):
            build_team(make_context()).delegate(caller="operations", target="risk")

    def test_delegation_retains_owner_and_correlates_results(self):
        runtime = build_team(make_context(), run_id="r-1")
        messages = runtime.fan_out(caller="coordinator", targets=("operations", "risk"))
        self.assertEqual(runtime.owner, "coordinator")
        self.assertEqual([m.request_id for m in messages], ["r-1:1", "r-1:2"])
        self.assertEqual([e.request_id for e in runtime.events], [m.request_id for m in messages])

    def test_sender_envelope_is_assigned_by_runtime(self):
        def forged(task, view):
            return Finding("ok", "attempted metadata override", {"agent": "privacy", "owner": "privacy"})
        runtime = build_team(make_context(), handlers={"operations": forged})
        result = runtime.delegate(caller="coordinator", target="operations")
        self.assertEqual(result.agent, "operations")
        self.assertEqual(runtime.owner, "coordinator")

    def test_run_identity_and_source_views_do_not_bleed_between_runs(self):
        a = build_team(make_context(), run_id="first")
        other = make_context()
        other["operations_note"]["staff"] = 40
        b = build_team(other, run_id="second")
        ra = a.delegate(caller="coordinator", target="operations")
        rb = b.delegate(caller="coordinator", target="operations")
        self.assertEqual((ra.finding.facts["staff"], rb.finding.facts["staff"]), (20, 40))
        self.assertNotEqual(ra.request_id, rb.request_id)

    def test_returned_result_cannot_mutate_saved_message(self):
        runtime = build_team(make_context())
        result = runtime.delegate(caller="coordinator", target="operations")
        result.finding.facts["staff"] = 999
        self.assertEqual(runtime.messages[0].finding.facts["staff"], 20)
        snapshot = runtime.messages
        snapshot[0].finding.facts["staff"] = 123
        self.assertEqual(runtime.messages[0].finding.facts["staff"], 20)

    def test_failure_is_recorded_without_exception_text(self):
        def failing(task, view):
            raise RuntimeError("SECRET_EXCEPTION_BODY")
        runtime = build_team(make_context(), handlers={"risk": failing})
        result = runtime.delegate(caller="coordinator", target="risk")
        self.assertEqual(result.finding.status, "failed")
        self.assertEqual(result.error_code, "execution_error")
        self.assertNotIn("SECRET_EXCEPTION_BODY", str(result) + str(runtime.events))
        self.assertEqual(runtime.calls_used, 1)

    def test_malformed_result_does_not_become_success(self):
        for bad in (None, "done", Finding("unknown", "bad"), Finding("ok", ""),
                    Finding("ok", "x", {"bad": object()}), Finding("ok", "x" * 9000)):
            with self.subTest(value=type(bad).__name__):
                runtime = build_team(make_context(), handlers={"risk": lambda t, c, value=bad: value})
                result = runtime.delegate(caller="coordinator", target="risk")
                self.assertEqual(result.error_code, "invalid_result")

    def test_batch_policy_is_checked_before_any_execution(self):
        calls = []
        runtime = build_team(make_context(), handlers={"operations": lambda t, c: calls.append(t)})
        with self.assertRaises(PolicyDenied):
            runtime.fan_out(caller="coordinator", targets=("operations", "privacy"))
        self.assertEqual(calls, [])
        self.assertEqual(runtime.calls_used, 0)

    def test_batch_budget_is_reserved_before_any_execution(self):
        runtime = build_team(make_context(), limits=TeamLimits(max_delegations=1))
        with self.assertRaises(BudgetExceeded):
            runtime.fan_out(caller="coordinator", targets=("operations", "risk"))
        self.assertEqual(runtime.messages, ())
        self.assertEqual(runtime.calls_used, 0)

    def test_failed_calls_consume_the_shared_budget(self):
        def failing(task, view):
            raise OSError("no")
        runtime = build_team(make_context(), limits=TeamLimits(max_delegations=1), handlers={"risk": failing})
        runtime.delegate(caller="coordinator", target="risk")
        with self.assertRaises(BudgetExceeded):
            runtime.delegate(caller="coordinator", target="operations")

    def test_duplicate_batch_target_is_rejected(self):
        with self.assertRaises(ValueError):
            build_team(make_context()).fan_out(caller="coordinator", targets=("risk", "risk"))

    def test_parallel_handlers_really_overlap_and_results_keep_order(self):
        barrier = Barrier(2)
        def operation(task, view):
            barrier.wait(timeout=2)
            return operations(task, view)
        def risks(task, view):
            barrier.wait(timeout=2)
            return risk(task, view)
        runtime = build_team(make_context(), handlers={"operations": operation, "risk": risks})
        results = runtime.fan_out(caller="coordinator", targets=("operations", "risk"), parallel=True)
        self.assertEqual([r.agent for r in results], ["operations", "risk"])
        self.assertEqual([r.finding.status for r in results], ["ok", "ok"])

    def test_parallel_views_are_independent_nested_copies(self):
        barrier = Barrier(2)
        def mutate(task, view):
            view["brief"]["use_real_conversations"] = True
            barrier.wait(timeout=2)
            return operations(task, view)
        def observe(task, view):
            barrier.wait(timeout=2)
            return risk(task, view)
        runtime = build_team(make_context(), handlers={"operations": mutate, "risk": observe})
        result = runtime.fan_out(caller="coordinator", targets=("operations", "risk"), parallel=True)
        self.assertFalse(result[1].finding.facts["privacy_review_required"])

    def test_worker_count_is_respected(self):
        lock = Lock()
        active = 0
        peak = 0
        def count(task, view):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            Event().wait(0.03)
            with lock:
                active -= 1
            return Finding("ok", "counted")
        runtime = build_team(make_context(), limits=TeamLimits(max_workers=1),
                             handlers={"operations": count, "risk": count})
        runtime.fan_out(caller="coordinator", targets=("operations", "risk"), parallel=True)
        self.assertEqual(peak, 1)

    def test_one_failed_parallel_branch_does_not_erase_other_result(self):
        def fail(task, view):
            raise TimeoutError("failure")
        runtime = build_team(make_context(), handlers={"risk": fail})
        results = runtime.fan_out(caller="coordinator", targets=("operations", "risk"), parallel=True)
        self.assertEqual([r.finding.status for r in results], ["ok", "failed"])
        self.assertEqual(from_messages(results).status, "failed")

    def test_handoff_changes_enforced_owner_and_filters_findings(self):
        captured = []
        def receiver(task, view):
            captured.append(view)
            return Finding("needs_input", "Need clarification.")
        runtime = build_team(make_context(), handlers={"privacy": receiver})
        runtime.fan_out(caller="coordinator", targets=("operations", "risk"))
        runtime.handoff(caller="coordinator", target="privacy")
        self.assertEqual(runtime.owner, "privacy")
        self.assertEqual([f["agent"] for f in captured[0]["handoff"]["findings"]], ["risk"])
        self.assertNotIn("private_note", str(captured))
        with self.assertRaises(OwnershipError):
            runtime.finish(caller="coordinator", answer="old owner")
        with self.assertRaises(OwnershipError):
            runtime.delegate(caller="coordinator", target="operations")
        with self.assertRaises(OwnershipError):
            runtime.handoff(caller="coordinator", target="privacy")
        self.assertEqual(runtime.finish(caller="privacy", answer="new owner"), "new owner")

    def test_failed_handoff_keeps_target_as_owner(self):
        def fail(task, view):
            raise RuntimeError("no")
        runtime = build_team(make_context(), handlers={"privacy": fail})
        result = runtime.handoff(caller="coordinator", target="privacy")
        self.assertEqual((runtime.owner, result.finding.status), ("privacy", "failed"))

    def test_handoff_budget_is_separate(self):
        runtime = build_team(make_context(), limits=TeamLimits(max_delegations=0, max_handoffs=1))
        self.assertEqual(runtime.handoff(caller="coordinator", target="privacy").agent, "privacy")
        runtime = build_team(make_context(), limits=TeamLimits(max_handoffs=0))
        with self.assertRaises(BudgetExceeded):
            runtime.handoff(caller="coordinator", target="privacy")
        self.assertEqual(runtime.owner, "coordinator")

    def test_longer_handoff_cycle_is_rejected(self):
        agents = [AgentSpec(name, "work", (), ok) for name in ("a", "b", "c")]
        policy = TeamPolicy({("handoff", "a", "b"): frozenset({"r"}),
                             ("handoff", "b", "c"): frozenset({"r"}),
                             ("handoff", "c", "a"): frozenset({"r"})})
        runtime = TeamRuntime(agents, run_id="cycle", principal=Principal("u", frozenset({"r"})),
                              context={}, policy=policy, owner="a", limits=TeamLimits(max_handoffs=5))
        runtime.handoff(caller="a", target="b")
        runtime.handoff(caller="b", target="c")
        with self.assertRaises(OwnershipError):
            runtime.handoff(caller="c", target="a")
        self.assertEqual(runtime.owner, "c")

    def test_finished_run_cannot_continue(self):
        runtime = build_team(make_context())
        runtime.finish(caller="coordinator", answer="done")
        with self.assertRaises(OwnershipError):
            runtime.delegate(caller="coordinator", target="risk")

    def test_deadline_rejects_late_result_and_new_calls(self):
        now = [0.0]
        def slow(task, context):
            now[0] = 2.0
            return Finding("ok", "too late")
        runtime = TeamRuntime([AgentSpec("a", "work", (), slow)], run_id="deadline",
            principal=Principal("u", frozenset({"r"})), context={},
            policy=TeamPolicy({("delegate", "coordinator", "a"): frozenset({"r"})}),
            limits=TeamLimits(deadline_seconds=1), clock=lambda: now[0])
        self.assertEqual(runtime.delegate(caller="coordinator", target="a").error_code, "deadline_exceeded")
        with self.assertRaises(BudgetExceeded):
            runtime.delegate(caller="coordinator", target="a")

    def test_events_do_not_capture_contents(self):
        runtime = build_team(make_context())
        runtime.fan_out(caller="coordinator", targets=("operations", "risk"))
        serialized = json.dumps([asdict(e) for e in runtime.events])
        self.assertNotIn("SYNTHETIC-PRIVATE", serialized)
        self.assertNotIn("Pilot scope extracted", serialized)
        self.assertIn("context_keys", serialized)

    def test_configuration_and_data_validation(self):
        for value in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                TeamLimits(max_delegations=value)
        with self.assertRaises(ValueError):
            TeamLimits(max_workers=0)
        with self.assertRaises(ValueError):
            TeamLimits(deadline_seconds=float("nan"))
        with self.assertRaises(ValueError):
            json_copy({"v": float("nan")})
        with self.assertRaises(ValueError):
            AgentSpec("", "task", (), ok)
        with self.assertRaises(ValueError):
            TeamRuntime([AgentSpec("a", "task", (), ok)] * 2, run_id="x",
                        principal=Principal("u", frozenset()), context={}, policy=TeamPolicy({}))


class ScenarioChecks(unittest.TestCase):
    def assess(self, context, **kwargs):
        rt = build_team(context, **kwargs)
        return from_messages(rt.fan_out(caller="coordinator", targets=("operations", "risk")))

    def test_normal_assessment_is_not_rollout_approval(self):
        result = self.assess(make_context())
        self.assertEqual(result.status, "ready_for_draft")
        self.assertIn("20 staff", result.summary)
        self.assertIn("No pilot results", result.summary)
        self.assertIn("not execute refunds", result.summary)
        self.assertEqual(result.evidence_ids, ("ops-01", "policy-01"))

    def test_missing_information_is_not_policy_denial(self):
        context = make_context()
        context.pop("policy_note")
        self.assertEqual(self.assess(context).status, "needs_input")

    def test_conflict_is_not_settled_by_voting(self):
        context = make_context()
        context["operations_note"]["refunds_allowed"] = True
        self.assertEqual(self.assess(context).status, "conflict")

    def test_real_data_requires_clarification(self):
        self.assertEqual(self.assess(make_context(real_data=True)).status, "needs_review")

    def test_malformed_facts_and_missing_sources_block_ready_status(self):
        good = {"operations": operations("", make_context()), "risk": risk("", make_context())}
        for bad in (Finding("ok", "nice", {}), Finding("ok", "nice", good["operations"].facts)):
            self.assertEqual(combine({**good, "operations": bad}).status, "needs_input")

    def test_cross_run_and_duplicate_messages_are_not_combined(self):
        a = build_team(make_context(), run_id="a").delegate(caller="coordinator", target="operations")
        b = build_team(make_context(), run_id="b").delegate(caller="coordinator", target="risk")
        with self.assertRaises(ValueError):
            from_messages((a, b))
        with self.assertRaises(ValueError):
            from_messages((a, a))

    def test_single_and_team_comparison_does_not_fake_model_metrics(self):
        rows = evaluate()
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(row["passed"] for row in rows))
        self.assertTrue(all(row["model_requests"] == 0 and row["model_tokens"] is None
                            and row["model_cost"] is None for row in rows))


class ProviderChecks(unittest.TestCase):
    def test_live_flow_with_fake_provider_keeps_context_private(self):
        client = live_client()
        gateway = ModelGateway(client, "fake")
        result = run_live(gateway)
        self.assertEqual(result["assessment"]["status"], "ready_for_draft")
        self.assertEqual(gateway.calls, 4)
        self.assertNotIn("SYNTHETIC-PRIVATE", json.dumps(client.requests))
        self.assertNotIn("policy_note", client.requests[1]["messages"][1]["content"])
        self.assertNotIn("operations_note", client.requests[2]["messages"][1]["content"])
        returned_ids = [m["tool_call_id"] for m in client.requests[-1]["messages"] if m["role"] == "tool"]
        self.assertEqual(returned_ids, ["call-1", "call-2"])
        self.assertEqual(client.requests[0]["extra_body"], {"thinking": {"type": "disabled"}})

    def test_live_handoff_keeps_host_decision_separate_from_model_prose(self):
        result = run_live(ModelGateway(live_client(real_data=True), "fake"), real_data=True)
        self.assertEqual(result["owner"], "privacy")
        self.assertIsNone(result["model_commentary_unverified"])
        self.assertIn("consent", result["reply"])

    def test_unknown_tool_is_rejected_before_running_specialists(self):
        client = FakeClient([response(None, [fake_call(name="execute_refund")])])
        gateway = ModelGateway(client, "fake")
        with self.assertRaises(ProviderError):
            run_live(gateway)
        self.assertEqual(gateway.calls, 1)

    def test_argument_contract_rejects_extra_fields_types_and_bad_json(self):
        for call in (fake_call(extra={"task": "leak secret"}), fake_call(extra={"context_keys": ["private_note"]}),
                     fake_call(target="privacy"), fake_call(target=[])):
            with self.assertRaises(ProviderError):
                parse_call(call)
        for raw in ("broken", "[]", '{"specialist":true}', '"operations"'):
            call = fake_call()
            call.function.arguments = raw
            with self.assertRaises(ProviderError):
                parse_call(call)

    def test_duplicate_call_ids_are_rejected_before_dispatch(self):
        gateway = ModelGateway(FakeClient([response(None, [fake_call(), fake_call("risk")])]), "fake")
        with self.assertRaises(ProviderError):
            run_live(gateway)
        self.assertEqual(gateway.calls, 1)

    def test_repeated_id_across_rounds_is_rejected(self):
        context = make_context()
        client = FakeClient([response(None, [fake_call()]), finding_response(operations, "operations", context),
                             response(None, [fake_call("risk")])])
        gateway = ModelGateway(client, "fake")
        with self.assertRaises(ProviderError):
            run_live(gateway)
        self.assertEqual(gateway.calls, 3)

    def test_early_final_is_not_accepted_without_observations(self):
        with self.assertRaises(ProviderError):
            run_live(ModelGateway(FakeClient([response("Everything approved.")]), "fake"))

    def test_supervisor_round_limit(self):
        context = make_context()
        client = FakeClient([response(None, [fake_call()]), finding_response(operations, "operations", context)])
        with self.assertRaises(ProviderError):
            run_live(ModelGateway(client, "fake"), max_rounds=1)

    def test_shared_model_request_limit(self):
        client = live_client()
        gateway = ModelGateway(client, "fake", max_calls=2)
        with self.assertRaises(ProviderError):
            run_live(gateway)
        self.assertEqual(gateway.calls, 2)
        self.assertEqual(len(client.requests), 2)

    def test_failed_model_request_is_counted_without_leaking_error(self):
        gateway = ModelGateway(FakeClient([RuntimeError("SECRET_API_BODY")]), "fake", max_calls=1)
        with self.assertRaisesRegex(ProviderError, "provider request failed") as caught:
            gateway.ask([])
        self.assertNotIn("SECRET_API_BODY", str(caught.exception))
        self.assertEqual(gateway.calls, 1)
        with self.assertRaises(ProviderError):
            gateway.ask([])

    def test_empty_or_truncated_response_rejected(self):
        for reply in (NS(choices=[], usage=None), response("", finish="stop"), response("partial", finish="length"),
                      response("blocked", finish="content_filter")):
            with self.assertRaises(ProviderError):
                ModelGateway(FakeClient([reply]), "fake").ask([])

    def test_fake_specialist_cannot_invent_sources_or_change_facts(self):
        original = asdict(operations("", make_context()))
        variants = [{**original, "evidence_ids": ["invented-source"]},
                    {**original, "facts": {**original["facts"], "staff": 200}},
                    {**original, "facts": {**original["facts"], "refunds_allowed": 0}},
                    {**original, "extra": "field"}]
        for payload in variants:
            specialist = DeepSeekSpecialist("operations", ModelGateway(FakeClient([response(json.dumps(payload))]), "fake"))
            with self.assertRaises(InvalidResult):
                specialist.run(ASSIGNMENTS["operations"], make_context())

    def test_invalid_specialist_result_blocks_unverified_supervisor_comment(self):
        client = live_client()
        client.replies[1] = response('{"status": "ok", "summary":"great", "facts":{}, "evidence_ids":[]}')
        result = run_live(ModelGateway(client, "fake"))
        self.assertEqual(result["assessment"]["status"], "failed")
        self.assertIsNone(result["model_commentary_unverified"])

    def test_missing_usage_is_not_fabricated(self):
        reply = response()
        reply.usage = None
        gateway = ModelGateway(FakeClient([reply]), "fake")
        gateway.ask([])
        self.assertEqual(gateway.usage, [None])


class CommandChecks(unittest.TestCase):
    def test_complete_programs_run_without_credentials(self):
        folder = Path(__file__).resolve().parent
        commands = [["demo.py"], ["demo.py", "--parallel"], ["demo.py", "--case", "handoff"],
                    ["demo.py", "--case", "failure"], ["demo.py", "--case", "conflict"],
                    ["demo.py", "--case", "missing"], ["evaluation.py"]]
        for command in commands:
            result = subprocess.run([sys.executable, str(folder / command[0]), *command[1:]],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("SYNTHETIC-PRIVATE", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)

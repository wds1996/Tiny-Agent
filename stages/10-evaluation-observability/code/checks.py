from __future__ import annotations

import unittest
from types import SimpleNamespace

from deepseek_observability import dispatch_tool_call
from evaluation import AgentRun, EvalCase, evaluate, recall_at_k, score_case
from tracing import CapturePolicy, Trace, Tracer, format_trace


class Stage10Checks(unittest.TestCase):
    def test_capture_policy_hashes_content_by_default(self) -> None:
        safe = CapturePolicy(capture_content=False).sanitize({"prompt": "private text"})
        self.assertNotIn("prompt", safe)
        self.assertIn("prompt_sha256", safe)
        self.assertEqual(safe["prompt_sha256"], "66c279b1e928")
        self.assertEqual(safe["prompt_chars"], 12)

    def test_capture_policy_can_explicitly_capture_bounded_text(self) -> None:
        policy = CapturePolicy(capture_content=True, max_text_chars=4)
        self.assertEqual(policy.sanitize({"prompt": "abcdef"})["prompt"], "abcd")

    def test_span_records_status_on_success(self) -> None:
        trace = Trace("r")
        with Tracer(trace).span("tool"):
            pass
        self.assertEqual(trace.spans[0].status, "ok")

    def test_span_records_error_and_reraises(self) -> None:
        trace = Trace("r")
        with self.assertRaises(RuntimeError):
            with Tracer(trace).span("tool"):
                raise RuntimeError("boom")
        self.assertEqual(trace.spans[0].status, "error")
        self.assertEqual(trace.spans[0].attributes["error_type"], "RuntimeError")

    def test_nested_spans_keep_their_parent_child_relationship(self) -> None:
        trace = Trace("run")
        tracer = Tracer(trace)
        with tracer.span("agent.run"):
            with tracer.span("tool.lookup_order"):
                pass
        root = next(span for span in trace.spans if span.name == "agent.run")
        child = next(span for span in trace.spans if span.name == "tool.lookup_order")
        self.assertEqual(child.parent_span_id, root.span_id)
        self.assertIn("└── agent.run [ok]", format_trace(trace))
        self.assertIn("└── tool.lookup_order [ok]", format_trace(trace))

    def test_case_scores_answer_and_trajectory_separately(self) -> None:
        case = EvalCase("c", "q", ("yes",), ("lookup",))
        score = score_case(case, AgentRun("yes", ("wrong",)))
        self.assertTrue(score.answer_ok)
        self.assertFalse(score.tool_trajectory_ok)
        self.assertFalse(score.passed)

    def test_abstention_is_part_of_expected_behavior(self) -> None:
        case = EvalCase("c", "q", ("not enough",), (), should_abstain=True)
        score = score_case(case, AgentRun("not enough", (), abstained=False))
        self.assertFalse(score.abstention_ok)

    def test_eval_reports_unnecessary_tools(self) -> None:
        report = evaluate(
            [EvalCase("c", "hello", ("hello",), ())],
            lambda case: AgentRun(
                "hello", ("lookup",), latency_ms=10, estimated_cost_usd=0.25
            ),
        )
        self.assertEqual(report.unnecessary_tool_rate, 1.0)
        self.assertEqual(report.average_tool_calls, 1.0)
        self.assertEqual(report.average_latency_ms, 10)
        self.assertEqual(report.average_estimated_cost_usd, 0.25)

    def test_deepseek_tool_adapter_records_a_tool_span(self) -> None:
        trace = Trace("live-test")
        call = SimpleNamespace(
            function=SimpleNamespace(
                name="search_refund_policy",
                arguments="{}",
            )
        )
        name, content, source_id = dispatch_tool_call(call, tracer=Tracer(trace))

        self.assertEqual(name, "search_refund_policy")
        self.assertIn('"ok": true', content)
        self.assertEqual(source_id, "refund-policy")
        self.assertEqual(trace.spans[0].name, "tool.search_refund_policy")

    def test_recall_at_k_measures_retrieval_component(self) -> None:
        self.assertEqual(recall_at_k(["a", "b", "c"], {"b", "x"}, k=2), 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)

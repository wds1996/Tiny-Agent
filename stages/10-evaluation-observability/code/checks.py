from __future__ import annotations

import unittest

from evaluation import AgentRun, EvalCase, evaluate, recall_at_k, score_case
from tracing import CapturePolicy, Trace, Tracer


class Stage10Checks(unittest.TestCase):
    def test_capture_policy_hashes_content_by_default(self) -> None:
        safe = CapturePolicy(capture_content=False).sanitize({"prompt": "private text"})
        self.assertNotIn("prompt", safe)
        self.assertIn("prompt_sha256", safe)
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
            lambda case: AgentRun("hello", ("lookup",), latency_ms=10),
        )
        self.assertEqual(report.unnecessary_tool_rate, 1.0)
        self.assertEqual(report.average_latency_ms, 10)

    def test_recall_at_k_measures_retrieval_component(self) -> None:
        self.assertEqual(recall_at_k(["a", "b", "c"], {"b", "x"}, k=2), 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)

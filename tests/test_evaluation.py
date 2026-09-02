import math

import pytest

from tiny_agent import (
    EvalExample,
    EvalScore,
    EvaluationSuite,
    ExactMatchEvaluator,
    LLMJudgeEvaluator,
    MetricGateRule,
    RegressionGate,
    RunArtifact,
    RunMetricsEvaluator,
    ToolArgumentsEvaluator,
    ToolInvocation,
    ToolSelectionEvaluator,
    TrajectoryEvaluator,
)


def _score_map(scores):
    return {score.key: score.score for score in scores}


def test_tool_selection_reports_precision_recall_and_f1_separately():
    example = EvalExample(
        "tool-choice",
        {"question": "weather"},
        expected_tools=("search", "weather"),
    )
    run = RunArtifact(
        output="sunny",
        tool_calls=(
            ToolInvocation("weather", {"city": "Tokyo"}),
            ToolInvocation("calculator", {"x": 1}),
        ),
    )

    scores = _score_map(ToolSelectionEvaluator().evaluate(example, run))
    assert scores["tool_precision"] == 0.5
    assert scores["tool_recall"] == 0.5
    assert scores["tool_f1"] == 0.5


def test_tool_arguments_evaluator_compares_name_and_arguments():
    example = EvalExample(
        "args",
        {"question": "weather"},
        reference_tool_calls=(
            ToolInvocation("weather", {"city": "Tokyo"}),
        ),
    )
    correct = RunArtifact(
        output="sunny",
        tool_calls=(ToolInvocation("weather", {"city": "Tokyo"}),),
    )
    wrong = RunArtifact(
        output="sunny",
        tool_calls=(ToolInvocation("weather", {"city": "Osaka"}),),
    )

    assert ToolArgumentsEvaluator().evaluate(example, correct)[0].score == 1.0
    assert ToolArgumentsEvaluator().evaluate(example, wrong)[0].score == 0.0


def test_trajectory_scores_sequence_and_safety_independently():
    example = EvalExample(
        "trajectory",
        {"task": "research and summarize"},
        required_tool_sequence=("search", "read"),
        forbidden_tools=("delete",),
        max_tool_calls=3,
    )
    run = RunArtifact(
        output="correct final answer",
        tool_calls=(
            ToolInvocation("search"),
            ToolInvocation("delete"),
            ToolInvocation("read"),
        ),
    )

    scores = _score_map(TrajectoryEvaluator().evaluate(example, run))
    assert scores["trajectory_sequence_recall"] == 1.0
    assert scores["trajectory_policy_ok"] == 0.0


def test_evaluation_suite_aggregates_repetitions_and_tracks_metric_coverage():
    dataset = [EvalExample("one", {"x": 1}, reference_output=2)]
    calls = 0

    def target(inputs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated crash")
        return RunArtifact(output=inputs["x"] + 1)

    report = EvaluationSuite([ExactMatchEvaluator()]).run(
        dataset,
        target,
        repetitions=2,
    )

    assert report.metric("execution_success") == 0.5
    assert report.metric("exact_match") == 1.0
    assert report.coverage("exact_match") == 0.5


def test_regression_gate_rejects_partial_metric_coverage():
    dataset = [EvalExample("one", {"x": 1}, reference_output=2)]
    calls = 0

    def target(_inputs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated crash")
        return RunArtifact(output=2)

    report = EvaluationSuite([ExactMatchEvaluator("quality")]).run(
        dataset,
        target,
        repetitions=2,
    )
    gate = RegressionGate([MetricGateRule("quality", absolute_limit=0.9)])
    result = gate.check(report)

    assert result.passed is False
    assert "coverage" in result.failures[0]


def test_regression_gate_handles_higher_and_lower_is_better_metrics():
    dataset = [EvalExample("one", {"x": 1}, reference_output=2)]

    baseline = EvaluationSuite(
        [ExactMatchEvaluator("quality"), RunMetricsEvaluator("latency_ms")]
    ).run(
        dataset,
        lambda _inputs: RunArtifact(output=2, metrics={"latency_ms": 100.0}),
    )
    candidate = EvaluationSuite(
        [ExactMatchEvaluator("quality"), RunMetricsEvaluator("latency_ms")]
    ).run(
        dataset,
        lambda _inputs: RunArtifact(output=2, metrics={"latency_ms": 140.0}),
    )

    gate = RegressionGate(
        [
            MetricGateRule("quality", direction="higher", absolute_limit=1.0),
            MetricGateRule(
                "latency_ms",
                direction="lower",
                absolute_limit=150.0,
                max_regression=20.0,
            ),
        ]
    )
    result = gate.check(candidate, baseline=baseline)
    assert result.passed is False
    assert any("regression" in failure for failure in result.failures)


def test_llm_judge_boundary_validates_score_shape():
    class FakeJudge:
        def judge(self, **_kwargs):
            return {"score": 0.8, "comment": "Mostly correct."}

    evaluator = LLMJudgeEvaluator(
        key="helpfulness",
        rubric="Score whether the answer is useful.",
        judge_model=FakeJudge(),
    )
    score = evaluator.evaluate(
        EvalExample("judge", {"q": "x"}),
        RunArtifact(output="answer"),
    )[0]
    assert score.score == 0.8


def test_llm_judge_rejects_out_of_range_or_nonfinite_score():
    class BadJudge:
        def __init__(self, score):
            self.score = score

        def judge(self, **_kwargs):
            return {"score": self.score}

    for invalid in (4.2, float("nan"), float("inf")):
        evaluator = LLMJudgeEvaluator(
            key="quality",
            rubric="0 to 1 only",
            judge_model=BadJudge(invalid),
        )
        with pytest.raises(ValueError):
            evaluator.evaluate(
                EvalExample("bad", {"q": "x"}),
                RunArtifact(output="x"),
            )


def test_evaluation_models_reject_nonfinite_numbers_and_noninteger_attempts():
    with pytest.raises(ValueError, match="finite"):
        EvalScore("bad", float("nan"))

    with pytest.raises(ValueError, match="finite"):
        RunArtifact(output="x", metrics={"latency_ms": float("inf")})

    with pytest.raises(TypeError, match="integer"):
        ToolInvocation("search", attempts=1.5)

    with pytest.raises(ValueError, match="finite"):
        MetricGateRule("quality", absolute_limit=math.nan)

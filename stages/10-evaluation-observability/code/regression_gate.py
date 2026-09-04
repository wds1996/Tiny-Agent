"""Stage 10 example 8: turn evaluation metrics into an explicit regression gate."""

from tiny_agent import (
    EvalExample,
    EvaluationSuite,
    ExactMatchEvaluator,
    MetricGateRule,
    RegressionGate,
    RunArtifact,
    RunMetricsEvaluator,
)


dataset = [EvalExample("math", {"x": 1}, reference_output=2)]
suite = EvaluationSuite([ExactMatchEvaluator("quality"), RunMetricsEvaluator("latency_ms")])

baseline = suite.run(
    dataset,
    lambda inputs: RunArtifact(output=inputs["x"] + 1, metrics={"latency_ms": 100.0}),
)
candidate = suite.run(
    dataset,
    lambda inputs: RunArtifact(output=inputs["x"] + 1, metrics={"latency_ms": 135.0}),
)

gate = RegressionGate(
    [
        MetricGateRule("execution_success", absolute_limit=1.0),
        MetricGateRule("quality", absolute_limit=1.0, max_regression=0.0),
        MetricGateRule(
            "latency_ms",
            direction="lower",
            absolute_limit=150.0,
            max_regression=20.0,
        ),
    ]
)
result = gate.check(candidate, baseline=baseline)

print("passed:", result.passed)
for failure in result.failures:
    print("-", failure)

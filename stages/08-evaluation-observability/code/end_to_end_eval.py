"""Stage 08 example 11: trace a target, evaluate it, and gate a regression."""

from tiny_agent import (
    EvalExample,
    EvaluationSuite,
    ExactMatchEvaluator,
    InMemorySpanSink,
    LocalTracer,
    MetricGateRule,
    RegressionGate,
    RunArtifact,
    ToolInvocation,
    ToolSelectionEvaluator,
    TrajectoryEvaluator,
    trace_roots,
)


dataset = [
    EvalExample(
        id="calc-42",
        inputs={"expression": "20 + 22"},
        reference_output="42",
        expected_tools=("calculator",),
        required_tool_sequence=("calculator",),
        forbidden_tools=("shell",),
        max_tool_calls=1,
    )
]


def tiny_addition_calculator(expression: str) -> int:
    """Deliberately tiny parser for the fixed teaching example; no eval/exec."""

    parts = expression.split()
    if len(parts) != 3 or parts[1] != "+":
        raise ValueError("demo calculator only supports '<int> + <int>'")
    return int(parts[0]) + int(parts[2])


def target(inputs):
    sink = InMemorySpanSink()
    tracer = LocalTracer(sink)
    with tracer.span("invoke_agent", kind="agent"):
        with tracer.span(
            "execute_tool calculator",
            kind="tool",
            attributes={"tool.name": "calculator"},
        ):
            output = str(tiny_addition_calculator(inputs["expression"]))

    roots = trace_roots(sink.spans)
    if len(roots) != 1:
        raise RuntimeError("demo expected exactly one root span")

    return RunArtifact(
        output=output,
        spans=sink.spans,
        tool_calls=(ToolInvocation("calculator", {"expression": inputs["expression"]}),),
        # End-to-end latency is the root wall-clock duration. Summing nested
        # spans would double-count time because the parent already contains the child.
        metrics={"latency_ms": roots[0].duration_ms},
    )


suite = EvaluationSuite(
    [
        ExactMatchEvaluator(),
        ToolSelectionEvaluator(),
        TrajectoryEvaluator(),
    ]
)
report = suite.run(dataset, target)

print("Mean scores:")
for key, value in report.mean_scores.items():
    print(f"  {key}: {value:.3f} (coverage={report.coverage(key):.2f})")

gate = RegressionGate(
    [
        MetricGateRule("execution_success", absolute_limit=1.0),
        MetricGateRule("exact_match", absolute_limit=1.0),
        MetricGateRule("trajectory_policy_ok", absolute_limit=1.0),
    ]
)
print("Gate passed:", gate.check(report).passed)

"""Stage 08 example 5: score Tool selection and arguments as different dimensions."""

from tiny_agent import (
    EvalExample,
    RunArtifact,
    ToolArgumentsEvaluator,
    ToolInvocation,
    ToolSelectionEvaluator,
)


example = EvalExample(
    id="weather-tokyo",
    inputs={"question": "Weather in Tokyo?"},
    expected_tools=("weather",),
    reference_tool_calls=(ToolInvocation("weather", {"city": "Tokyo"}),),
)

run = RunArtifact(
    output="Sunny.",
    tool_calls=(ToolInvocation("weather", {"city": "Osaka"}),),
)

print("Selection scores:")
for score in ToolSelectionEvaluator().evaluate(example, run):
    print(f"  {score.key}: {score.score:.2f}")

print("Argument score:")
for score in ToolArgumentsEvaluator().evaluate(example, run):
    print(f"  {score.key}: {score.score:.2f}")

print("\nThe Agent selected the right Tool but the wrong city.")

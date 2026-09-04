"""Stage 10 example 4: an evaluation dataset is executable specification, not a prompt pile."""

from tiny_agent import EvalExample, ToolInvocation


dataset = [
    EvalExample(
        id="calculator-001",
        inputs={"question": "What is 20 + 22?"},
        reference_output="42",
        expected_tools=("calculator",),
        reference_tool_calls=(
            ToolInvocation("calculator", {"expression": "20 + 22"}),
        ),
        required_tool_sequence=("calculator",),
        forbidden_tools=("send_email",),
        max_tool_calls=1,
        metadata={"split": "regression", "risk": "low"},
    ),
    EvalExample(
        id="greeting-001",
        inputs={"question": "Say hello."},
        reference_output="Hello!",
        expected_tools=(),
        max_tool_calls=0,
        metadata={"split": "smoke"},
    ),
]

for example in dataset:
    print(example.id)
    print("  expected tools :", example.expected_tools)
    print("  max tool calls :", example.max_tool_calls)
    print("  metadata       :", dict(example.metadata))

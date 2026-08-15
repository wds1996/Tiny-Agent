"""Stage 03 example 5: selected LangChain abstractions used around LangGraph.

This is intentionally *not* a full LangChain Agent. It shows the reusable
components that map to concepts Tiny-Agent already implemented manually.

Run:

    pip install -e ".[stage03]"
    python stages/03-stateful-orchestration/code/langchain_component_examples.py
"""

from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import tool


@tool
def multiply(a: int, b: int) -> int:
    """Multiply two integers exactly."""
    return a * b


if __name__ == "__main__":
    messages = [
        HumanMessage(content="What is 6 * 7?"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_mul",
                    "name": "multiply",
                    "args": {"a": 6, "b": 7},
                }
            ],
        ),
        ToolMessage(content="42", tool_call_id="call_mul"),
    ]

    print("LangChain messages:")
    for message in messages:
        print(type(message).__name__, message.content)

    print("\nTool call correlation:")
    print(messages[-1].tool_call_id)

    print("\nTool name:")
    print(multiply.name)

    print("\nTool description:")
    print(multiply.description)

    print("\nTool input schema:")
    print(multiply.args_schema.model_json_schema())

    print("\nTool invocation:")
    print(multiply.invoke({"a": 6, "b": 7}))

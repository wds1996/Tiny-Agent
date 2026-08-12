"""Real Stage 01 example: Tiny-Agent + OpenAI Responses API.

Run from the repository root after installing the optional provider dependency:

    pip install -e ".[openai]"
    export OPENAI_API_KEY="..."
    python stages/01-react-runtime/code/openai_multi_tool_agent.py

The runtime is provider-neutral. Only ``OpenAIResponsesModel`` knows OpenAI's
request/response protocol.
"""

from tiny_agent import AgentRuntime, Tool, ToolRegistry
from tiny_agent.models import OpenAIResponsesModel


def multiply(a: float, b: float) -> float:
    return a * b


def add(a: float, b: float) -> float:
    return a + b


NUMBER_PAIR_SCHEMA = {
    "type": "object",
    "properties": {
        "a": {"type": "number", "description": "The first number."},
        "b": {"type": "number", "description": "The second number."},
    },
    "required": ["a", "b"],
    "additionalProperties": False,
}


tools = ToolRegistry(
    [
        Tool(
            name="multiply",
            description=(
                "Multiply two numbers. Use this tool instead of doing the "
                "multiplication mentally when an exact arithmetic result is needed."
            ),
            parameters=NUMBER_PAIR_SCHEMA,
            handler=multiply,
        ),
        Tool(
            name="add",
            description=(
                "Add two numbers. Use this tool when an exact arithmetic sum is needed."
            ),
            parameters=NUMBER_PAIR_SCHEMA,
            handler=add,
        ),
    ]
)


model = OpenAIResponsesModel(
    # Luna keeps this learning example relatively inexpensive. Swap models without
    # changing AgentRuntime.
    model="gpt-5.6-luna",
    reasoning_effort="none",
    strict_tools=True,
)

runtime = AgentRuntime(
    model=model,
    tools=tools,
    system_prompt=(
        "You are a precise arithmetic assistant. Use the provided tools for exact "
        "calculations. If a result from one tool is needed by another tool, use the "
        "observation from the first call as the next argument. Explain the final "
        "result concisely."
    ),
    max_steps=6,
)


if __name__ == "__main__":
    result = runtime.run("Calculate (23 * 17) + 41 and explain the result.")

    print("\nFinal answer")
    print("------------")
    print(result.output)

    print("\nAuditable trajectory")
    print("--------------------")
    for index, message in enumerate(result.messages, start=1):
        role = message["role"]
        if role == "assistant" and "tool_calls" in message:
            for call in message["tool_calls"]:
                print(
                    f"{index:02d}. ACTION      "
                    f"{call['name']}({call['arguments']}) [id={call['id']}]"
                )
        elif role == "tool":
            print(
                f"{index:02d}. OBSERVATION "
                f"{message['name']} -> {message['content']}"
            )
        else:
            print(f"{index:02d}. {role.upper():11s} {message.get('content', '')}")

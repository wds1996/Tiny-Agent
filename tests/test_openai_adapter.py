from types import SimpleNamespace

from tiny_agent.models.openai import OpenAIResponsesModel


class FakeResponsesAPI:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self._responses)


class FakeOpenAIClient:
    def __init__(self, responses):
        self.responses = FakeResponsesAPI(responses)


def test_adapter_normalizes_function_call_and_request_schema():
    provider_response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="call_123",
                name="multiply",
                arguments='{"a": 23, "b": 17}',
            )
        ],
        output_text="",
    )
    client = FakeOpenAIClient([provider_response])
    model = OpenAIResponsesModel(client=client)

    messages = [
        {"role": "system", "content": "Use tools when needed."},
        {"role": "user", "content": "Calculate 23 * 17."},
    ]
    tools = [
        {
            "name": "multiply",
            "description": "Multiply two numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        }
    ]

    result = model.generate(messages, tools)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_123"
    assert result.tool_calls[0].name == "multiply"
    assert result.tool_calls[0].arguments == {"a": 23, "b": 17}

    request = client.responses.calls[0]
    assert request["model"] == "gpt-5.6-luna"
    assert request["reasoning"] == {"effort": "none"}
    assert request["parallel_tool_calls"] is True
    assert request["tools"][0]["type"] == "function"
    assert request["tools"][0]["strict"] is True


def test_adapter_converts_runtime_tool_history_to_responses_items():
    provider_response = SimpleNamespace(output=[], output_text="432")
    client = FakeOpenAIClient([provider_response])
    model = OpenAIResponsesModel(client=client)

    messages = [
        {"role": "system", "content": "Use tools when useful."},
        {"role": "user", "content": "Calculate (23 * 17) + 41."},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_mul",
                    "name": "multiply",
                    "arguments": {"a": 23, "b": 17},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_mul",
            "name": "multiply",
            "content": "391",
        },
    ]

    result = model.generate(messages, tools=[])

    assert result.final_answer == "432"
    provider_input = client.responses.calls[0]["input"]
    assert provider_input[2] == {
        "type": "function_call",
        "call_id": "call_mul",
        "name": "multiply",
        "arguments": '{"a": 23, "b": 17}',
    }
    assert provider_input[3] == {
        "type": "function_call_output",
        "call_id": "call_mul",
        "output": "391",
    }


def test_adapter_supports_multiple_function_calls_in_one_turn():
    provider_response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="call_a",
                name="lookup_a",
                arguments='{"query": "alpha"}',
            ),
            SimpleNamespace(
                type="function_call",
                call_id="call_b",
                name="lookup_b",
                arguments='{"query": "beta"}',
            ),
        ],
        output_text="",
    )
    model = OpenAIResponsesModel(client=FakeOpenAIClient([provider_response]))

    result = model.generate([{"role": "user", "content": "Compare A and B"}], [])

    assert [call.name for call in result.tool_calls] == ["lookup_a", "lookup_b"]
    assert [call.id for call in result.tool_calls] == ["call_a", "call_b"]

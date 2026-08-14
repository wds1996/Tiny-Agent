from types import SimpleNamespace

import pytest

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


def test_adapter_returns_final_text_when_no_function_call_exists():
    response = SimpleNamespace(output=[], output_text="A direct answer.")
    model = OpenAIResponsesModel(client=FakeOpenAIClient([response]))

    result = model.generate(
        [{"role": "user", "content": "Answer directly."}],
        tools=[],
    )

    assert result.final_answer == "A direct answer."
    assert result.tool_calls == []


def test_adapter_rejects_invalid_json_function_arguments():
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="call_bad_json",
                name="lookup",
                arguments="not-json",
            )
        ],
        output_text="",
    )
    model = OpenAIResponsesModel(client=FakeOpenAIClient([response]))

    with pytest.raises(RuntimeError, match="invalid JSON arguments"):
        model.generate([{"role": "user", "content": "Look this up."}], tools=[])


def test_adapter_rejects_non_object_function_arguments():
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="call_list",
                name="lookup",
                arguments='["alpha"]',
            )
        ],
        output_text="",
    )
    model = OpenAIResponsesModel(client=FakeOpenAIClient([response]))

    with pytest.raises(RuntimeError, match="must decode to a JSON object"):
        model.generate([{"role": "user", "content": "Look this up."}], tools=[])


def test_adapter_prioritizes_tool_calls_over_incidental_text_in_stage_01_contract():
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="call_1",
                name="lookup",
                arguments='{"query": "alpha"}',
            )
        ],
        output_text="I will check that first.",
    )
    model = OpenAIResponsesModel(client=FakeOpenAIClient([response]))

    result = model.generate([{"role": "user", "content": "Check alpha."}], tools=[])

    assert [call.name for call in result.tool_calls] == ["lookup"]
    assert result.final_answer is None


def test_adapter_rejects_unsupported_internal_message_role():
    response = SimpleNamespace(output=[], output_text="unused")
    model = OpenAIResponsesModel(client=FakeOpenAIClient([response]))

    with pytest.raises(ValueError, match="Unsupported Tiny-Agent message role"):
        model.generate([{"role": "mystery", "content": "hello"}], tools=[])

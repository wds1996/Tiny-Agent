from types import SimpleNamespace

import pytest

from tiny_agent.models.openai_structured import OpenAIStructuredDecisionModel


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


def test_structured_decision_uses_json_schema_and_parses_object():
    response = SimpleNamespace(
        output_text='{"route":"technical","reason":"The request reports an error."}'
    )
    client = FakeOpenAIClient([response])
    model = OpenAIStructuredDecisionModel(client=client)
    schema = {
        "type": "object",
        "properties": {
            "route": {"type": "string", "enum": ["technical", "general"]},
            "reason": {"type": "string"},
        },
        "required": ["route", "reason"],
        "additionalProperties": False,
    }

    result = model.decide(
        prompt="The app crashes on startup.",
        instructions="Choose one route.",
        schema_name="route_decision",
        schema=schema,
    )

    assert result == {
        "route": "technical",
        "reason": "The request reports an error.",
    }
    request = client.responses.calls[0]
    assert request["model"] == "gpt-5.6-luna"
    assert request["reasoning"] == {"effort": "none"}
    assert request["instructions"] == "Choose one route."
    assert request["text"]["format"] == {
        "type": "json_schema",
        "name": "route_decision",
        "schema": schema,
        "strict": True,
    }


def test_structured_decision_rejects_invalid_json():
    model = OpenAIStructuredDecisionModel(
        client=FakeOpenAIClient([SimpleNamespace(output_text="not-json")])
    )

    with pytest.raises(RuntimeError, match="not valid JSON"):
        model.decide(
            prompt="route me",
            schema_name="decision",
            schema={"type": "object"},
        )


def test_structured_decision_rejects_non_object_output():
    model = OpenAIStructuredDecisionModel(
        client=FakeOpenAIClient([SimpleNamespace(output_text='["a"]')])
    )

    with pytest.raises(RuntimeError, match="must decode to a JSON object"):
        model.decide(
            prompt="route me",
            schema_name="decision",
            schema={"type": "object"},
        )

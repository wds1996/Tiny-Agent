from types import SimpleNamespace

import pytest

from tiny_agent.models.openai_structured import (
    OpenAIStructuredDecisionModel,
    StructuredDecisionIncomplete,
    StructuredDecisionRefusal,
)


class FakeResponsesAPI:
    def __init__(self, responses):
        self._responses = iter(responses)

    def create(self, **kwargs):
        return next(self._responses)


class FakeOpenAIClient:
    def __init__(self, responses):
        self.responses = FakeResponsesAPI(responses)


def test_structured_decision_reports_refusal_as_first_class_outcome():
    response = SimpleNamespace(
        status="completed",
        output=[
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(
                        type="refusal",
                        refusal="I cannot make this requested decision.",
                    )
                ],
            )
        ],
        output_text="",
    )
    model = OpenAIStructuredDecisionModel(client=FakeOpenAIClient([response]))

    with pytest.raises(
        StructuredDecisionRefusal,
        match="cannot make this requested decision",
    ):
        model.decide(
            prompt="decide",
            schema_name="decision",
            schema={"type": "object"},
        )


def test_structured_decision_reports_incomplete_response_separately():
    response = SimpleNamespace(
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        output=[],
        output_text="",
    )
    model = OpenAIStructuredDecisionModel(client=FakeOpenAIClient([response]))

    with pytest.raises(
        StructuredDecisionIncomplete,
        match="max_output_tokens",
    ):
        model.decide(
            prompt="decide",
            schema_name="decision",
            schema={"type": "object"},
        )

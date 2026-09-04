import pytest
from pydantic import BaseModel, ConfigDict, ValidationError
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_none

from tiny_agent import ToolInputError, TransientToolError
from tiny_agent.validators.jsonschema import JsonSchemaToolArgumentsValidator


def test_jsonschema_adapter_handles_schema_features_beyond_teaching_subset():
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "target": {
                "oneOf": [
                    {"type": "string", "pattern": "^doc-"},
                    {"type": "integer", "minimum": 1},
                ]
            }
        },
        "required": ["target"],
        "additionalProperties": False,
    }
    validator = JsonSchemaToolArgumentsValidator()

    validator.validate(schema, {"target": "doc-7"})
    with pytest.raises(ToolInputError):
        validator.validate(schema, {"target": "wrong-prefix"})


def test_tenacity_can_express_bounded_retry_predicate_without_retrying_fatal_errors():
    calls = 0

    def flaky():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TransientToolError("temporary")
        return "ok"

    retryer = Retrying(
        stop=stop_after_attempt(2),
        wait=wait_none(),
        retry=retry_if_exception_type(TransientToolError),
        reraise=True,
    )

    assert retryer(flaky) == "ok"
    assert calls == 2


def test_pydantic_strict_mode_rejects_type_coercion_at_application_boundary():
    class TransferArgs(BaseModel):
        model_config = ConfigDict(strict=True, extra="forbid")
        amount: int
        currency: str

    assert TransferArgs.model_validate({"amount": 10, "currency": "USD"}).amount == 10

    with pytest.raises(ValidationError):
        TransferArgs.model_validate({"amount": "10", "currency": "USD"})
    with pytest.raises(ValidationError):
        TransferArgs.model_validate(
            {"amount": 10, "currency": "USD", "surprise": "extra"}
        )

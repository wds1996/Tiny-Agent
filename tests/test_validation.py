import pytest

from tiny_agent import SimpleToolArgumentsValidator, ToolInputError


SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "minLength": 1},
        "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
        "filters": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}


def test_simple_validator_accepts_supported_valid_schema_subset():
    SimpleToolArgumentsValidator().validate(
        SCHEMA,
        {"query": "agent safety", "top_k": 3, "filters": ["docs"]},
    )


def test_simple_validator_rejects_missing_required_argument():
    with pytest.raises(ToolInputError, match="Missing required argument"):
        SimpleToolArgumentsValidator().validate(SCHEMA, {"top_k": 3})


def test_simple_validator_rejects_wrong_integer_type_including_bool():
    with pytest.raises(ToolInputError, match="integer"):
        SimpleToolArgumentsValidator().validate(
            SCHEMA,
            {"query": "agent", "top_k": True},
        )


def test_simple_validator_rejects_additional_properties():
    with pytest.raises(ToolInputError, match="Unexpected argument"):
        SimpleToolArgumentsValidator().validate(
            SCHEMA,
            {"query": "agent", "surprise": "do not pass"},
        )


def test_simple_validator_checks_nested_array_items():
    with pytest.raises(ToolInputError, match="string"):
        SimpleToolArgumentsValidator().validate(
            SCHEMA,
            {"query": "agent", "filters": [123]},
        )


def test_invalid_application_schema_is_not_misreported_as_model_input_error():
    malformed = {
        "type": "object",
        "properties": [],
        "required": ["query"],
    }

    with pytest.raises(ValueError, match="properties"):
        SimpleToolArgumentsValidator().validate(malformed, {"query": "agent"})


def test_unsupported_schema_feature_fails_closed_in_teaching_validator():
    unsupported = {
        "type": ["string", "null"],
    }

    with pytest.raises(ValueError, match="single string JSON type"):
        SimpleToolArgumentsValidator().validate(
            {"type": "object", "properties": {"value": unsupported}},
            {"value": "ok"},
        )

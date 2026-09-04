"""Stage 09 example 2: local validation before a model-proposed tool call executes."""

from pydantic import BaseModel, ConfigDict, ValidationError

from tiny_agent import SimpleToolArgumentsValidator, ToolInputError
from tiny_agent.validators.jsonschema import JsonSchemaToolArgumentsValidator


schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "query": {"type": "string", "minLength": 1},
        "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
    },
    "required": ["query", "top_k"],
    "additionalProperties": False,
}

simple = SimpleToolArgumentsValidator()
full = JsonSchemaToolArgumentsValidator()

simple.validate(schema, {"query": "agent safety", "top_k": 3})
full.validate(schema, {"query": "agent safety", "top_k": 3})
print("Valid dynamic tool arguments accepted.")

try:
    full.validate(schema, {"query": "agent safety", "top_k": 999})
except ToolInputError as exc:
    print("Invalid dynamic tool arguments blocked:", exc)


class TransferArgs(BaseModel):
    """Application-owned typed boundary: strict means no surprising coercion."""

    model_config = ConfigDict(strict=True, extra="forbid")
    amount: int
    currency: str


try:
    TransferArgs.model_validate({"amount": "100", "currency": "USD"})
except ValidationError:
    print('Strict Pydantic rejected amount="100" instead of silently coercing it.')

# Dynamic JSON Tool schema -> JSON Schema validator
# Stable application model   -> Pydantic strict model

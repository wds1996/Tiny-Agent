from __future__ import annotations

from typing import Any, Protocol

from .reliability import ToolInputError


class ToolArgumentsValidator(Protocol):
    def validate(self, schema: dict[str, Any], arguments: dict[str, Any]) -> None:
        """Raise ToolInputError when arguments do not satisfy a valid schema."""


class SimpleToolArgumentsValidator:
    """Small educational validator for a useful JSON-Schema subset.

    Supported keywords:

    - type
    - properties / required / additionalProperties (boolean only)
    - enum
    - minimum / maximum
    - minLength / maxLength
    - minItems / maxItems / items

    It is deliberately *not* a full JSON Schema implementation. Invalid or
    unsupported application-owned schema shapes raise ``ValueError``; model
    arguments that fail a valid supported schema raise ``ToolInputError``.
    Stage 07 also provides a ``jsonschema`` adapter for complete schema work.
    """

    def validate(self, schema: dict[str, Any], arguments: dict[str, Any]) -> None:
        if not isinstance(schema, dict):
            raise ValueError("Tool schema must be an object")
        if not isinstance(arguments, dict):
            raise ToolInputError("Tool arguments must be an object.")
        self._validate_value(arguments, schema, path="$arguments")

    def _validate_value(self, value: Any, schema: dict[str, Any], *, path: str) -> None:
        expected_type = schema.get("type")
        if expected_type is not None:
            if not isinstance(expected_type, str):
                raise ValueError("Simple validator supports only a single string JSON type")
            if not self._matches_type(value, expected_type):
                raise ToolInputError(f"{path} must be of JSON type {expected_type!r}.")

        if "enum" in schema:
            enum = schema["enum"]
            if not isinstance(enum, list) or not enum:
                raise ValueError("Tool schema enum must be a non-empty array")
            if value not in enum:
                raise ToolInputError(f"{path} must be one of the allowed enum values.")

        if isinstance(value, dict):
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            if not isinstance(properties, dict):
                raise ValueError("Tool schema properties must be an object")
            if not isinstance(required, list) or any(
                not isinstance(key, str) for key in required
            ):
                raise ValueError("Tool schema required must be an array of strings")

            for key in required:
                if key not in value:
                    raise ToolInputError(f"Missing required argument: {key}.")

            additional = schema.get("additionalProperties", True)
            if not isinstance(additional, bool):
                raise ValueError(
                    "Simple validator supports only boolean additionalProperties"
                )
            if additional is False:
                unknown = sorted(set(value) - set(properties))
                if unknown:
                    raise ToolInputError(
                        f"Unexpected argument(s): {', '.join(unknown)}."
                    )

            for key, child_schema in properties.items():
                if not isinstance(child_schema, dict):
                    raise ValueError("Tool property schema must be an object")
                if key in value:
                    self._validate_value(value[key], child_schema, path=f"{path}.{key}")

        if isinstance(value, list):
            min_items = schema.get("minItems")
            max_items = schema.get("maxItems")
            if min_items is not None and len(value) < min_items:
                raise ToolInputError(f"{path} contains too few items.")
            if max_items is not None and len(value) > max_items:
                raise ToolInputError(f"{path} contains too many items.")
            item_schema = schema.get("items")
            if item_schema is not None and not isinstance(item_schema, dict):
                raise ValueError("Simple validator items must be an object")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    self._validate_value(item, item_schema, path=f"{path}[{index}]")

        if isinstance(value, str):
            min_length = schema.get("minLength")
            max_length = schema.get("maxLength")
            if min_length is not None and len(value) < min_length:
                raise ToolInputError(f"{path} is shorter than the minimum length.")
            if max_length is not None and len(value) > max_length:
                raise ToolInputError(f"{path} is longer than the maximum length.")

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum = schema.get("minimum")
            maximum = schema.get("maximum")
            if minimum is not None and value < minimum:
                raise ToolInputError(f"{path} is below the allowed minimum.")
            if maximum is not None and value > maximum:
                raise ToolInputError(f"{path} is above the allowed maximum.")

    @staticmethod
    def _matches_type(value: Any, expected: str) -> bool:
        checks = {
            "object": lambda item: isinstance(item, dict),
            "array": lambda item: isinstance(item, list),
            "string": lambda item: isinstance(item, str),
            "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
            "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
            "boolean": lambda item: isinstance(item, bool),
            "null": lambda item: item is None,
        }
        checker = checks.get(expected)
        if checker is None:
            raise ValueError(
                f"Simple validator does not support JSON type {expected!r}"
            )
        return checker(value)

"""Full JSON Schema adapter for Stage 09.

This module intentionally depends on the optional ``stage09`` extra so earlier
learning stages keep a lightweight base installation.
"""

from __future__ import annotations

from typing import Any

from jsonschema.validators import validator_for

from ..reliability import ToolInputError


class JsonSchemaToolArgumentsValidator:
    """Validate dynamic Tool JSON Schema with the maintained jsonschema package."""

    def __init__(self, *, check_formats: bool = False) -> None:
        self.check_formats = check_formats

    def validate(self, schema: dict[str, Any], arguments: dict[str, Any]) -> None:
        validator_cls = validator_for(schema)
        try:
            validator_cls.check_schema(schema)
        except Exception as exc:
            # Invalid application-owned schemas are configuration failures. The
            # raw library error is chained for developers, not exposed as a
            # model observation.
            raise ValueError("Tool JSON Schema is invalid.") from exc

        kwargs: dict[str, Any] = {}
        if self.check_formats:
            kwargs["format_checker"] = validator_cls.FORMAT_CHECKER
        validator = validator_cls(schema, **kwargs)

        errors = sorted(validator.iter_errors(arguments), key=lambda err: list(err.path))
        if not errors:
            return

        first = errors[0]
        path = ".".join(str(part) for part in first.path)
        location = f" at {path}" if path else ""
        raise ToolInputError(f"Tool arguments failed JSON Schema validation{location}.")

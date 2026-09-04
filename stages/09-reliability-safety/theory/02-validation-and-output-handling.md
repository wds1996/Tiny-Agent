# 02 — Validate Model Output Before It Becomes Program Input

Stage 00 introduced Function Calling and JSON Schema.

Stage 09 adds the missing production rule:

> **A schema shown to the model is not the same thing as a schema enforced by your runtime.**

The model may usually return valid arguments.

Usually is not a security boundary.

---

# 1. The dangerous shortcut

Suppose a Tool declares:

```python
parameters = {
    "type": "object",
    "properties": {
        "amount": {
            "type": "integer",
            "minimum": 1,
            "maximum": 1000,
        }
    },
    "required": ["amount"],
    "additionalProperties": False,
}
```

The model proposes:

```json
{
  "amount": -9000000,
  "admin": true
}
```

If runtime code does:

```python
tool.handler(**arguments)
```

without local validation, then the JSON Schema was mostly advice.

---

# 2. Structured Output improves generation; validation protects execution

These are complementary.

```text
Structured Output / constrained generation
    -> increase probability and guarantees around model response shape

local runtime validation
    -> independently verify data before crossing an execution boundary
```

Even when a provider promises schema-constrained output, local validation is still valuable because:

- different providers/adapters may behave differently;
- cached or replayed ToolCalls may bypass the original generation path;
- MCP/remote schemas may enter from external systems;
- application business rules may be stricter than provider schema support;
- bugs can mutate arguments after model generation;
- the same Tool may be called by code, not only an LLM.

---

# 3. Why Tiny-Agent has two validation layers

Stage 09 teaches the mechanism first:

```python
SimpleToolArgumentsValidator
```

It supports a deliberately small JSON-Schema-like subset:

- primitive types;
- object properties;
- required fields;
- `additionalProperties: false`;
- enums;
- numeric bounds;
- string lengths;
- array lengths and item schemas.

Why write a small version?

Because it makes the control flow visible:

```text
arguments
    ↓
required?
    ↓
known properties?
    ↓
types?
    ↓
bounds?
    ↓
handler
```

But it is **not** advertised as a complete JSON Schema implementation.

That disclaimer matters.

A half-implemented standard presented as complete validation is worse than a clearly labeled teaching subset.

---

# 4. Full dynamic JSON Schema: use `jsonschema`

For real dynamic Tool schemas Stage 09 adds:

```python
from tiny_agent.validators.jsonschema import (
    JsonSchemaToolArgumentsValidator,
)
```

It delegates to the maintained `jsonschema` package.

Conceptually:

```python
validator_cls = validator_for(schema)
validator_cls.check_schema(schema)
validator = validator_cls(schema)
errors = list(validator.iter_errors(arguments))
```

This matters for features such as:

```text
oneOf / anyOf
pattern
references
nested constraints
schema draft selection
```

that should not be casually reimplemented in an Agent tutorial.

---

# 5. Invalid schema vs invalid model arguments

These are different failures.

## Invalid model arguments

```text
model proposed bad data
```

Result:

```text
ToolFailure[invalid_arguments]
```

The model may be able to recover by proposing corrected arguments.

## Invalid Tool schema

```text
application developer configured an invalid schema
```

That is an application configuration bug.

Do not tell the model:

```text
"Please repair our JSON Schema implementation."
```

Stage 09's full adapter therefore treats malformed application schema as a developer error rather than a normal ToolCall failure.

---

# 6. Why `additionalProperties: false` matters

Consider:

```json
{
  "path": "report.txt",
  "delete_after_read": true
}
```

If your handler only expects `path`, extra fields might be ignored today.

Tomorrow a wrapper may start forwarding them.

Strict schema surfaces reduce accidental capability expansion.

For stable tool contracts, prefer:

```json
{
  "type": "object",
  "properties": {...},
  "required": [...],
  "additionalProperties": false
}
```

unless extensibility is intentionally part of the contract.

---

# 7. Pydantic is useful at a different boundary

Dynamic MCP/provider Tool schemas are naturally represented as JSON Schema.

Application-owned Python data often benefits from a typed model:

```python
from pydantic import BaseModel, ConfigDict

class TransferArgs(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
    )

    amount: int
    currency: str
```

Strict mode is important when silent conversion is undesirable.

Without strict validation, some systems happily turn:

```json
{"amount": "100"}
```

into:

```python
amount = 100
```

Sometimes conversion is convenient.

At a financial or permission boundary, convenience can become ambiguity.

---

# 8. Schema validation is not business authorization

A perfectly valid request can still be forbidden.

```json
{
  "environment": "production",
  "release": "v0.7.0"
}
```

may satisfy every type constraint.

But perhaps:

```text
current role = intern
```

Therefore:

```text
valid
!=
authorized
```

Stage 09 uses this order:

```text
shape validation
    ↓
permission / role / approval policy
    ↓
execution
```

---

# 9. Output handling needs the same zero-trust mindset

OWASP calls out **Improper Output Handling** because LLM-generated output may be passed into:

- shell commands;
- SQL;
- HTML/JavaScript;
- file paths;
- downstream APIs.

Function Calling does not grant permission to skip context-specific validation.

Examples:

Bad:

```python
os.system(model_text)
```

Better:

```text
model chooses from application-owned operation enum
    ↓
validated structured arguments
    ↓
specific API function
```

Bad:

```python
sql = f"SELECT * FROM users WHERE id = {model_value}"
```

Better:

```text
parameterized query + authorization
```

---

# 10. Humorous memory aid

JSON Schema shown to the model is a menu.

Runtime validation is the kitchen checking that the customer did not scribble:

```text
"One sandwich, plus ownership of the restaurant"
```

in the notes field.

---

## Code to inspect

- `src/tiny_agent/validation.py`
- `src/tiny_agent/validators/jsonschema.py`
- `code/validation_boundary.py`

Run:

```bash
python stages/09-reliability-safety/code/validation_boundary.py
```

---

## Completion check

Explain:

1. Provider schema constraints vs local validation.
2. Why Tiny-Agent's simple validator is intentionally incomplete.
3. Why mature JSON Schema support should use a maintained library.
4. `additionalProperties: false` and capability surface reduction.
5. JSON Schema vs Pydantic typed application models.
6. Strict validation vs convenient coercion.
7. Validation vs authorization.
8. Why model output should be treated like untrusted program input.

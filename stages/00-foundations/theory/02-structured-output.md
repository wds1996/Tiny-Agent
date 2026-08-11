# Structured Output

## 1. Why natural language is not enough

Language models are good at producing text, but applications often need data that software can reliably parse.

For example, this is easy for a human to understand:

```text
The user wants to book a meeting tomorrow at 3 PM with Alice.
```

But application code would rather receive:

```json
{
  "intent": "schedule_meeting",
  "date": "tomorrow",
  "time": "15:00",
  "attendees": ["Alice"]
}
```

Structured output is the bridge between probabilistic natural-language generation and deterministic software logic.

## 2. The core idea

Instead of asking a model to produce arbitrary text, the application defines the shape of the expected result.

Conceptually:

```json
{
  "type": "object",
  "properties": {
    "intent": {"type": "string"},
    "confidence": {"type": "number"}
  },
  "required": ["intent", "confidence"]
}
```

The exact provider API differs, but the engineering principle is stable:

> Make model output machine-readable at boundaries where software must make decisions.

## 3. Structured output vs prompt-only JSON

A weak approach is:

```text
Please answer in JSON.
```

The model may still produce:

```text
Sure! Here is the JSON:
{...}
```

or malformed JSON.

A schema-constrained structured-output feature is stronger because the provider or runtime actively constrains/validates the output format.

When native schema enforcement is unavailable, the application should still validate the returned object before trusting it.

## 4. Validation is part of the runtime

Suppose the desired object is:

```python
{
    "city": "Tokyo",
    "unit": "celsius"
}
```

Possible failures include:

- missing `city`;
- unsupported `unit`;
- wrong data type;
- extra unexpected fields;
- semantically invalid values.

Therefore the runtime should treat model output as **untrusted input** until validation succeeds.

This principle becomes even more important in Agent systems because structured model output may trigger real actions.

## 5. Structured output is not the same as function calling

These ideas are related but different.

### Structured output

The application wants the model's response in a particular data shape.

```text
User -> Model -> {intent, priority, summary}
```

### Function calling

The application gives the model descriptions of available actions and asks it to choose whether/how to invoke one.

```text
User -> Model -> call search(query="...")
```

A tool call is itself usually structured data, but its semantic purpose is **action selection**, not merely formatting an answer.

## 6. Where structured output appears in Agent systems

Structured output is used for more than tools.

Examples:

### Routing

```json
{
  "route": "web_search"
}
```

### Planning

```json
{
  "steps": [
    {"id": 1, "task": "search sources"},
    {"id": 2, "task": "compare evidence"}
  ]
}
```

### Evaluation

```json
{
  "passed": true,
  "score": 0.92,
  "reason": "..."
}
```

### Human approval metadata

```json
{
  "risk": "high",
  "requires_approval": true
}
```

## 7. Typed application models

As the project grows, raw dictionaries become hard to maintain.

Instead of passing arbitrary objects everywhere, applications often define typed structures:

```python
@dataclass
class ToolCall:
    name: str
    arguments: dict
```

or use a validation library such as Pydantic.

Benefits:

- explicit contracts;
- better IDE support;
- centralized validation;
- clearer tests;
- easier provider normalization.

Tiny-Agent uses normalized internal types so the runtime does not depend on a specific provider's response format.

## 8. A useful rule

Use natural language for communication with humans.

Use structured output for boundaries where software must interpret the result.

Many production Agent bugs happen because a system asks the LLM to communicate critical control information through unconstrained prose and then tries to parse it with fragile string operations.

## 9. Key takeaways

- Structured output makes probabilistic model responses easier for deterministic software to consume.
- Schema-constrained output is stronger than simply asking for JSON in a prompt.
- Model-produced structures must still be validated.
- Structured output and function calling solve different problems.
- Agent routing, planning, evaluation, and tool use all benefit from explicit structured contracts.

## Review questions

1. Why is `"Please output JSON"` weaker than schema-constrained output?
2. Why should model-produced JSON still be treated as untrusted input?
3. What is the conceptual difference between structured output and tool calling?
4. Where else besides tools would structured output be useful in an Agent runtime?

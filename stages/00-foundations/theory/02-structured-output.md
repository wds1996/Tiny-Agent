# 02 — When Software Consumes the Answer: Structured Output

> Language: English | [简体中文](02-structured-output.zh-CN.md)

The previous chapter gave us one real LLM call:

```text
Python application
    ↓
OpenAI Responses API
    ↓
model
    ↓
natural-language answer
```

If a human is the final consumer, that may be enough.

Agents, however, do more than chat. Model outputs often feed routing, planning, risk checks, extraction, evaluation, and other program logic. At that boundary, natural language becomes awkward.

So this chapter is not really about “making the model write better JSON.” It asks:

> **How do we turn probabilistic model output into a data interface that deterministic software can consume reliably?**

---

## 1. Start with a realistic failure mode

Continue the travel assistant.

The user says:

> I am going to Tokyo on October 3, 2026. My budget is about 8,000 CNY and I also want weather information.

With ordinary text generation:

```python
response = client.responses.create(
    model="gpt-5.6-luna",
    input=(
        "Extract the city, date, budget, and whether weather is needed from: "
        "I am going to Tokyo on October 3, 2026. My budget is about 8,000 CNY "
        "and I also want weather information."
    ),
)

print(response.output_text)
```

A perfectly good answer might be:

```text
The destination is Tokyo, the date is October 3, 2026, the budget is
approximately 8,000 CNY, and the user wants weather information.
```

A human understands that immediately. What should the program do next?

You might write substring checks or regular expressions. Then the model changes wording:

```text
Destination: Tokyo
Travel date: 10/03/2026
Budget: roughly RMB 8k
Weather requested: yes
```

Your parser gradually becomes a contest against natural-language variation.

The problem is not that your regex is insufficiently clever. **The boundary is wrong.**

If software needs a structured object, make the contract structured at the model boundary.

---

## 2. Why “please output JSON” is still weaker

A common improvement is:

```text
Return only JSON. No explanation. No Markdown.
```

That is better than unconstrained prose, but it remains a language instruction.

The model may still produce a preamble, rename a field, or change a type:

```json
{
  "destination": "Tokyo",
  "budget": "about eight thousand yuan"
}
```

When code depends on field names, types, and required values, we want a stronger contract.

That is the role of Structured Output.

---

## 3. Define what the program needs before thinking about the model

Suppose the application wants:

```json
{
  "city": "Tokyo",
  "travel_date": "2026-10-03",
  "budget_cny": 8000,
  "needs_weather": true
}
```

A JSON Schema can express that interface:

```python
TRIP_SCHEMA = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "travel_date": {"type": "string"},
        "budget_cny": {"type": "number"},
        "needs_weather": {"type": "boolean"},
    },
    "required": [
        "city",
        "travel_date",
        "budget_cny",
        "needs_weather",
    ],
    "additionalProperties": False,
}
```

Do not think of JSON Schema as “special LLM syntax.”

It is simply an interface contract saying:

```text
result must be an object
city must be a string
budget_cny must be a number
needs_weather must be a boolean
all fields must exist
no undeclared fields are allowed
```

That is conceptually similar to defining types at any other software boundary.

---

## 4. Complete OpenAI Structured Output example

The current Responses API can constrain text output with a JSON Schema through `text.format`.

```python
import json
from openai import OpenAI

client = OpenAI()

TRIP_SCHEMA = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "travel_date": {"type": "string"},
        "budget_cny": {"type": "number"},
        "needs_weather": {"type": "boolean"},
    },
    "required": [
        "city",
        "travel_date",
        "budget_cny",
        "needs_weather",
    ],
    "additionalProperties": False,
}

response = client.responses.create(
    model="gpt-5.6-luna",
    instructions=(
        "Extract information from the user's travel description. "
        "Normalize dates to YYYY-MM-DD. Do not invent missing facts."
    ),
    input=(
        "I am going to Tokyo on October 3, 2026. My budget is about 8,000 CNY "
        "and I also want weather information."
    ),
    text={
        "format": {
            "type": "json_schema",
            "name": "trip_request",
            "strict": True,
            "schema": TRIP_SCHEMA,
        }
    },
)

data = json.loads(response.output_text)
print(data)
print(type(data["needs_weather"]))
```

Runnable version:

[`../code/structured_output_demo.py`](../code/structured_output_demo.py)

### Expected output

```text
{'city': 'Tokyo', 'travel_date': '2026-10-03', 'budget_cny': 8000, 'needs_weather': True}
<class 'bool'>
```

Exact string choices may vary, but the output shape must satisfy the schema.

The application no longer guesses the model's formatting intent after generation. It declares the contract before generation.

---

## 5. What `text.format` is doing

The important block is:

```python
text={
    "format": {
        "type": "json_schema",
        "name": "trip_request",
        "strict": True,
        "schema": TRIP_SCHEMA,
    }
}
```

`type="json_schema"` says this is schema-constrained structured output rather than ordinary prose.

`name="trip_request"` gives the format a stable identifier.

`strict=True` requests strict adherence to the supported schema constraints.

`schema=TRIP_SCHEMA` defines the fields, types, and required shape.

Structured Output therefore primarily constrains:

```text
shape / syntax
```

It does not automatically guarantee:

```text
real-world semantic truth
```

That distinction matters enormously.

---

## 6. A valid schema can still contain a wrong answer

Imagine the model returns:

```json
{
  "city": "Osaka",
  "travel_date": "2026-10-03",
  "budget_cny": 8000,
  "needs_weather": true
}
```

The object is perfectly valid under the schema.

It is still wrong because the user said Tokyo.

So:

```text
Structured Output
    ↓
helps guarantee the result has the expected structure

but does not guarantee
    ↓
every value is factually or semantically correct
```

Traditional typed programs have the same issue:

```python
age: int = 999
```

The type is valid; the business meaning may not be.

A mature runtime can therefore have multiple layers:

```text
schema validation
    +
business-rule validation
    +
permission / safety validation
```

Stage 07 expands that idea.

---

## 7. Structured Output is about representation, not action

This is the point where learners often confuse the current chapter with the next one.

### Structured Output asks:

> In what shape should the model return a result to software?

For example:

```json
{
  "route": "weather",
  "confidence": 0.96
}
```

That is data.

### Tool Calling asks:

> Is the model proposing that the application perform an external action?

For example:

```text
get_weather(city="Tokyo")
```

That is an **action proposal**.

A useful shorthand is:

```text
Structured Output
    = structured conclusion for software

Tool Calling
    = structured action proposal for the Runtime
```

Tool calls are themselves structured, but their semantics are different.

---

## 8. Why Agents rely heavily on structured contracts

If a chatbot formats one answer badly, the UI may look odd.

Agent outputs often sit on program-control boundaries:

```text
user request
   ↓
model routing
   ↓
route = "search"
   ↓
application performs retrieval
```

or:

```text
model plan
   ↓
steps = [...]
   ↓
runtime executes the plan
```

or:

```text
model risk assessment
   ↓
risk = "high"
   ↓
application enters an approval path
```

If critical control data is hidden in free-form prose and recovered with string matching, the system becomes brittle.

The closer an output is to a **software decision boundary**, the stronger the case for an explicit contract.

---

## 9. When should you not use Structured Output?

Do not overcorrect and turn every professional system into a JSON factory.

When the intended consumer is a person—for example, an explanation, an email, a report paragraph, or a summary—natural language is often the right format.

A useful question is:

> **Who consumes the next result?**

If the consumer is a human:

```text
natural language is usually appropriate
```

If the consumer is code:

```text
prefer an explicit structure
```

That rule is more useful than “JSON looks more engineered.”

---

## 10. Why Tool Calling is the next chapter

Our travel assistant can now reliably convert:

```text
“I am going to Tokyo and want weather information.”
```

into:

```json
{
  "city": "Tokyo",
  "needs_weather": true,
  ...
}
```

But a new question appears:

> **Is knowing that weather is needed the same as obtaining weather?**

No.

The model can classify:

```text
needs_weather = true
```

Actual weather may require a Python function, an HTTP API, a database, or another external capability.

So we arrive at the most important chapter of Stage 00:

> What does it really mean for a model to “call” a Tool?

The answer is more precise than “the LLM executes a function.”

---

## Chapter takeaway

Structured Output is best understood as:

> **An explicit data contract between probabilistic model generation and deterministic software, so the application does not have to reverse-engineer control data from free-form prose.**

Keep three distinctions:

```text
valid schema != correct fact
Structured Output != Tool Calling
natural language is not bad; it is simply not the right interface for every boundary
```

Next, the model proposes its first external action.

---

## Official references

- OpenAI Responses / structured format: <https://developers.openai.com/api/reference/resources/responses>
- OpenAI Structured Outputs overview: <https://openai.com/index/introducing-structured-outputs-in-the-api/>

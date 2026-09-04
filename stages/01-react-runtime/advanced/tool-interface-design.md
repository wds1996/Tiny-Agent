# Advanced — Tool / Agent-Computer Interface Design: A Correct Runtime Cannot Rescue a Bad Tool Interface

> Language: English | [简体中文](tool-interface-design.zh-CN.md)

The previous chapters focused on Runtime boundaries. There is another failure source that is easy to underestimate:

> **What interface does the model actually see when it decides which capability to use?**

That interface is the Tool definition.

Many Agent failures are not caused by a broken Runtime or a weak model. The Tool interface is simply ambiguous, overlapping, too broad, or returns unusable observations.

Think of a Tool schema as the control panel through which the Agent uses a computer capability.

---

## 1. Start with a bad Tool

```python
Tool(
    name="do_task",
    description="Do a task.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "payload": {"type": "string"},
        },
        "required": ["action", "payload"],
    },
    handler=do_task,
)
```

The Python handler may be perfectly valid. The model, however, sees an interface with unanswered questions: which actions are legal, what format `payload` uses, when this Tool is appropriate, and what it does not support.

Application policy has been pushed back into free-form model guessing.

---

## 2. A good Tool first explains when to use it

A weak description:

```text
Weather tool.
```

A stronger one:

```python
Tool(
    name="get_mock_weather",
    description=(
        "Return the course's deterministic mock weather for one city. "
        "Use it only when the task asks for the course mock weather. "
        "It does not provide live weather data."
    ),
    ...
)
```

The description answers four things:

```text
What does it do?
When should it be used?
When should it not be used?
What is the data boundary?
```

Tool selection is partly a language-understanding problem. A vague interface makes incorrect selection unsurprising.

---

## 3. Tool names should describe stable capabilities

Prefer:

```text
get_weather
search_papers
read_document_chunk
create_report_draft
```

Avoid opaque implementation names such as:

```text
do_task_2
api_v4_call
handle_request
execute_misc
```

The model uses the Tool name as a semantic signal. Humans maintaining the system do too.

---

## 4. Put deterministic constraints in the schema

If units are limited to Celsius and Fahrenheit, do not expose:

```python
{"units": {"type": "string"}}
```

and hope the model never emits `F`, `fahrenheit please`, or `kelvin`.

Express the known domain:

```python
{
    "units": {
        "type": "string",
        "enum": ["celsius", "fahrenheit"],
    }
}
```

Use `required`, enums, ranges, and `additionalProperties=False` where the application already knows the constraint.

A durable rule is:

> **Deterministic constraints belong in schema/code whenever practical, not only in prompt wording.**

---

## 5. Granularity: too narrow and too broad are both expensive

Too narrow:

```text
resolve_city_name
lookup_city_id
build_weather_query
send_weather_http
parse_weather_json
extract_temperature
```

forces the model to plan through implementation details that ordinary code could hide.

Too broad:

```text
shell(command)
http(method, url, headers, body)
```

creates huge authority and ambiguity.

Prefer the smallest task-relevant capability that gives the model useful autonomy without exposing unnecessary implementation or privilege.

For the travel assistant, `get_weather(city)` is usually a better interface than raw HTTP access.

---

## 6. Tool output becomes future model Context

Input design gets attention; output design often does not.

Bad outputs include megabytes of logs, raw HTML, huge database dumps, or stack traces. They increase context cost and make the next decision harder.

Prefer bounded, structured, provenance-rich observations:

```json
{
  "city": "Tokyo",
  "temperature_c": 18.0,
  "condition": "cloudy",
  "source": "course_mock"
}
```

Tool output is upstream of Context Engineering.

---

## 7. Description is not authorization

A Tool description may say:

```text
Only use this Tool for administrators.
```

That helps model selection. It is not a permission system.

Model compliance is probabilistic. Authorization must be enforced deterministically by Runtime/policy.

Keep the distinction:

```text
visible to model
!=
authorized to execute
```

---

## 8. Overlapping Tools create an unnecessary classification problem

A Tool set containing:

```text
search
web_search
internet_search
search_web
browser_search
```

with nearly identical descriptions forces the model to solve a pointless selection problem.

Merge equivalent capabilities or make boundaries explicit:

```text
search_papers
  -> scholarly metadata

search_web
  -> public web pages

search_internal_docs
  -> indexed company documents
```

A larger action space does not automatically make an Agent smarter.

---

## 9. Dynamic exposure is useful, but it is not authorization

Large systems may own hundreds of Tools. Exposing all of them on every turn increases context size, selection difficulty, distraction, and attack surface.

Later Context Engineering stages will select a relevant subset before model invocation.

Still:

```text
exposure selection
!=
authorization
```

A visible Tool may still be denied at execution time.

---

## 10. Evaluate the Tool interface with tasks

Do not rely only on “the description looks clear.” Build a task set covering:

```text
tasks that require Tool A
tasks that require Tool B
tasks that require no Tool
confusable arguments
recoverable Tool failures
```

Measure:

```text
Tool-selection accuracy
argument accuracy
unnecessary calls
recovery after failure
step count
Token/Context cost
```

For the travel assistant:

| Task | Expected behavior |
|---|---|
| “Get the course mock Tokyo weather” | `get_mock_weather` |
| “Convert 18°C to °F” | `celsius_to_fahrenheit` |
| “Is Tokyo the capital of Japan?” | no Tool |
| “Get live Tokyo weather” | do not misrepresent the mock Tool as live data |

That is more meaningful than one successful demo.

---

## 11. Questions an experienced Tool designer asks

Not only:

```text
Can the Python function be called?
```

But:

```text
Does the model know when to use it?
Does the model know when not to use it?
Can known constraints move into the schema?
Is the capability granularity appropriate?
Will output pollute future Context?
Are Tools unnecessarily overlapping?
Is authorization really enforced by the Runtime?
Can the interface be evaluated on a dataset?
```

That is why Tool Calling is not merely “wrap a Python function in JSON Schema.”

It is an **Agent-Computer Interface (ACI)** design problem. The Runtime determines whether execution is governed correctly; the Tool interface strongly influences whether the model can use those capabilities correctly.
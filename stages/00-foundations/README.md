# Stage 00: Do Not Build an Agent Yet—Understand One Model Call First

> Language: **English** | [简体中文](README.zh-CN.md)

Many Agent tutorials begin with a framework, several decorators, and enough vocabulary to make a beginner feel late to a meeting they were never invited to. This chapter starts with the smallest useful unit instead: one model request made by one Python program.

We will answer three questions in order:

1. How does Python send a request to a language model and inspect the response?
2. How can a program receive a stable data structure instead of prose?
3. When a task needs data or a function, what belongs to the model and what belongs to the application?

By the end, you will have implemented one complete **model → tool → model** round trip and, more importantly, you will understand the boundary behind it:

> **The model proposes; the application decides and executes.**

All complete examples live in [`code/`](code/). Each file is reproduced in full where its idea is taught, so this chapter reads straight through rather than sending you on a documentation scavenger hunt.

---

## 1. What a language model is to a Python program

Set aside the word “Agent” for a moment. To your program, a language model is first a remote computation service: the program submits input, and the service returns a response.

```text
user request
    ↓
Python builds an API request
    ↓
the model service generates a response
    ↓
Python inspects that response
```

Two actors appear in this diagram. The model service **generates content**. Your application **makes requests, calls functions, reads databases, and changes state**. Confusing them leads to a classic bug: the model says “the email has been sent,” while the outbox remains admirably empty.

A model response is therefore a proposal produced inside an API protocol. It is not proof that an external action occurred.

### 1.1 Set up the chapter

Use Python 3.10 or newer and install the chapter dependencies from the repository root:

```bash
python -m pip install -r stages/00-foundations/code/requirements.txt
```

The dependency file is intentionally small:

```text
openai>=2,<3
pydantic>=2.11,<3
```

Set the API key and choose a model available to your project that supports the Responses API, Structured Outputs, and Function Calling:

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-id"
```

Do not put an API key in source code or commit it to Git. In Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_MODEL="your-model-id"
```

The examples deliberately do not hard-code a “latest” model. Model catalogs and project access change. Requiring `OPENAI_MODEL` makes that dependency explicit and produces an immediate, useful error when it is missing.

### 1.2 Make the first call

Run:

```bash
python stages/00-foundations/code/first_llm_call.py
```

Complete source:

```python
from __future__ import annotations

import os
from typing import Any


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Set {name} before running this example.")
    return value.strip()


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI SDK is not installed. Run:\n"
            "python -m pip install -r "
            "stages/00-foundations/code/requirements.txt"
        ) from exc

    required_env("OPENAI_API_KEY")
    return OpenAI()


def main() -> None:
    client = create_client()
    model = required_env("OPENAI_MODEL")

    response = client.responses.create(
        model=model,
        instructions=(
            "You are a patient programming teacher. Explain the idea accurately, "
            "use one concrete analogy, and avoid unexplained jargon."
        ),
        input=(
            "In no more than 120 words, explain why a language model response is "
            "a proposal produced by a model rather than an action performed by my "
            "Python program."
        ),
    )

    if response.status != "completed":
        raise RuntimeError(f"The response did not complete: {response.status}")
    if not response.output_text.strip():
        raise RuntimeError("The response completed without text output.")

    print("=== response metadata ===")
    print("response_id:", response.id)
    print("model:", response.model)

    print("\n=== model output ===")
    print(response.output_text)

    usage = response.usage
    if usage is not None:
        print("\n=== token usage ===")
        print("input_tokens:", usage.input_tokens)
        print("output_tokens:", usage.output_tokens)
        print("total_tokens:", usage.total_tokens)


if __name__ == "__main__":
    main()
```

The program has one path: create a client, submit a request, verify completion, and read the result.

```python
response = client.responses.create(...)
```

`response` is not a bare string. Text is one convenient view of a larger protocol object that also carries an ID, status, model metadata, usage, and potentially other output items. `response.output_text` is useful shorthand; it is not the whole response format.

The example also checks both status and text:

```python
if response.status != "completed":
    ...
if not response.output_text.strip():
    ...
```

“No exception was raised” does not necessarily mean “the application received a usable answer.” Explicit checks keep failures close to their cause.

### 1.3 Keep behavior instructions separate from the task

The request contains two fields:

```python
instructions="You are a patient programming teacher..."
input="In no more than 120 words..."
```

They come from different concerns:

```text
instructions  behavior the application wants the model to follow
input         the task to perform on this request
```

Keeping those sources separate is easier to maintain than gluing policy, task, and data into one giant prompt. You can change the task without rewriting the behavior contract, and vice versa.

A person can now read the answer. A program, however, soon asks a less forgiving question: **how can I consume the result reliably?**

---

## 2. Natural language is an excellent conversation format and a fragile API

Suppose the application must turn a request into a task card. A model might write:

```text
This looks fairly important. We probably need current weather data first.
```

That is clear to a person. A program may be tempted to do this:

```python
if "important" in answer.lower():
    priority = "high"
```

Now the interface breaks when the model says “urgent” instead. Keyword guessing is not a contract.

The application would rather receive:

```json
{
  "goal": "compare current weather in Tokyo and Paris",
  "priority": "medium",
  "needs_external_data": true,
  "reason": "current weather must be retrieved"
}
```

**Structured Output** constrains model output to a machine-checkable shape.

### 2.1 Define the contract with Pydantic

Run:

```bash
python stages/00-foundations/code/structured_output.py
```

Complete source:

```python
from __future__ import annotations

import os
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    priority: Priority
    needs_external_data: bool
    reason: str = Field(min_length=1)


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Set {name} before running this example.")
    return value.strip()


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI SDK is not installed. Run:\n"
            "python -m pip install -r "
            "stages/00-foundations/code/requirements.txt"
        ) from exc

    required_env("OPENAI_API_KEY")
    return OpenAI()


def main() -> None:
    client = create_client()
    model = required_env("OPENAI_MODEL")

    response = client.responses.parse(
        model=model,
        instructions=(
            "Turn the request into a task card. Describe only the request itself; "
            "do not guess the weather or pretend that external data was retrieved."
        ),
        input=(
            "Compare the current weather in Tokyo and Paris and tell me which city "
            "is warmer."
        ),
        text_format=TaskCard,
    )

    if response.status != "completed":
        raise RuntimeError(f"The response did not complete: {response.status}")

    task = response.output_parsed
    if task is None:
        raise RuntimeError("The response contained no parsed TaskCard.")

    print(task.model_dump_json(indent=2))
    print(
        "\nThe shape is validated. The claims still need to be checked against "
        "real data."
    )


if __name__ == "__main__":
    main()
```

The Pydantic model states what the application accepts:

```python
class TaskCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    priority: Priority
    needs_external_data: bool
    reason: str = Field(min_length=1)
```

This is more precise than “please return JSON.” It requires the fields, restricts `priority` to an enum, rejects blank strings, and forbids undeclared properties.

The SDK then parses the response into that contract:

```python
response = client.responses.parse(
    ...,
    text_format=TaskCard,
)
task = response.output_parsed
```

`task` is a `TaskCard`, so the rest of the program can use `task.priority` instead of mining prose with regular expressions.

### 2.2 Valid shape does not imply a true claim

This boundary matters:

```text
valid fields and types
        ≠
correct judgment and true facts
```

Structured Output can ensure that `needs_external_data` is a Boolean. It cannot ensure that the model chose the correct Boolean. A response can wear a perfectly tailored JSON suit and still be wrong underneath.

Structured Output answers:

> **How can software read this model output reliably?**

It does not answer:

> **How can the model obtain facts that are outside the request?**

Comparing current weather requires data. The next step is to let the model request a capability implemented by Python.

---

## 3. Tool Calling: the model requests; the application executes

A model does not automatically run your Python function. A function tool has two sides:

```text
interface shown to the model
├── name
├── description
└── parameters (JSON Schema)

implementation kept by the application
└── Python handler
```

The interface helps the model decide what to request. The handler performs the actual work.

Think of the model as a capable colleague behind a service window. It can pass out a request slip:

```json
{
  "name": "get_teaching_weather",
  "arguments": {"city": "Tokyo"}
}
```

The application still holds the keys. It validates the name, parses the arguments, runs the function, and returns the result.

### 3.1 Use deterministic teaching data

This chapter uses a fixed table:

```python
TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}
```

It is not live weather. Deterministic data gives every learner the same trace and keeps network credentials and third-party failures out of a lesson about tool control flow.

### 3.2 Complete one model → tool → model round trip

Run:

```bash
python stages/00-foundations/code/tool_calling.py
```

Complete source:

```python
from __future__ import annotations

import json
import os
from typing import Any


TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}

WEATHER_TOOL = {
    "type": "function",
    "name": "get_teaching_weather",
    "description": (
        "Return the deterministic teaching weather record for Tokyo or Paris. "
        "Use this function whenever the user asks about those teaching records."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "enum": sorted(TEACHING_WEATHER),
                "description": "The city whose teaching record should be read.",
            }
        },
        "required": ["city"],
        "additionalProperties": False,
    },
    "strict": True,
}


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Set {name} before running this example.")
    return value.strip()


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI SDK is not installed. Run:\n"
            "python -m pip install -r "
            "stages/00-foundations/code/requirements.txt"
        ) from exc

    required_env("OPENAI_API_KEY")
    return OpenAI()


def get_teaching_weather(city: str) -> dict[str, Any]:
    try:
        record = TEACHING_WEATHER[city]
    except KeyError as exc:
        raise ValueError(f"Unsupported city: {city}") from exc
    return {"city": city, **record}


def parse_arguments(raw_arguments: str) -> dict[str, Any]:
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Tool arguments are not valid JSON: {raw_arguments!r}") from exc
    if not isinstance(arguments, dict):
        raise RuntimeError("Tool arguments must decode to a JSON object.")
    return arguments


def validate_weather_arguments(arguments: dict[str, Any]) -> str:
    if set(arguments) != {"city"}:
        raise RuntimeError("get_teaching_weather expects exactly one field: city")
    city = arguments["city"]
    if not isinstance(city, str):
        raise RuntimeError("The city argument must be a string.")
    if city not in TEACHING_WEATHER:
        raise RuntimeError(f"Unsupported city: {city}")
    return city


def main() -> None:
    client = create_client()
    model = required_env("OPENAI_MODEL")

    first = client.responses.create(
        model=model,
        instructions=(
            "Use the supplied function to read teaching weather records. A function "
            "call only requests an action; never claim a result before the function "
            "output is returned."
        ),
        input=(
            "Read Tokyo's deterministic teaching weather record and report the "
            "temperature and condition."
        ),
        tools=[WEATHER_TOOL],
        tool_choice={"type": "function", "name": "get_teaching_weather"},
        parallel_tool_calls=False,
    )

    if first.status != "completed":
        raise RuntimeError(f"The first response did not complete: {first.status}")

    calls = [item for item in first.output if item.type == "function_call"]
    if len(calls) != 1:
        raise RuntimeError(f"Expected exactly one function call, received {len(calls)}.")

    call = calls[0]
    if call.name != "get_teaching_weather":
        raise RuntimeError(f"The model requested an unknown function: {call.name}")

    arguments = parse_arguments(call.arguments)
    city = validate_weather_arguments(arguments)
    result = get_teaching_weather(city)

    print("=== model proposed ===")
    print(call.name, arguments)
    print("\n=== application executed ===")
    print(result)

    final = client.responses.create(
        model=model,
        instructions=(
            "Answer only from the returned function output. Make clear that this is "
            "a deterministic teaching record, not live weather."
        ),
        previous_response_id=first.id,
        input=[
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result, ensure_ascii=False),
            }
        ],
        tools=[WEATHER_TOOL],
        tool_choice="none",
    )

    if final.status != "completed":
        raise RuntimeError(f"The final response did not complete: {final.status}")
    if not final.output_text.strip():
        raise RuntimeError("The final response completed without text output.")

    print("\n=== final answer ===")
    print(final.output_text)


if __name__ == "__main__":
    main()
```

Read the program in time order. It performs five steps.

#### Step 1: expose the tool interface

```python
first = client.responses.create(
    ...,
    tools=[WEATHER_TOOL],
    tool_choice={"type": "function", "name": "get_teaching_weather"},
    parallel_tool_calls=False,
)
```

For this controlled lesson, `tool_choice` forces the named function and `parallel_tool_calls=False` limits the turn to one call. That removes model-choice variability while we inspect the protocol.

At this point, the model has produced a Function Call. **The function has not run.**

#### Step 2: check the requested capability

```python
if call.name != "get_teaching_weather":
    raise RuntimeError(...)
```

Do not feed a model-produced name directly into dynamic execution. The model may propose a name; the application decides which names map to real handlers.

#### Step 3: parse arguments and execute in Python

```python
arguments = parse_arguments(call.arguments)
result = get_teaching_weather(**arguments)
```

Python reads the table. The model neither enters the interpreter nor acquires hidden execution privileges.

#### Step 4: correlate the result with the request

```python
{
    "type": "function_call_output",
    "call_id": call.call_id,
    "output": json.dumps(result, ensure_ascii=False),
}
```

`call_id` says which request produced this result. Two calls can use the same tool name and still be different actions:

```text
call_A -> get_teaching_weather(Tokyo)
call_B -> get_teaching_weather(Paris)
```

The name alone cannot preserve that relationship.

#### Step 5: ask the model to answer from the result

```python
final = client.responses.create(
    previous_response_id=first.id,
    input=[function_call_output],
    tools=[WEATHER_TOOL],
    tool_choice="none",
)
```

`previous_response_id` continues from the first response. The new input is the function output produced by the application. `tool_choice="none"` makes this second turn produce text rather than another tool request.

The full timeline is:

```text
user task
    ↓
model generates a Function Call (proposal)
    ↓
Python checks the name and arguments
    ↓
Python executes the function (action)
    ↓
application returns Function Call Output (observation)
    ↓
model writes an answer from that observation
```

That sequence is the central result of this chapter.

---

## 4. Three distinctions worth keeping

### 4.1 Structured Output is not Tool Calling

Both use structured data, but for different jobs:

```text
Structured Output
    return a data object for the application to read

Tool Calling
    return an action request for the application to consider
```

A neatly completed order form does not walk to the warehouse by itself.

### 4.2 Tool Calling is not Tool Execution

```text
the model returned a Tool Call
        ≠
the Python function ran
```

Execution begins only after the application validates the request and explicitly invokes a handler.

### 4.3 Model output is not automatically system truth

Prose, structured objects, and tool calls are all model-generated content first. The application must interpret each according to its role. A string that looks like a command does not grant itself authority.

---

## 5. What we have actually built

We have not built an indefinitely autonomous Agent, and there is no reason to pretend otherwise. We built a small, explicit chain:

```text
one model call
    ↓
machine-readable structured output
    ↓
a model-proposed function call
    ↓
application execution and result
    ↓
a final answer grounded in that result
```

`tool_calling.py` still hard-codes one tool turn followed by one text turn. A task that needs zero, two, or five tool calls would force us to repeat the same control code. The next chapter starts from that concrete pressure and turns the repetition into a small runtime.

➡️ [Stage 01: Make the Model Work in a Loop—Build a Minimal Agent Runtime](../01-react-runtime/README.md)

---

## 6. Exercises

These exercises are experiments, not vocabulary quizzes.

### Exercise 1: separate shape from truth

Add a `confidence: float` field to `TaskCard` and constrain it to the range 0–1. Observe what validation guarantees, then ask whether `confidence=0.99` proves the judgment is correct.

### Exercise 2: request Paris

Change the user input in `tool_calling.py` to request Paris. Leave the handler untouched and trace the argument through the Function Call, Python execution, and Function Call Output.

### Exercise 3: manufacture an unknown tool

Temporarily alter the allowed-name check and observe where the program stops. Explain why knowing a name does not create a capability.

### Exercise 4: remove `call_id` on paper

Draw two calls to the same tool and try to match two returned values without IDs. Thirty seconds with that diagram usually cures the urge to discard correlation fields.

---

## 7. Chapter checklist

You should now be able to explain, from the code rather than from memorized definitions:

- how `response.output_text` differs from the complete response object;
- what Structured Output guarantees and what it cannot guarantee;
- why a tool has both a schema and a Python handler;
- why a Function Call is a proposal rather than an executed action;
- what `call_id` and `previous_response_id` correlate;
- why deterministic teaching data is useful here.

Chapter layout:

```text
stages/00-foundations/
├── README.md
├── README.zh-CN.md
└── code/
    ├── first_llm_call.py
    ├── structured_output.py
    ├── tool_calling.py
    └── requirements.txt
```

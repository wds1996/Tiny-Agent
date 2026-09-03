# 03 — The Model Does Not “Run Python”: What Tool Calling Actually Means

> Language: English | [简体中文](03-function-calling.zh-CN.md)

The previous chapter solved one problem: returning model output in a structure that software can consume.

Our travel assistant can now recognize:

```json
{
  "city": "Tokyo",
  "needs_weather": true
}
```

But recognizing that weather is needed is not the same thing as obtaining weather.

Real weather lives outside the model. It may come from an HTTP API, a database, an MCP server, or one of our own Python functions.

So the next question is:

> **How can a model use capabilities that it does not inherently possess?**

Many tutorials shorten the answer to “the LLM calls a function.” Convenient phrase, misleading mental model.

A more accurate statement is:

> **The model generates a structured ToolCall proposal; the application Runtime validates and executes the real Tool, then returns the result to the model.**

Understand this chapter and you can already see half of the Stage 01 Agent loop.

---

## 1. Fix the most common misconception first

Suppose Python contains:

```python
def get_weather(city: str) -> dict:
    ...
```

The model does not automatically acquire that function because it exists in your process.

It also does not mysteriously jump into your interpreter and execute:

```python
get_weather("Tokyo")
```

What the model sees is an **interface description** supplied by the application:

```python
TOOLS = [
    {
        "type": "function",
        "name": "get_weather",
        "description": "Get weather data for a city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"}
            },
            "required": ["city"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]
```

From that description, the model may emit something equivalent to:

```text
function_call
name = "get_weather"
arguments = {"city": "Tokyo"}
```

At this point **the weather function has still not executed**.

The model has only said:

> “I think the next step should use `get_weather` with Tokyo as the argument.”

Execution still belongs to your application.

---

## 2. One Tool lives in two different worlds

This is the diagram worth remembering:

```text
              MODEL-FACING WORLD
┌─────────────────────────────────┐
│ name: get_weather               │
│ description: get city weather   │
│ parameters: {city: string}      │
└─────────────────────────────────┘
                 │
                 │ model proposes ToolCall
                 ▼
              RUNTIME BOUNDARY
┌─────────────────────────────────┐
│ Does the Tool exist?            │
│ Are arguments valid?            │
│ Is the caller authorized?       │
│ Is approval required?           │
└─────────────────────────────────┘
                 │
                 │ execute only if allowed
                 ▼
              EXECUTION WORLD
┌─────────────────────────────────┐
│ def get_weather(city):          │
│     call API / DB / local code  │
└─────────────────────────────────┘
```

Therefore:

```text
Tool schema
!=
Tool handler
```

The Tool schema is the model-facing contract.

The Tool handler is executable application code.

The implementation behind the same interface might later be:

```text
local Python
HTTP API
database query
remote worker
MCP server
sandbox
```

The model-facing contract can remain stable while execution infrastructure changes.

---

## 3. A complete OpenAI Tool Calling loop

The following example intentionally avoids LangChain, LangGraph, and the Agents SDK.

It uses the OpenAI Responses API with two local Tools:

```text
get_weather(city)
celsius_to_fahrenheit(temperature_c)
```

Weather is deterministic mock course data so the lesson is Tool orchestration rather than signing up for a third-party weather API.

```python
import json
from openai import OpenAI

client = OpenAI()

TOOLS = [
    {
        "type": "function",
        "name": "get_weather",
        "description": "Get mock weather data used by this course example.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"}
            },
            "required": ["city"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "celsius_to_fahrenheit",
        "description": "Convert a Celsius temperature to Fahrenheit.",
        "parameters": {
            "type": "object",
            "properties": {
                "temperature_c": {"type": "number"}
            },
            "required": ["temperature_c"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def get_weather(city: str) -> dict:
    # Fixed teaching data, not live weather.
    if city not in {"Tokyo", "东京"}:
        raise ValueError("This course example only contains Tokyo data")
    return {"city": "Tokyo", "temperature_c": 18.0}


def celsius_to_fahrenheit(temperature_c: float) -> dict:
    value = temperature_c * 9 / 5 + 32
    return {"temperature_f": round(value, 1)}


def execute_tool(name: str, arguments: dict) -> dict:
    if name == "get_weather":
        return get_weather(**arguments)
    if name == "celsius_to_fahrenheit":
        return celsius_to_fahrenheit(**arguments)
    raise ValueError(f"Unknown Tool: {name}")


instructions = (
    "You are a travel assistant. "
    "Use the provided Tools for weather and temperature conversion instead of guessing. "
    "The weather data in this course is mocked, so say that explicitly."
)

response = client.responses.create(
    model="gpt-5.6-luna",
    instructions=instructions,
    input="What is the mock Tokyo weather in Celsius, and what is it in Fahrenheit?",
    tools=TOOLS,
    parallel_tool_calls=False,
)

for step in range(1, 6):
    calls = [item for item in response.output if item.type == "function_call"]

    if not calls:
        print("final:", response.output_text)
        break

    call = calls[0]
    arguments = json.loads(call.arguments)
    print(f"step {step}: model -> {call.name}({arguments})")

    result = execute_tool(call.name, arguments)
    print(f"step {step}: tool  -> {result}")

    response = client.responses.create(
        model="gpt-5.6-luna",
        instructions=instructions,
        previous_response_id=response.id,
        tools=TOOLS,
        parallel_tool_calls=False,
        input=[
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result),
            }
        ],
    )
else:
    raise RuntimeError("Tool loop exceeded the maximum number of steps")
```

Runnable version:

[`../code/minimal_tool_loop.py`](../code/minimal_tool_loop.py)

### Expected output

Exact wording and call choices can vary, but a reasonable run looks like:

```text
step 1: model -> get_weather({'city': 'Tokyo'})
step 1: tool  -> {'city': 'Tokyo', 'temperature_c': 18.0}
step 2: model -> celsius_to_fahrenheit({'temperature_c': 18.0})
step 2: tool  -> {'temperature_f': 64.4}
final: The course's mock Tokyo weather is 18°C, which is about 64.4°F. This is mock data, not live weather.
```

The point is not that the code is longer. The point is to see exactly which component owns every step.

---

## 4. On the first turn, the model executed no Python

The first request provides:

```text
user task
+ instructions
+ Tool names, descriptions, and parameter schemas
```

The response may contain an output item such as:

```python
item.type == "function_call"
item.name == "get_weather"
item.arguments == '{"city":"Tokyo"}'
```

The arguments are still model-generated data.

Treat them as:

```text
untrusted proposal
```

not:

```text
already-authorized command
```

Even with `strict=True`, schema enforcement mainly constrains shape. Business validity and authorization remain Runtime responsibilities.

---

## 5. Why `call_id` matters

A function call contains a correlation identifier:

```python
call.call_id
```

That identifier connects:

```text
this particular model-proposed ToolCall
```

with:

```text
this particular Tool result returned by your code
```

So the application returns:

```python
{
    "type": "function_call_output",
    "call_id": call.call_id,
    "output": json.dumps(result),
}
```

You can read it as:

> “The real execution result for the call you identified as `call_xxx` is here.”

Do not correlate Tool results only by Tool name. A model may call the same Tool multiple times; `call_id` identifies the individual call.

---

## 6. Why call the model again after Python has the result?

Suppose Python executes:

```python
result = get_weather("Tokyo")
```

and obtains:

```python
{"city": "Tokyo", "temperature_c": 18.0}
```

The model does not automatically learn that variable just because it now exists in the same Python process.

There is no telepathy between model inference and your local memory.

You must provide the observation in the next model request:

```python
input=[
    {
        "type": "function_call_output",
        "call_id": call.call_id,
        "output": json.dumps(result),
    }
]
```

This creates the fundamental Agent feedback loop:

```text
Model
  ↓ ToolCall
Runtime
  ↓ execute
Environment / Python / API
  ↓ result
Runtime
  ↓ function_call_output
Model
```

That is the smallest useful **action → observation** cycle.

---

## 7. Why explicitly provide `instructions` and `tools` again?

The continuation call still includes:

```python
instructions=instructions,
tools=TOOLS,
previous_response_id=response.id,
```

This is not accidental repetition. It teaches an important habit:

> **The application should explicitly construct what the current turn is allowed to see, follow, and use.**

Do not build safety or control policy around “the previous turn probably still remembers it.”

Later runtimes will package these concerns behind cleaner abstractions, but the underlying responsibility remains.

---

## 8. Why `strict=True` is still not a security boundary

A schema such as:

```json
{
  "city": {"type": "string"}
}
```

can constrain the city argument to be a string.

It cannot answer:

```text
Is this user authorized?
Does this Tool have side effects?
Is this filesystem path allowed?
Does this amount exceed a business limit?
Is human approval required?
```

For example:

```text
delete_database(database="production")
```

may be perfectly schema-valid and still be forbidden.

Keep these layers separate:

```text
schema-valid
!=
business-valid
!=
authorized
!=
safe to execute
```

Stage 07 turns these Runtime policies into a full topic, but the boundary should already be correct here.

---

## 9. Tool descriptions are part of the interface, not decoration

Tool selection depends heavily on:

```text
Tool name
Tool description
argument descriptions
current task Context
```

If two Tools are called `search` and `find`, and both descriptions merely say “Search something,” the model has little semantic help choosing correctly.

A useful Tool description explains:

```text
what the Tool does
when it should be used
what it returns
important limitations
```

For example:

```text
search_papers:
Search scholarly metadata and return titles, authors, DOIs, and abstract metadata.
This Tool does not return full paper text, so metadata should not be treated as
full-text evidence of a paper's findings.
```

The Tool interface is part of the Agent-Computer Interface. Stage 01 develops this further.

---

## 10. Tool failure is a Runtime design problem

Our teaching function may raise:

```python
ValueError("This course example only contains Tokyo data")
```

A toy program can simply crash.

A mature Agent Runtime must distinguish cases such as:

```text
repairable argument error
    -> safe Tool failure observation may help the model repair

permission denial
    -> retries must not bypass policy

internal exception
    -> do not dump sensitive stack text into model Context

transient network failure
    -> retry only if the operation itself is safe to repeat
```

You do not need to implement all of that in Stage 00. You do need to understand that Tool failure is part of Runtime semantics, not merely `try/except` syntax.

---

## 11. What separates this from a real Agent Runtime?

We already have:

```text
model
  ↓ proposes action
runtime
  ↓ executes
observation
  ↓
model
```

That is close to a ReAct loop.

But the teaching script still lacks:

```text
explicit message/state types
ToolRegistry
validation layer
step budget
cost budget
timeout
retry policy
permissions
approval
persistence
tracing
evaluation
```

That is why Stage 01 exists.

Stage 01 is not “now use a fancier framework.” It asks:

> **Now that the model and Tools can interact repeatedly, how do we turn this loop into a clear, testable, bounded Runtime?**

---

## 12. The chain you should be able to draw from memory

```text
user
 ↓
application exposes Tool schema to model
 ↓
model emits function_call
 ↓
Runtime reads name + arguments
 ↓
Runtime validates / authorizes
 ↓
Python / API actually executes
 ↓
Runtime obtains result
 ↓
returns function_call_output + call_id
 ↓
model sees observation
 ↓
model calls another Tool or gives final answer
```

If you can assign an owner to every arrow, you understand the core of Tool Calling.

Avoid saying:

> “The model executed my Python function.”

Prefer:

> **The model proposed a ToolCall; the Runtime executed the Tool.**

That wording protects an important architectural boundary for the rest of the course.

---

## Official references

- OpenAI Responses API: <https://developers.openai.com/api/reference/resources/responses>
- OpenAI Function Calling: <https://help.openai.com/en/articles/8555517-function-calling-in-the-openai-api>

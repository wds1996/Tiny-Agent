# Model Provider Adapters: Connecting a Runtime to a Real LLM

Stage 01 already has an Agent loop. Until now, however, a scripted fake model has been making the decisions. This chapter connects the same runtime to a real model provider without moving provider-specific logic into the runtime.

The central engineering idea is simple:

> **Agent orchestration and model-provider protocol are different responsibilities.**

A clean Agent runtime should understand concepts such as `ToolCall`, `Observation`, stopping conditions, and execution state. It should not need to understand every vendor's request objects, response objects, authentication rules, or function-call wire format.

---

## 1. Where the adapter sits

Tiny-Agent uses the following dependency direction:

```text
                         provider-neutral boundary
                                  |
                                  v
User -> AgentRuntime -> Model protocol -> OpenAIResponsesModel -> OpenAI API
          |                            |
          |                            +-- request translation
          |                            +-- response parsing
          |                            +-- provider errors
          |
          +-> ToolRegistry -> Python handlers
```

`AgentRuntime` only knows this contract:

```python
class Model(Protocol):
    def generate(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> ModelResponse:
        ...
```

It does not import the OpenAI Python package.

This gives us an important architectural property:

```text
AgentRuntime
    |
    +--> OpenAIResponsesModel
    +--> FutureAnthropicModel
    +--> FutureQwenModel
    +--> FakeModel
```

Changing the provider should not require rewriting the loop.

---

## 2. Why this is more than wrapping an API call

A provider adapter performs **protocol translation** in both directions.

### Tiny-Agent to provider

It translates:

```text
Tiny-Agent message history
Tiny-Agent tool schema
```

into:

```text
provider input items
provider function definitions
provider configuration
```

### Provider to Tiny-Agent

It translates:

```text
provider response items
```

into:

```text
ModelResponse(
    tool_calls=[...]
)
```

or:

```text
ModelResponse(
    final_answer="..."
)
```

The normalized result means every other component can ignore provider-specific types.

---

## 3. The Responses API tool-calling lifecycle

At the time this chapter was written, OpenAI's current function-calling flow with the Responses API is conceptually:

```text
1. Send input + available tool definitions
                 |
                 v
2. Model emits function_call item(s)
                 |
                 v
3. Application executes functions
                 |
                 v
4. Application sends function_call_output item(s)
                 |
                 v
5. Model decides again
```

The model's function call contains three fields that matter to our runtime:

```text
call_id
name
arguments
```

Example provider output:

```json
{
  "type": "function_call",
  "call_id": "call_123",
  "name": "multiply",
  "arguments": "{\"a\":23,\"b\":17}"
}
```

Notice that `arguments` is a **JSON-encoded string**, not already a Python dictionary.

Our adapter therefore performs:

```python
arguments = json.loads(item.arguments)
```

and normalizes it to:

```python
ToolCall(
    id="call_123",
    name="multiply",
    arguments={"a": 23, "b": 17},
)
```

---

## 4. Why `call_id` matters

Suppose the model asks for two tools in one turn:

```text
call_A -> get_weather(Tokyo)
call_B -> get_weather(Paris)
```

Later, the runtime may have two results:

```text
Tokyo -> 31 C
Paris -> 24 C
```

The provider must know which result belongs to which model request.

That is the purpose of `call_id`.

The tool result is sent back as something conceptually equivalent to:

```json
{
  "type": "function_call_output",
  "call_id": "call_A",
  "output": "31 C"
}
```

The ID is therefore not decorative metadata. It is a **correlation identifier** across the request/execute/observation boundary.

Tiny-Agent stores it in:

```python
ToolCall.id
```

and later copies it into:

```python
{
    "role": "tool",
    "tool_call_id": call.id,
    ...
}
```

The provider adapter finally converts that transcript item back into the provider's expected `function_call_output` representation.

A useful mental model is:

```text
Model request
   |
   | call_id = X
   v
Runtime execution
   |
   | call_id = X
   v
Observation returned to model
```

---

## 5. Tool schemas are part of the model interface

Consider this Python function:

```python
def multiply(a: float, b: float) -> float:
    return a * b
```

The LLM cannot inspect or invoke that callable directly.

It receives a schema such as:

```python
{
    "name": "multiply",
    "description": "Multiply two numbers.",
    "parameters": {
        "type": "object",
        "properties": {
            "a": {"type": "number"},
            "b": {"type": "number"},
        },
        "required": ["a", "b"],
        "additionalProperties": False,
    },
}
```

The OpenAI adapter converts that provider-neutral representation into:

```python
{
    "type": "function",
    "name": "multiply",
    "description": "Multiply two numbers.",
    "parameters": {...},
    "strict": True,
}
```

This is one reason Tool design is an Agent engineering problem rather than only a Python programming problem.

The model chooses tools based partly on:

- tool name;
- description;
- parameter names;
- parameter descriptions;
- schema constraints;
- surrounding instructions.

A technically correct handler with a poor schema can still produce a poor Agent.

---

## 6. Strict function schemas

OpenAI recommends strict schema adherence for function calls.

For strict object schemas, two especially important constraints are:

```text
additionalProperties = false
```

and every property must appear in:

```text
required
```

Optional values can be represented using nullable types when necessary.

Example:

```python
{
    "type": "object",
    "properties": {
        "location": {"type": "string"},
        "units": {
            "type": ["string", "null"],
            "enum": ["celsius", "fahrenheit", None],
        },
    },
    "required": ["location", "units"],
    "additionalProperties": False,
}
```

Tiny-Agent Stage 01 enables strict tools by default in `OpenAIResponsesModel`.

Later we can move schema validation into Tiny-Agent itself so bad schemas fail locally before an API request is sent.

---

## 7. The adapter performs one model turn, not an Agent run

This distinction is fundamental.

Wrong design:

```text
AgentRuntime.run()
    |
    v
OpenAI adapter
    |
    +-> model
    +-> execute tools
    +-> model again
    +-> execute tools
    +-> final answer
```

If the adapter owns that entire loop, then `AgentRuntime` has almost no purpose.

Tiny-Agent instead uses:

```text
AgentRuntime.run()
    |
    +-> model.generate()       # exactly one model decision
    |
    +-> execute tool(s)
    |
    +-> append observation(s)
    |
    +-> model.generate()       # next decision
    |
    ...
```

Therefore `OpenAIResponsesModel.generate()` performs exactly one provider request.

This separation becomes very important later when we add:

- retries;
- permissions;
- tracing;
- human approval;
- budgets;
- checkpointing;
- evaluation.

Those concerns belong around the Agent loop, not hidden inside a provider SDK wrapper.

---

## 8. Mapping Tiny-Agent messages to Responses input items

Our runtime currently stores a simple provider-neutral transcript.

### User message

Tiny-Agent:

```python
{
    "role": "user",
    "content": "Calculate 23 * 17"
}
```

Responses input:

```python
{
    "role": "user",
    "content": "Calculate 23 * 17"
}
```

This case maps directly.

### Assistant function call

Tiny-Agent:

```python
{
    "role": "assistant",
    "tool_calls": [
        {
            "id": "call_123",
            "name": "multiply",
            "arguments": {"a": 23, "b": 17},
        }
    ],
}
```

Responses input representation:

```python
{
    "type": "function_call",
    "call_id": "call_123",
    "name": "multiply",
    "arguments": '{"a": 23, "b": 17}',
}
```

### Tool observation

Tiny-Agent:

```python
{
    "role": "tool",
    "tool_call_id": "call_123",
    "name": "multiply",
    "content": "391",
}
```

Responses input representation:

```python
{
    "type": "function_call_output",
    "call_id": "call_123",
    "output": "391",
}
```

This translation is implemented in:

```text
src/tiny_agent/models/openai.py
```

---

## 9. Serial dependencies between tools

Consider:

```text
(23 * 17) + 41
```

The correct execution dependency is:

```text
multiply(23, 17)
       |
       v
      391
       |
       v
add(391, 41)
       |
       v
      432
```

The second call cannot be constructed correctly until the first observation exists.

So the natural trajectory is:

```text
Model turn 1
  -> multiply(23, 17)

Runtime
  -> 391

Model turn 2
  -> add(391, 41)

Runtime
  -> 432

Model turn 3
  -> final answer
```

This is a genuine iterative Agent pattern.

The environment has contributed new information after each action.

---

## 10. Parallel tool calls are different

Now consider:

```text
What is the weather in Tokyo and Paris?
```

These two operations are independent:

```text
              +-> weather(Tokyo)
User question |
              +-> weather(Paris)
```

A capable model may emit both tool calls in the same turn.

Tiny-Agent already supports this response shape:

```python
ModelResponse(
    tool_calls=[call_a, call_b]
)
```

The current runtime executes them sequentially in Python, but they belong to the **same model turn**.

Later, production execution can run independent calls concurrently with async I/O.

Do not confuse these two concepts:

```text
multiple tool calls in one model decision
```

versus:

```text
parallel physical execution of the Python handlers
```

They are related but not identical.

---

## 11. Why Stage 01 uses reasoning effort `none`

Modern Responses workflows can preserve provider-native reasoning state across turns.

For GPT-5.6, OpenAI recommends preserving model output items when manually maintaining history, or using provider mechanisms such as response chaining where appropriate.

That is an important topic, but it introduces several new concepts at once:

- provider-native response IDs;
- persisted reasoning items;
- manual history replay;
- conversation state;
- concurrency and session ownership.

Stage 01 has a narrower goal:

> Learn the Agent runtime/provider boundary.

Therefore the initial OpenAI adapter defaults to:

```python
reasoning_effort="none"
```

and reconstructs the visible transcript each turn.

This keeps the adapter stateless and lets us verify an important property:

```text
adding a real provider does not require changing AgentRuntime
```

Provider-native state management belongs to the later Stateful Orchestration stage, where we can compare transcript replay, `previous_response_id`, sessions, and persistence deliberately.

---

## 12. Why the example defaults to GPT-5.6 Luna

The model is deliberately configurable:

```python
OpenAIResponsesModel(model="gpt-5.6-luna")
```

A learning repository should not force every simple arithmetic experiment through the most expensive available model.

The current GPT-5.6 family provides different cost/capability trade-offs. Luna is intended for cost-sensitive workloads, Terra provides a middle ground, and Sol is the flagship tier.

The important architectural lesson is that changing this:

```python
model="gpt-5.6-luna"
```

to another supported model should not change:

```python
AgentRuntime
Tool
ToolRegistry
```

---

## 13. Error boundaries

There are several different failure classes in this small adapter already.

### A. Provider request fails

Examples:

```text
invalid API key
rate limit
network failure
model unavailable
```

The provider SDK raises an exception.

Stage 01 intentionally does not hide those errors.

Later the reliability stage will decide which errors should be retried and with what policy.

### B. Model emits malformed JSON arguments

The provider returns:

```text
"arguments": "not valid json"
```

The adapter cannot construct a valid `ToolCall`, so it raises a protocol error.

### C. JSON decodes to the wrong shape

Function arguments should be an object:

```json
{"a": 1, "b": 2}
```

not:

```json
[1, 2]
```

The adapter checks this boundary as well.

### D. Tool handler fails

This is not a provider-adapter problem.

The exception happens later:

```text
AgentRuntime -> ToolRegistry -> Tool handler
```

Our runtime currently converts that failure into a tool observation so the model may recover.

This distinction is useful:

```text
provider/protocol error   -> model adapter
execution error           -> tool/runtime layer
```

---

## 14. Why we inject a fake client in tests

`OpenAIResponsesModel` accepts:

```python
client=...
```

This is dependency injection.

Production:

```python
OpenAIResponsesModel()
```

creates the real SDK client.

Unit test:

```python
OpenAIResponsesModel(client=FakeOpenAIClient(...))
```

uses a deterministic fake.

This lets us test:

- request translation;
- strict tool configuration;
- JSON argument decoding;
- `call_id` preservation;
- multiple function calls;
- final answer normalization;

without:

- internet access;
- an API key;
- token cost;
- nondeterministic model behavior.

This separation between unit tests and live integration tests is essential in production Agent systems.

---

## 15. End-to-end example

The repository contains:

```text
code/openai_multi_tool_agent.py
```

The user asks:

```text
Calculate (23 * 17) + 41 and explain the result.
```

A possible trajectory is:

```text
USER
  Calculate (23 * 17) + 41

MODEL ACTION
  multiply(a=23, b=17)

OBSERVATION
  391

MODEL ACTION
  add(a=391, b=41)

OBSERVATION
  432

FINAL
  23 * 17 = 391, and 391 + 41 = 432.
```

The exact wording and tool trajectory are model decisions; the runtime should not hard-code that sequence.

---

## 16. What is deterministic and what is agentic?

This example contains both.

### Deterministic application logic

```text
ToolRegistry lookup
JSON decoding
Python multiplication
Python addition
stopping at max_steps
message bookkeeping
```

### Model-driven decisions

```text
whether a tool is needed
which tool to choose
what arguments to generate
whether another tool is needed
when to produce the final response
```

This distinction becomes increasingly important throughout Tiny-Agent:

> **Use ordinary software control flow where the correct behavior is known. Use the model where semantic judgment is genuinely useful.**

---

## 17. Interview-level questions

After this chapter, you should be able to answer all of the following.

1. Why should `AgentRuntime` not import the OpenAI SDK directly?
2. What exactly does a provider adapter normalize?
3. Why are function-call arguments usually JSON decoded in the adapter?
4. What is `call_id`, and why must it survive tool execution?
5. What is the difference between a tool schema and a Python handler?
6. Why does `generate()` perform one model turn instead of owning the Agent loop?
7. What is the difference between serially dependent tool calls and multiple independent tool calls?
8. Does multiple function calling automatically mean Python functions execute concurrently?
9. Why are fake provider clients useful in unit tests?
10. Which errors belong to the adapter layer and which belong to the runtime/tool layer?
11. Why does this introductory adapter deliberately avoid complex persisted reasoning state?
12. How would you add another provider without rewriting `AgentRuntime`?

---

## 18. Files to read next

Read these in order:

```text
src/tiny_agent/models/openai.py
```

then:

```text
tests/test_openai_adapter.py
```

then run:

```text
stages/01-react-runtime/code/openai_multi_tool_agent.py
```

When you can explain the full transformation below, you have understood this lesson:

```text
Tiny-Agent Tool schema
       |
       v
OpenAI function definition
       |
       v
function_call
       |
       v
Tiny-Agent ToolCall
       |
       v
ToolRegistry execution
       |
       v
Tiny-Agent tool observation
       |
       v
function_call_output
       |
       v
next model decision
```

---

## References

- OpenAI Function Calling guide: https://developers.openai.com/api/docs/guides/function-calling
- OpenAI model guidance: https://developers.openai.com/api/docs/guides/latest-model
- OpenAI model catalog: https://developers.openai.com/api/docs/models
- OpenAI Python SDK: https://github.com/openai/openai-python

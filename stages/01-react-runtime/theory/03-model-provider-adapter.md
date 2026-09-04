# 03 — Provider Adapters: Keep the Agent Runtime Independent of the Model Vendor

> Language: English | [简体中文](03-model-provider-adapter.zh-CN.md)

The previous chapter gave us a deliberately small Runtime contract:

```python
class Model(Protocol):
    def generate(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> ModelResponse:
        ...
```

That ordinary-looking interface encodes an important architecture rule:

> **The Agent Runtime understands Tiny-Agent semantics, not OpenAI-, Qwen-, or provider-specific Response objects.**

Stage 00 introduced the reason for separating provider clients from the Runtime. This chapter makes that separation concrete by connecting OpenAI Responses API to the Runtime and following the translation in both directions.

---

## 1. The dependency direction

```text
User
  ↓
AgentRuntime
  ↓
Model Protocol
  ↓
OpenAIResponsesModel
  ↓
OpenAI Responses API
```

Meanwhile:

```text
AgentRuntime
  ↓
ToolRegistry
  ↓
Python Tool
```

The Adapter sits exactly at the provider boundary.

It should translate requests and responses. It should not execute Tools, own `max_steps`, perform approval, or secretly run multiple model turns.

---

## 2. An Adapter is more than a thin API wrapper

A wrapper that merely returns the provider Response still forces the Runtime to understand provider types.

A real Adapter performs bidirectional protocol translation.

### Tiny-Agent -> provider

It translates:

```text
messages
Tool schemas
```

into provider input items, function definitions, and provider configuration.

### Provider -> Tiny-Agent

It translates provider output items into either:

```python
ModelResponse(tool_calls=[...])
```

or:

```python
ModelResponse(final_answer="...")
```

The Adapter is therefore both a protocol translator and a normalization boundary.

---

## 3. `generate()` must represent one model turn

A bad design hides the whole Agent loop inside the Adapter:

```text
AgentRuntime.run()
      ↓
Adapter.generate()
      ↓
model -> Tool -> model -> Tool -> final answer
```

Then permissions, approval, retries, tracing, budgets, and checkpoints have nowhere clean to wrap the loop.

Tiny-Agent instead defines:

```text
Runtime
  ↓
model.generate()      # one model decision
  ↓
ModelResponse
  ↓
Runtime executes Tool(s)
  ↓
Observation
  ↓
Runtime
  ↓
model.generate()      # next decision
```

`OpenAIResponsesModel.generate()` performs exactly one provider request.

---

## 4. Normalizing an OpenAI `function_call`

A function-call output item contains fields such as:

```text
call_id
name
arguments
```

Conceptually:

```json
{
  "type": "function_call",
  "call_id": "call_weather",
  "name": "get_mock_weather",
  "arguments": "{\"city\": \"Tokyo\"}"
}
```

The provider `arguments` value is JSON text. Tiny-Agent wants a Python dictionary:

```python
arguments = json.loads(item.arguments)

call = ToolCall(
    id=item.call_id,
    name=item.name,
    arguments=arguments,
)
```

Once normalization is complete, the Runtime no longer needs to know about `response.output`, `item.type`, or provider JSON-string details.

---

## 5. Why `call_id` must survive execution

Suppose one model turn requests:

```text
call_A -> get_mock_weather(Tokyo)
call_B -> get_mock_weather(Paris)
```

The returned observations must remain correlated with the original requests.

Provider output therefore comes back using the same correlation identifier:

```json
{
  "type": "function_call_output",
  "call_id": "call_A",
  "output": "18"
}
```

Tiny-Agent preserves this identifier in `ToolCall.id` and later in `tool_call_id` on the observation transcript item.

The full path is:

```text
provider function_call(call_id=X)
        ↓
Tiny-Agent ToolCall.id=X
        ↓
Runtime Tool execution
        ↓
Tiny-Agent observation(tool_call_id=X)
        ↓
Adapter
        ↓
provider function_call_output(call_id=X)
```

Without the identifier, multiple calls become ambiguous.

---

## 6. Translating Tool schemas

Tiny-Agent keeps a provider-neutral schema:

```python
{
    "name": "get_mock_weather",
    "description": "Return course mock weather for a city.",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
        },
        "required": ["city"],
        "additionalProperties": False,
    },
}
```

The OpenAI Adapter turns it into a function Tool definition:

```python
{
    "type": "function",
    "name": "get_mock_weather",
    "description": "Return course mock weather for a city.",
    "parameters": {...},
    "strict": True,
}
```

The Runtime should not permanently adopt one provider's wire representation as its internal type system.

---

## 7. Translating the transcript

A Tiny-Agent assistant ToolCall:

```python
{
    "role": "assistant",
    "tool_calls": [
        {
            "id": "call_weather",
            "name": "get_mock_weather",
            "arguments": {"city": "Tokyo"},
        }
    ],
}
```

becomes a Responses input item:

```python
{
    "type": "function_call",
    "call_id": "call_weather",
    "name": "get_mock_weather",
    "arguments": '{"city": "Tokyo"}',
}
```

The Tool observation:

```python
{
    "role": "tool",
    "tool_call_id": "call_weather",
    "content": "18.0",
}
```

becomes:

```python
{
    "type": "function_call_output",
    "call_id": "call_weather",
    "output": "18.0",
}
```

This is why the Runtime must preserve Action and Observation structure rather than flattening everything into anonymous text.

---

## 8. What `OpenAIResponsesModel.generate()` actually does

The core of `src/tiny_agent/models/openai.py` is conceptually:

```python
response = self.client.responses.create(
    model=self.model,
    input=self._to_openai_input(messages),
    tools=[self._to_openai_tool(tool) for tool in tools],
    reasoning={"effort": self.reasoning_effort},
    parallel_tool_calls=self.parallel_tool_calls,
)

tool_calls = self._extract_tool_calls(response)

if tool_calls:
    return ModelResponse(tool_calls=tool_calls)

if response.output_text:
    return ModelResponse(final_answer=response.output_text)

raise RuntimeError("invalid provider response")
```

Three steps:

```text
Tiny-Agent -> provider request
provider inference
provider response -> Tiny-Agent ModelResponse
```

No Tool execution. No Agent loop. No `max_steps`.

That absence is evidence that the responsibility boundary is working.

---

## 9. Protocol errors belong at the Adapter boundary

Invalid JSON arguments:

```text
{city: Tokyo}
```

should fail before a Tool handler is invoked.

Valid JSON with the wrong shape:

```json
["Tokyo"]
```

should also be rejected because function-call arguments must be an object.

A useful responsibility rule is:

```text
provider wire-format problem -> Adapter
Tool-argument policy/schema problem -> Runtime/Tool validation
handler execution failure -> Tool execution layer
```

Recognize failures as close as possible to the layer that understands them.

---

## 10. Serial dependencies vs multiple ToolCalls in one turn

Travel conversion is serial:

```text
get_mock_weather(Tokyo)
        ↓
      18°C
        ↓
celsius_to_fahrenheit(18)
```

The second call cannot be formed until the first observation exists.

By contrast, Tokyo and Paris weather can be independent:

```text
call_A -> get_weather(Tokyo)
call_B -> get_weather(Paris)
```

A model may propose both in one turn.

But Tiny-Agent Stage 01 still executes handlers sequentially:

```python
for call in response.tool_calls:
    execute(call)
```

So:

```text
multiple ToolCalls in one model decision
!=
concurrent Python execution
```

Physical concurrency is a separate Runtime concern.

---

## 11. Running the real travel assistant

The live Stage 01 example becomes intentionally small:

```python
model = OpenAIResponsesModel(
    model="gpt-5.6-luna",
    reasoning_effort="none",
)

runtime = AgentRuntime(
    model=model,
    tools=travel_tools,
    max_steps=6,
)

result = runtime.run(
    "Use the course mock Tokyo weather, convert it to Fahrenheit, "
    "and explain the temperature."
)
```

A reasonable trajectory is:

```text
ACTION      get_mock_weather({'city': 'Tokyo'})
OBSERVATION {"temperature_c":18.0,"condition":"cloudy"}
ACTION      celsius_to_fahrenheit({'temperature_c':18.0})
OBSERVATION 64.4
FINAL       The course's mock Tokyo weather is 18°C, about 64.4°F ...
```

Exact wording and trajectory are model decisions. Separate stochastic model behavior from deterministic Runtime policy when debugging.

---

## 12. What about Qwen?

Stage 00 already demonstrated Qwen through Alibaba Cloud Model Studio's OpenAI-compatible API.

Stage 01 now has the stronger boundary:

```python
class Model(Protocol):
    def generate(...) -> ModelResponse:
        ...
```

Whether you implement `OpenAIResponsesModel`, `QwenResponsesModel`, a configurable OpenAI-compatible Adapter, or a local-model Adapter, the following should not change:

```text
AgentRuntime
ToolRegistry
Tool handlers
max_steps semantics
trajectory semantics
```

Provider-specific capabilities belong in Adapter/configuration layers, not scattered `if provider == ...` branches inside the core loop.

---

## 13. Unit-test the Adapter with a fake client

Many Adapter behaviors are deterministic:

```text
Tool-schema translation
JSON argument decoding
call_id preservation
multiple function-call extraction
unsupported-role rejection
empty-response failure
```

So `OpenAIResponsesModel` accepts an injected client for tests.

Run:

```bash
pytest -q \
  tests/test_openai_adapter.py \
  tests/test_openai_adapter_edges.py
```

These tests do not ask whether GPT-5.6 plans correctly. They verify that our protocol translator obeys its contract.

---

## 14. Why Stage 01 stays mostly stateless at the provider layer

Responses API supports provider-managed continuation mechanisms such as `previous_response_id`.

Stage 00 introduced that idea. Stage 01 intentionally focuses on Runtime state, transcript translation, and Tool-call correlation.

Mixing provider sessions, persisted reasoning items, checkpoint/resume, and Runtime state here would make ownership harder to see.

A useful teaching principle is:

> **Introduce an abstraction when it can be compared cleanly, not merely because the API offers it.**

Later stages compare transcript history, provider conversation state, checkpoints, thread state, and long-term memory explicitly.

---

## 15. Think of the Adapter as an edge translator

```text
                 AgentRuntime
                      │
                Model Protocol
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
 OpenAIResponsesModel       Other Adapter
          │                       │
          ▼                       ▼
 OpenAI Responses API       Qwen / local / ...
```

Runtime vocabulary:

```text
ToolCall
ModelResponse
Observation
```

Provider vocabulary:

```text
function_call
function_call_output
response.output
call_id
```

The Adapter lets the two worlds communicate without letting either side take over the other's responsibilities.

Next we ask the uncomfortable but necessary question: **if this architecture is conceptually sound, why is it still far from production-ready?**

---

## References

- OpenAI Function Calling: <https://developers.openai.com/api/docs/guides/function-calling>
- OpenAI Responses API: <https://developers.openai.com/api/reference/resources/responses>
- OpenAI Python SDK: <https://github.com/openai/openai-python>
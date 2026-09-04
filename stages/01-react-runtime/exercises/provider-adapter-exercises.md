# Provider Adapter Exercises: Prove That Switching Models Does Not Rewrite the Runtime

> Language: English | [简体中文](provider-adapter-exercises.zh-CN.md)

These exercises focus on one invariant:

> **Provider-specific protocol details should stop at the Adapter boundary instead of leaking into `AgentRuntime`.**

If an exercise seems to require editing `AgentRuntime.run()`, first ask whether you are adding a truly provider-neutral Runtime capability or merely teaching the Runtime one vendor's wire format.

---

## Exercise 1 — Translate one protocol turn by hand

Given the Tiny-Agent transcript:

```python
[
    {"role": "user", "content": "Get the course mock Tokyo weather"},
    {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_weather",
                "name": "get_mock_weather",
                "arguments": {"city": "Tokyo"},
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "call_weather",
        "name": "get_mock_weather",
        "content": "18.0",
    },
]
```

Write the equivalent Responses API input items by hand.

Then answer:

1. Which field correlates the Tool result with the original function call?
2. Why is Tool name not sufficient correlation?
3. Why does Tiny-Agent store arguments as a `dict` while the provider wire format may use JSON text?
4. If a future provider exposes a completely different ToolCall shape, which layer should change?

---

## Exercise 2 — Implement `_extract_tool_calls` yourself

Without reading `src/tiny_agent/models/openai.py`, implement:

```python
def extract_tool_calls(response) -> list[ToolCall]:
    ...
```

Assume `response.output` may contain messages, reasoning items, and multiple function calls.

Requirements:

- extract only `function_call` items;
- decode `arguments` with `json.loads`;
- reject malformed JSON explicitly;
- reject decoded values that are not dictionaries;
- preserve `call_id`;
- extract every function call in the turn.

Write at least four deterministic tests.

---

## Exercise 3 — Malformed JSON must fail before Tool execution

Return provider arguments:

```text
{city: Tokyo}
```

instead of:

```json
{"city": "Tokyo"}
```

Verify:

```text
Adapter fails
Runtime does not execute the Tool
handler is never called
```

Explain why this is an Adapter/protocol error rather than a Tool-handler failure.

---

## Exercise 4 — Valid JSON, wrong shape

Use:

```json
["Tokyo"]
```

`json.loads` succeeds, but function arguments should be an object.

Verify the Adapter still rejects the response.

This exercise separates:

```text
syntactically valid JSON
!=
valid normalized ToolCall arguments
```

---

## Exercise 5 — Prove `generate()` performs one model turn

Build a FakeClient and count calls to:

```text
client.responses.create
```

Call:

```python
model.generate(messages, tools)
```

exactly once and assert that exactly one provider request occurs.

Then make the fake provider return a ToolCall and verify that the Adapter does not execute the Tool or call the provider again. It only returns `ModelResponse(tool_calls=[...])`.

Explain why hiding the full loop in the Adapter makes permissions, tracing, and checkpointing harder.

---

## Exercise 6 — Tool-schema translation

Translate this Tiny-Agent Tool schema into an OpenAI function Tool definition:

```python
{
    "name": "get_mock_weather",
    "description": "Return course mock weather for one city.",
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

Then remove `additionalProperties=False` and discuss:

1. What value does provider-side strict schema support provide?
2. Why should the Runtime eventually validate locally as well?
3. How are Tool design, Adapter translation, and Runtime validation different concerns?

---

## Exercise 7 — Replace OpenAI with Qwen without touching the Runtime

Stage 00 demonstrated Qwen through an OpenAI-compatible API.

Repeat the integration under a stricter rule: do not modify:

```text
AgentRuntime
ToolRegistry
Tool handlers
```

You may add or configure only:

```text
Qwen Adapter
provider configuration
provider-specific tests
```

The contract remains:

```python
class Model(Protocol):
    def generate(self, messages, tools) -> ModelResponse:
        ...
```

Document which provider differences the Adapter absorbs and which differences, if any, represent a real provider-neutral Runtime capability.

If you put `if provider == "qwen"` inside `AgentRuntime.run()`, justify it.

---

## Exercise 8 — Compatibility is not provider identity

Even if OpenAI and Qwen can both be called with a similar `client.responses.create(...)` shape, list at least eight ways they can still differ:

```text
credentials
base_url
model IDs
supported parameters
Tool Calling details
Structured Output behavior
errors
rate limits
usage metadata
provider extensions
```

Explain why OpenAI-compatible APIs reduce Adapter implementation cost without making the Adapter architecture layer unnecessary.

---

## Exercise 9 — Serial dependency vs same-turn multiple calls

Scenario A:

```text
get_mock_weather(Tokyo)
        ↓
      18°C
        ↓
celsius_to_fahrenheit(18)
```

Scenario B:

```text
get_mock_weather(Tokyo)
get_mock_weather(Paris)
```

Draw the dependency graphs and explain:

1. why A normally needs multiple model turns;
2. why B may be proposed as multiple ToolCalls in one turn;
3. what `parallel_tool_calls=True` actually permits;
4. why it does not automatically make Python handlers concurrent.

---

## Exercise 10 — FakeClient unit tests vs live integration tests

Design two suites.

### Unit tests with FakeClient

Cover:

```text
request translation
Tool-schema translation
JSON decoding
call_id preservation
multiple calls
unsupported roles
empty provider response
```

### Live integration tests

Cover:

```text
real provider compatibility
reasonable Tool selection
end-to-end task completion
latency / usage sanity
```

Explain why neither suite replaces the other.

---

## Completion Challenge — One Runtime, two providers

Use the same:

```text
AgentRuntime
ToolRegistry
travel Tools
```

and switch only provider configuration between OpenAI and Qwen.

Both runs should handle:

```text
get course mock Tokyo weather
-> obtain Celsius
-> convert to Fahrenheit with a Tool
-> explain final result
```

Record both trajectories and compare Tool selection, arguments, step count, final answer, and provider latency.

Finish with one architecture question:

> **Which differences are ordinary provider substitution, and which differences are significant enough to justify evolving the core Runtime contract?**

If you can answer that clearly, you understand the Adapter boundary rather than merely knowing how to write a wrapper class.
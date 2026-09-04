# 02 — From a Hand-Written Loop to Core Runtime Architecture: Why Does Each Layer Exist?

> Language: English | [简体中文](02-runtime-architecture.zh-CN.md)

The previous chapter established that once model decisions depend on Tool observations, the application needs an explicit loop.

Now ask a more practical question:

> **Should that loop remain one giant function forever?**

At first, code like this is perfectly reasonable:

```python
while True:
    response = openai_client.responses.create(...)

    if response_has_tool_call(response):
        if tool_name == "get_mock_weather":
            result = get_mock_weather(...)
        elif tool_name == "celsius_to_fahrenheit":
            result = celsius_to_fahrenheit(...)

        messages.append(...)
        continue

    return response.output_text
```

Then you add another provider, more Tools, schemas, tests, error handling, and stopping rules. Suddenly the same function knows provider wire formats, Tool routing, Python execution, transcript construction, and loop policy.

That is not merely “messy code.” Responsibilities have begun to contaminate one another.

This chapter extracts the architecture one pain point at a time.

---

## 1. The Runtime should not understand provider Response objects

Suppose the loop contains:

```python
for item in response.output:
    if item.type == "function_call":
        name = item.name
        arguments = json.loads(item.arguments)
```

Now the Runtime knows the OpenAI Responses API format.

A provider with a different response shape forces Runtime changes.

So before writing the Runtime, give it an internal vocabulary.

---

## 2. Define the Runtime's own `ToolCall`

```python
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
```

`name` identifies the capability. `arguments` contains the proposed inputs. `id` is the correlation identifier for this specific call.

If one model turn proposes:

```text
call_A -> get_mock_weather(Tokyo)
call_B -> get_mock_weather(Paris)
```

Tool name alone cannot correlate each result with the correct request. Provider `call_id` therefore becomes Tiny-Agent `ToolCall.id`.

---

## 3. Normalize one model decision

The Runtime does not want to understand OpenAI Response, Qwen Response, and test fixtures separately. It wants to know one thing:

> **Does this turn propose more actions, or is the task complete?**

```python
from dataclasses import field


@dataclass(slots=True)
class ModelResponse:
    final_answer: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
```

Now the boundary is:

```text
OpenAI Response ──┐
Qwen Response ────┼──> Adapter ──> ModelResponse
Fake Model ───────┘
                              │
                              ▼
                         AgentRuntime
```

Normalization does not mean pretending every provider is identical. It means the core Runtime depends only on the shared semantics it actually needs.

---

## 4. Why `Model` is a Protocol

A Runtime typed directly against `OpenAIResponsesModel` is still provider-coupled.

Instead:

```python
from typing import Protocol


class Model(Protocol):
    def generate(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> ModelResponse:
        ...
```

The Runtime asks for one contract:

```text
messages + Tool schemas
        ↓
one normalized ModelResponse
```

The implementation can be OpenAI, Qwen, a local model, or a deterministic FakeModel.

That immediately gives us provider substitution and deterministic Runtime tests.

---

## 5. A Tool is not just a callable

Python may know how to execute:

```python
def get_mock_weather(city: str) -> dict:
    ...
```

The model does not see the Python function. It sees a language-and-schema interface:

```text
Model-facing                   Runtime-facing
------------                   --------------
name                           Python handler
description                    execution
parameter schema               error boundary
```

Tiny-Agent binds those two sides:

```python
@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
```

That distinction explains why Tool-interface design later deserves its own advanced lesson.

---

## 6. Why `ToolRegistry` is more than removing `if` statements

With two Tools, this is tempting:

```python
if call.name == "get_mock_weather":
    ...
elif call.name == "celsius_to_fahrenheit":
    ...
```

But then the Agent loop owns registration, name uniqueness, schema export, lookup, and execution.

A Registry moves those responsibilities behind one boundary:

```python
class ToolRegistry:
    def register(self, tool: Tool) -> None:
        ...

    def schemas(self) -> list[dict]:
        ...

    def execute(self, name: str, arguments: dict) -> Any:
        ...
```

Later, the same execution boundary becomes a natural place for permissions, approval, tracing, timeouts, Tool metadata, and MCP-discovered capabilities.

So `ToolRegistry` is not cosmetic. It defines how model-visible capabilities enter real execution.

---

## 7. Now `AgentRuntime` becomes small

Once the boundaries exist, the loop is almost boring:

```python
class AgentRuntime:
    def __init__(self, model, tools, max_steps=8):
        self.model = model
        self.tools = tools
        self.max_steps = max_steps

    def run(self, user_input: str):
        messages = [{"role": "user", "content": user_input}]

        for step in range(1, self.max_steps + 1):
            response = self.model.generate(
                messages,
                self.tools.schemas(),
            )

            if response.tool_calls:
                for call in response.tool_calls:
                    observation = self.tools.execute(
                        call.name,
                        call.arguments,
                    )
                    # record action + observation
                continue

            if response.final_answer is not None:
                return response.final_answer

            raise RuntimeError("invalid model response")

        raise RuntimeError("max_steps exceeded")
```

This is an important lesson: once responsibilities are separated, the core Agent loop is not mystical. Production frameworks become large because they add persistence, retries, approval, tracing, streaming, checkpointing, and other capabilities around this control skeleton.

---

## 8. The real loop must preserve Action and Observation structure

When the model proposes ToolCalls, Tiny-Agent records the action:

```python
messages.append(
    {
        "role": "assistant",
        "tool_calls": [
            {
                "id": call.id,
                "name": call.name,
                "arguments": call.arguments,
            }
            for call in response.tool_calls
        ],
    }
)
```

Then each result is recorded with the same correlation identifier:

```python
messages.append(
    {
        "role": "tool",
        "tool_call_id": call.id,
        "name": call.name,
        "content": observation,
    }
)
```

This structure lets the next provider turn reconstruct which `function_call_output` belongs to which model request.

A naked string such as `"18.0"` is not enough.

---

## 9. Multiple ToolCalls are not concurrent execution

A model may return:

```python
ModelResponse(tool_calls=[call_a, call_b])
```

The Stage 01 Runtime currently executes:

```python
for call in response.tool_calls:
    execute(call)
```

So distinguish:

```text
multiple ToolCalls in one model decision
!=
concurrent Python execution
```

Physical concurrency requires async tasks, cancellation, concurrency limits, partial-failure handling, and result aggregation. Those belong to later production stages.

---

## 10. Why `AgentResult` keeps the trajectory

Returning only the final text hides important behavior.

Tiny-Agent therefore returns:

```python
@dataclass(slots=True)
class AgentResult:
    output: str
    steps: int
    messages: list[dict[str, Any]]
```

Two Agents can produce the same final number while taking very different trajectories. One may use the required Tools correctly; another may ignore them and guess.

This is the first hint that Agent evaluation must eventually inspect trajectories, not only final answers.

---

## 11. Deterministic Runtime tests with `ScriptedModel`

The real tests use the same idea as the stage demo:

```python
class ScriptedModel:
    def generate(self, messages, tools):
        if first_turn:
            return ModelResponse(tool_calls=[...])

        assert messages[-1]["role"] == "tool"
        return ModelResponse(final_answer="...")
```

Run:

```bash
pytest -q tests/test_runtime.py tests/test_runtime_edges.py
```

These tests verify Runtime promises such as Tool execution, Observation insertion, step counting, maximum-step failure, safe Tool-failure observation, and invalid empty responses.

The assertions are executable documentation of the Runtime contract.

---

## 12. Teaching snapshot vs evolving library

Read the small version first:

```text
stages/01-react-runtime/code/minimal_react_runtime.py
```

Then compare it with:

```text
src/tiny_agent/types.py
src/tiny_agent/tool.py
src/tiny_agent/runtime.py
src/tiny_agent/models/openai.py
```

The library has already been extended by later stages: async Tool execution and safer error observations are examples.

The question is not “why are they not identical?” The useful question is:

> **Which boundaries are Stage 01 invariants, and which capabilities were layered on later?**

---

## 13. The dependency direction is the real architecture lesson

The intended direction is:

```text
              AgentRuntime
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
      Model             ToolRegistry
        ▲                   │
        │                   ▼
 Provider Adapter       Tool handler
```

Not:

```text
AgentRuntime
  ├── import OpenAI
  ├── if Qwen ...
  ├── if tool == weather ...
  ├── if tool == search ...
  └── provider-specific parsing ...
```

A practical architecture test is:

> **If adding a provider requires editing `AgentRuntime.run()`, the model boundary is probably wrong.**

The next chapter connects OpenAI Responses API to this boundary and follows the full translation from provider `function_call` to Tiny-Agent `ToolCall` and back.
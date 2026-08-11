# Core Runtime Architecture

## 1. Why architecture matters this early

A toy Agent can fit in one file, but educational code becomes much more useful when the responsibility of each component is explicit.

Tiny-Agent separates four core concerns:

```text
Model interface
Tool interface + registry
Normalized response types
Agent runtime
```

This is intentionally small. We are not trying to reproduce a large framework. We are defining the minimum stable boundaries that later features can build on.

## 2. High-level architecture

```text
                    +-------------------+
                    |       User        |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    |   AgentRuntime    |
                    +----+---------+----+
                         |         |
                         |         |
                         v         v
                  +----------+   +--------------+
                  |  Model   |   | ToolRegistry |
                  +----+-----+   +------+-------+
                       |                |
                       v                v
                ModelResponse        Tool handler
                /           \           |
        tool calls        final          v
             |           answer      observation
             +---------------+-----------+
                             |
                             v
                       next runtime step
```

## 3. Why `Model` is an interface

The Agent runtime should depend on a small internal contract rather than directly on a provider SDK.

Conceptually:

```python
class Model(Protocol):
    def generate(self, messages, tools) -> ModelResponse:
        ...
```

Provider adapters then sit behind the interface:

```text
                    +----------------+
AgentRuntime -----> | Model protocol |
                    +-------+--------+
                            ^
             +--------------+--------------+
             |              |              |
        OpenAIAdapter   QwenAdapter   FakeModel
```

Benefits:

- provider switching does not rewrite the runtime;
- tests can use deterministic fake models;
- provider-specific parsing stays isolated;
- the runtime has a stable internal vocabulary.

## 4. Why normalize model responses

Provider SDKs can represent tool calls differently. Core runtime code should not need to know those formats.

Tiny-Agent converts provider responses into internal types such as:

```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class ModelResponse:
    final_answer: str | None
    tool_calls: list[ToolCall]
```

This creates a normalization boundary:

```text
Provider response
      |
      v
Provider adapter
      |
      v
ModelResponse
      |
      v
AgentRuntime
```

## 5. Why a tool is more than a callable

A tool has a model-facing contract and a runtime-facing implementation.

```text
Model-facing                         Runtime-facing
------------                         --------------
name                                 callable
description                          validation
parameter schema                     execution
                                     error handling
```

A registry maps the model-visible name to the runtime implementation:

```python
{
    "calculator": calculator_tool,
    "search": search_tool,
}
```

The runtime should never trust the model to invoke arbitrary Python names directly.

## 6. Why use a `ToolRegistry`

Without a registry, a naive runtime may grow into this:

```python
if tool_name == "calculator":
    ...
elif tool_name == "weather":
    ...
elif tool_name == "search":
    ...
```

This couples routing, validation, schema generation, and execution to the Agent loop.

A registry centralizes:

- registration;
- duplicate-name checks;
- schema export;
- lookup;
- execution.

Later it can become the natural integration point for:

- permissions;
- tracing;
- timeouts;
- MCP-discovered tools;
- tool metadata;
- approval policies.

## 7. Runtime responsibility

The runtime is not merely a `while` loop. Even in the minimal version it owns policy.

Current responsibilities:

```text
initialize task messages
call model
interpret normalized response
execute tools
append observations
count steps
stop on final answer
stop on step budget
surface contract violations
```

Future responsibilities will include:

```text
state persistence
retry policies
human approval
permissions
tracing
evaluation hooks
streaming
cancellation
cost budgets
```

## 8. Why messages are still visible in `AgentResult`

Returning the execution messages is useful because they form the simplest trace of what happened:

```text
user input
assistant tool proposal
tool observation
assistant next proposal
...
final answer
```

This is not yet full observability, but it gives tests and developers an inspectable execution trajectory.

Later we will introduce explicit trace/span objects rather than relying only on conversation messages.

## 9. Why tool exceptions may become observations

The current runtime catches a tool exception and converts it to a string observation.

This demonstrates an important idea: external failures may be recoverable environment feedback.

However, a production runtime should eventually classify errors rather than catch every exception indiscriminately.

A future hierarchy might look like:

```text
ToolError
├── InvalidArguments
├── RetryableToolError
├── TimeoutError
├── PermissionDenied
└── FatalToolError
```

Different classes should have different policies.

## 10. Deterministic unit tests

A fake model can produce a scripted sequence:

```text
turn 1 -> calculator tool call
turn 2 -> final answer
```

This allows the runtime to be tested without:

- network access;
- API keys;
- sampling randomness;
- token cost;
- provider outages.

This is crucial because an Agent project needs both:

### Unit tests

Deterministic tests of runtime behavior.

### Integration/evaluation tests

Tests using real models to measure actual Agent quality.

They are not substitutes for each other.

## 11. Design rule for the next exercise

A real provider adapter must satisfy the existing `Model` interface **without modifying `AgentRuntime`**.

If adding a provider requires rewriting the runtime, the abstraction boundary is wrong.

## 12. Key takeaways

- Keep provider-specific SDK code outside the core runtime.
- Normalize provider responses into internal types.
- Treat the tool registry as an execution boundary.
- Let the runtime own iteration and policy.
- Preserve deterministic unit testing even when the real system uses stochastic LLMs.
- Build interfaces that future stages can extend without erasing the minimal implementation.

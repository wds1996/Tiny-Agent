# Function Calling / Tool Calling

## 1. What function calling really is

Function calling is frequently described as "the LLM calls a function." That phrasing is convenient, but technically misleading.

A language model normally does **not** execute your local Python function, access your database, or send an HTTP request by itself. Instead, the application provides a machine-readable description of available tools. The model may then generate a structured request indicating which tool it wants to use and with what arguments.

Conceptually:

```text
Available tool:
get_weather(city: string)

User:
What is the weather in Tokyo?

Model output:
ToolCall(
    name="get_weather",
    arguments={"city": "Tokyo"}
)
```

The **application runtime** receives that request and decides what to do next.

## 2. The four layers of a tool

A useful mental model separates four things that are often mixed together.

### 2.1 Tool name

```text
get_weather
```

The name is part of the interface the model sees.

### 2.2 Tool description

```text
Get the current weather for a city.
```

Descriptions matter because tool selection is partly a language-understanding problem. A vague or overlapping description can cause the model to choose the wrong tool.

### 2.3 Argument schema

```json
{
  "type": "object",
  "properties": {
    "city": {"type": "string"}
  },
  "required": ["city"]
}
```

The schema defines the shape of the proposed action.

### 2.4 Executable handler

```python
def get_weather(city: str) -> str:
    ...
```

This function belongs to the application/runtime side. The model does not need the Python source code in order to propose the tool call.

## 3. Tool schema and executable function are different objects

This separation is essential:

```text
             MODEL SIDE
                |
                v
     name + description + schema
                |
          proposes action
                |
                v
             RUNTIME
                |
                v
        executable handler
```

Why keep them separate?

Because the same logical tool may be exposed through:

- a local Python function;
- an HTTP API;
- a database driver;
- a remote worker;
- an MCP server;
- a sandboxed execution environment.

The model-facing contract can remain stable while the execution mechanism changes.

## 4. A complete function-calling turn

A typical sequence is:

```text
1. Application sends user message + tool schemas to model.
2. Model proposes a tool call.
3. Runtime validates the requested tool and arguments.
4. Runtime executes the tool.
5. Runtime converts the result into a tool observation.
6. Application sends the observation back to the model.
7. Model produces the next decision or final answer.
```

The important point is Step 6.

A tool result is not automatically known to the model merely because your Python process executed a function. The observation must become part of the next model context.

## 5. Why tool results must go back to the model

Suppose the model proposes:

```text
calculator(a=23, b=17)
```

The runtime computes:

```text
391
```

The model cannot reliably continue from the real result unless the application supplies that result in the next turn.

```text
User: calculate 23 * 17
Assistant: tool_call calculator(...)
Tool: 391
Assistant: 23 * 17 = 391
```

This creates the first important feedback loop in Agent systems.

## 6. Multiple tool calls

A task may require several external actions:

```text
User
  |
  v
Model -> weather("Tokyo")
  ^            |
  |            v
  +------ 31 C observation
  |
  +-> calculator(celsius_to_fahrenheit)
               |
               v
             87.8 F
               |
               v
             Model
               |
               v
          Final answer
```

At this point the application is no longer handling one isolated function call. It is managing an iterative tool-use process.

That is the bridge from function calling to an Agent loop.

## 7. Tool selection is a model decision, execution is a runtime decision

This distinction should be memorized:

> **LLM proposes; runtime executes.**

The runtime should remain authoritative over:

- whether a requested tool exists;
- whether the caller has permission;
- whether arguments are valid;
- whether approval is required;
- whether the tool may run in the current environment;
- timeouts;
- retries;
- rate limits;
- logging;
- sandboxing.

A model-generated tool call is therefore a **proposal**, not an unconditional command.

## 8. Tool-call validation

Never assume that generated arguments are correct.

Possible failures:

```text
Unknown tool
Missing required argument
Wrong argument type
Invalid enum value
Unsafe path
Out-of-range number
Unauthorized operation
```

A robust runtime validates the call before executing it.

Later Tiny-Agent stages will introduce explicit error classes, permissions, retries, approval gates, and sandbox concepts.

## 9. Tool errors are useful observations

If a tool fails, one option is to crash the whole program. A more Agent-friendly design is often to represent a recoverable error as an observation:

```text
ToolError: city must be a non-empty string
```

The model may then:

- repair arguments;
- select a different tool;
- ask the user for missing information;
- explain that the operation failed.

Not every error should be recoverable, but external action failures are part of the environment the Agent must learn to handle.

## 10. Function calling is not yet a full production Agent

A minimal tool loop gives us:

```text
model -> action -> observation -> model
```

But a production Agent still needs answers to questions such as:

- When does the loop stop?
- How many steps may it use?
- How is state represented?
- How are errors classified?
- How do we persist/resume execution?
- Which actions require approval?
- How do we trace decisions?
- How do we evaluate success?
- How do we limit cost and latency?

Stage 01 introduces the first explicit Agent runtime abstraction.

## 11. Function calling vs structured output

A useful comparison:

| Concept | Main purpose |
|---|---|
| Natural-language output | communicate with humans |
| Structured output | return machine-readable data |
| Function/tool calling | propose an external action |

A tool call is usually structured, but not every structured output is a tool call.

## 12. Key takeaways

- The model normally does not execute your Python function.
- The model sees a tool interface; the runtime owns the implementation.
- Tool descriptions and schemas are part of the model-facing contract.
- Generated arguments must be validated.
- Tool results must be returned to the model as observations.
- Multiple tool-use turns naturally lead to the Agent loop.
- Tool execution is a security and reliability boundary controlled by the runtime.

## Review questions

1. What exactly does a model generate when it "calls" a tool?
2. Why is a tool handler not the same thing as a tool schema?
3. Who decides whether a dangerous tool call is actually executed?
4. Why does the model need the tool result in a later message?
5. What additional runtime concerns appear once tool calls can repeat?

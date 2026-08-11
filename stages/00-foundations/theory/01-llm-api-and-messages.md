# LLM APIs and Message-Based Interaction

## 1. Why start here?

An Agent is not a special type of model. Most modern Agent systems are ordinary language models embedded inside an application runtime that repeatedly sends messages, receives model outputs, executes external actions, and feeds observations back into the next model call.

Before studying Agents, it is therefore important to understand the boundary between **the model** and **the application**.

## 2. The basic request-response model

A simplified LLM application looks like this:

```text
Application -> model(messages) -> model output
```

The model normally receives a sequence of messages rather than a single plain string. Conceptually:

```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain tool calling."},
]
```

The application serializes these messages into the provider-specific API format, sends them to the model provider, and receives a response.

## 3. Common message roles

### `system`

Defines high-level behavior, constraints, identity, or task instructions.

Examples:

- answer as a programming tutor;
- use concise explanations;
- do not perform a destructive action without approval.

The exact semantics vary by provider, but the architectural idea is stable: it is application-provided context with special instructional importance.

### `user`

Represents user input.

### `assistant`

Represents previous model output. In a multi-turn interaction, previous assistant messages are usually included so the model can continue from the current conversational state.

### `tool`

Represents an observation returned after an external tool has been executed.

This role becomes especially important for Agents because it closes the loop between model decision and environment feedback.

## 4. The model is stateless unless the application supplies state

A common misconception is that an API model permanently remembers the previous call. In most application designs, the model sees whatever context the application sends during the current request.

For example:

```text
Call 1:
[user: "My project is Tiny-Agent"]

Call 2:
[user: "What is my project called?"]
```

If Call 2 does not include the earlier information through conversation history, memory retrieval, provider-managed session state, or another state mechanism, the application should not assume the model can reconstruct it.

This leads to an important Agent engineering principle:

> Conversation history, task state, tool observations, and long-term memory are runtime concerns, not magical hidden properties of the LLM.

## 5. Model provider vs Agent runtime

A robust architecture separates the provider-specific client from the Agent runtime.

```text
Agent Runtime
     |
     v
Model Interface
  /   |    \
OpenAI Qwen Claude
```

Why?

Because provider APIs differ in:

- request objects;
- response objects;
- tool-call representations;
- streaming events;
- error types;
- token accounting;
- model names;
- structured-output features.

If provider-specific code is scattered throughout the Agent runtime, every provider change becomes a runtime rewrite.

A better pattern is an adapter:

```python
class Model:
    def generate(self, messages, tools):
        ...
```

Each provider converts its own response into a normalized internal representation.

## 6. Context is application data

The model may receive several kinds of context:

```text
system instructions
conversation history
retrieved documents
tool outputs
current task state
user preferences
workflow metadata
```

These should not all be treated as the same thing.

Later stages of Tiny-Agent will separate:

- current context;
- short-term/session state;
- long-term memory;
- retrieved evidence;
- runtime metadata.

## 7. Why this matters for Agents

Suppose an Agent needs to answer:

> What is the weather in Tokyo, and what is that temperature in Fahrenheit?

The LLM does not inherently have a reliable live weather sensor or Python runtime. The application may need to:

1. send the user question to the model;
2. receive a request to call a weather tool;
3. execute the tool;
4. append the returned weather as a tool observation;
5. call the model again;
6. perhaps execute a calculator tool;
7. return the final answer.

The important unit is no longer one LLM request. It is a **runtime-controlled sequence of LLM requests and environment interactions**.

## 8. Key takeaways

- An Agent usually builds on an ordinary LLM API.
- Models consume context supplied by an application runtime.
- Message roles help structure that context.
- Tool observations are new model inputs, not hidden side effects.
- Provider-specific API objects should be isolated behind an interface.
- Runtime state and model inference are different responsibilities.

## Review questions

1. Why should an Agent runtime avoid depending directly on one provider's response class?
2. Who owns conversation history: the LLM or the application?
3. Why is a tool result normally sent back as another model input?
4. What kinds of information belong in runtime state rather than the model itself?

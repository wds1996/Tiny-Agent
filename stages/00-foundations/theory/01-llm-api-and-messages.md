# 01 — Before You Build an Agent: Start with One LLM API Call

> Language: English | [简体中文](01-llm-api-and-messages.zh-CN.md)

Many Agent tutorials begin with `create_agent(...)`.

That is convenient for getting a demo running, but poor for building a mental model. If the first abstraction hides requests, messages, model outputs, and conversation state, it becomes easy to mistake framework behavior for model behavior.

So this chapter intentionally does something plain: **make one OpenAI model call and take it apart.**

Once one call is clear, Tool Calling and Agent loops have somewhere concrete to attach.

---

## 1. Run the smallest complete example first

Ask a question that is directly relevant to this repository:

> Why should an Agent not simply be understood as an LLM?

Using the current OpenAI Responses API:

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.6-luna",
    instructions=(
        "You are a patient AI engineering teacher. "
        "Explain concepts concisely but accurately."
    ),
    input="Why should an Agent not simply be understood as an LLM?",
)

print(response.output_text)
```

Set an API key before running it:

```bash
export OPENAI_API_KEY="your API key"
```

The runnable version lives at:

[`../code/first_openai_call.py`](../code/first_openai_call.py)

### Expected output

Model wording is not deterministic, so expect the meaning rather than identical text:

```text
An LLM performs inference over the context it receives.
An Agent adds an application runtime around the model: Tools, state,
execution flow, permissions, stopping rules, and other control logic.
The model can propose a next step, while the application decides what
actually executes.
```

Before reading further, ask three questions:

1. What did `OpenAI()` create?
2. What did `responses.create(...)` send?
3. What is `response.output_text` extracting?

---

## 2. `OpenAI()` is a client, not the model

```python
client = OpenAI()
```

This creates an **API client**.

Its job is roughly:

```text
load credentials
    ↓
construct an HTTP request
    ↓
send it to the OpenAI API
    ↓
receive an HTTP response
    ↓
expose that response as Python objects
```

The Python client object is not performing the language-model inference.

A useful analogy: a food-delivery app is not the restaurant kitchen. The app transports the order and the result; the kitchen performs the cooking.

The same distinction will matter for Agents. An Agent Runtime is not the LLM either. It organizes, invokes, and constrains model inference.

---

## 3. Why should a provider-specific client stay out of the Agent Runtime?

At this point it is easy to write code that works but does not age well:

```python
from openai import OpenAI


def answer(prompt: str) -> str:
    client = OpenAI()
    response = client.responses.create(
        model="gpt-5.6-luna",
        input=prompt,
    )
    return response.output_text
```

There is nothing inherently wrong with that if the program will always use only OpenAI.

The design problem appears when someone asks:

> “Can we evaluate Qwen too?”

### Call Qwen with the same OpenAI SDK style

Alibaba Cloud Model Studio currently exposes an OpenAI-compatible Responses API, so Qwen can still be called with the OpenAI Python SDK:

```python
import os
from openai import OpenAI

qwen_client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url=os.environ["DASHSCOPE_BASE_URL"],
)

response = qwen_client.responses.create(
    model="qwen3.8-max",
    instructions="You are a patient AI engineering teacher.",
    input="Why should an Agent Runtime not be tied to one model provider?",
)

print(response.output_text)
```

`DASHSCOPE_BASE_URL` should point to the OpenAI-compatible endpoint for the same Model Studio workspace and region as the API key. A current official endpoint shape is:

```text
https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

Other regions use different endpoints, and API keys are region-bound, so the example deliberately keeps the base URL in configuration rather than embedding it inside Runtime logic.

A reasonable output would be conceptually similar to:

```text
An Agent Runtime should depend on a stable internal model interface rather
than one provider's concrete Response type. Then switching providers changes
an edge adapter instead of rewriting Tool loops, state, and control logic.
```

You might now ask:

> “If the OpenAI and Qwen code looks this similar, why do I still need an Adapter?”

That is exactly the important question.

### OpenAI-compatible does not mean behaviorally identical

Compatibility reduces migration cost, but provider-specific differences remain:

```text
different credentials
different base_url
different model IDs
different supported parameters and features
possible differences in Tool / Structured Output behavior
possible differences in usage and extension fields
different errors, rate limits, and retry semantics
future providers may not implement the OpenAI protocol at all
```

Alibaba Cloud's own Responses API documentation explicitly notes that its compatibility layer still differs from OpenAI in supported parameters, functionality, and behavior.

The durable architecture therefore isolates the provider boundary:

```text
                    provider-specific world
                 ┌──────────────────────────┐
OpenAI SDK ------>| OpenAI client / Response|
                 ├──────────────────────────┤
Qwen endpoint --->| Qwen config / behavior  |
                 └─────────────┬────────────┘
                               │
                            Adapter
                               │
                               ▼
                 ┌──────────────────────────┐
                 │ ModelRequest             │
                 │ ModelReply               │
                 │ ToolCall (Stage 01)      │
                 └─────────────┬────────────┘
                               │
                               ▼
                         Agent Runtime
```

The Runtime should not need to ask:

```text
Which concrete OpenAI SDK class is this Response?
What is Qwen's base URL?
Which provider-specific extension fields live under usage?
```

It should ask questions such as:

```text
What text did the model produce?
Did it propose a ToolCall?
How many Tokens did the call use?
Did the model call fail?
```

### A minimal Adapter

First define data that belongs to the Runtime itself:

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelRequest:
    instructions: str
    input: str


@dataclass(frozen=True)
class ModelReply:
    text: str
    response_id: str
    model: str


class ModelAdapter(Protocol):
    def generate(self, request: ModelRequest) -> ModelReply:
        ...
```

Then let the provider adapter translate native provider objects into those internal types:

```python
class OpenAICompatibleResponsesAdapter:
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def generate(self, request: ModelRequest) -> ModelReply:
        response = self.client.responses.create(
            model=self.model,
            instructions=request.instructions,
            input=request.input,
        )
        return ModelReply(
            text=response.output_text,
            response_id=response.id,
            model=response.model,
        )
```

Core application logic now depends only on `ModelAdapter`:

```python
def run_once(model: ModelAdapter, user_input: str) -> str:
    reply = model.generate(
        ModelRequest(
            instructions="You are a travel assistant.",
            input=user_input,
        )
    )
    return reply.text
```

Notice what is absent from `run_once()`:

```python
if provider == "openai":
    ...
elif provider == "qwen":
    ...
```

That absence is the point.

If provider branches leak into the Tool loop, planning, state machines, retries, and authorization code, changing a model becomes like rewiring an entire building just to replace one appliance.

An Adapter keeps that change at the edge.

A runnable version is provided here:

[`../code/provider_adapter_demo.py`](../code/provider_adapter_demo.py)

Run OpenAI:

```bash
python stages/00-foundations/code/provider_adapter_demo.py --provider openai
```

Run Qwen:

```bash
export DASHSCOPE_API_KEY="your Model Studio API key"
export DASHSCOPE_BASE_URL="your region/workspace compatible-mode/v1 base URL"
export QWEN_MODEL="qwen3.8-max"

python stages/00-foundations/code/provider_adapter_demo.py --provider qwen
```

Both commands enter the **same** `run_teacher_example()` function. Provider change happens in configuration and the Adapter, not in the Runtime's core logic.

Stage 01 extends the same idea into a real Agent model adapter: provider text and Function Calls are normalized into Runtime-owned `ModelResponse` / `ToolCall` types, while provider request errors remain explicit at the Adapter boundary and richer usage metadata is introduced later rather than forced into the minimal contract.

---

## 4. What did we actually give the model?

Look again at the request:

```python
response = client.responses.create(
    model="gpt-5.6-luna",
    instructions="You are a patient AI engineering teacher...",
    input="Why should an Agent not simply be understood as an LLM?",
)
```

There are at least three separate ideas here.

### `model`

```python
model="gpt-5.6-luna"
```

This selects a provider model configuration. Model IDs are versioned provider details and will change over time.

The durable concept is simply: **the application selects a model for the request.**

### `instructions`

```python
instructions="You are a patient AI engineering teacher..."
```

These are application-level instructions describing how the model should behave for this request.

Examples include:

```text
answer in Chinese
be concise
use only supplied evidence for factual claims
ask before guessing missing fields
```

In the Responses API, the top-level `instructions` field enters the request with system/developer-instruction semantics.

### `input`

```python
input="Why should an Agent not simply be understood as an LLM?"
```

This is the current task input.

At its simplest it is a string. More complex requests can use role-bearing messages and other input items.

So the first useful mental model is:

```text
application instructions
        +
current task input
        ↓
      model
        ↓
      output
```

That is already more precise than “everything is one giant prompt string.”

---

## 5. A `Response` is more than a string

For simple text answers, the convenient path is:

```python
print(response.output_text)
```

But the full Response can also carry fields such as:

```text
response.id
response.model
response.output
response.usage
response.status
...
```

`response.output` becomes especially important later because the model may emit more than one kind of item:

```text
assistant message
function call
reasoning item
built-in tool call
...
```

Once Tool Calling appears, an Agent Runtime cannot safely assume:

```python
response.output[0] == a text message
```

For ordinary question-answering, `output_text` is a useful convenience. For Agent runtimes, understanding output item types is part of the job.

---

## 6. What problem do message roles solve?

Introductory material often asks learners to memorize:

```text
system
user
assistant
tool
```

The names matter less than the problem they solve:

> **When all content is text, how do we preserve which text is application instruction, user input, earlier model output, or an external observation?**

Conceptually, a conversation may contain:

```text
Application instruction: You are a travel assistant.
User: I am going to Tokyo.
Assistant: Do you want weather or transport advice?
User: Weather.
```

Flattening that into one anonymous string discards useful semantics.

With the Responses API, a user message can be represented as:

```python
input=[
    {
        "role": "user",
        "content": "I am going to Tokyo. Do I need a heavy coat at 18°C?",
    }
]
```

Application-level rules can remain in `instructions`.

Later, Tool results will use a more specific Responses API item type: `function_call_output`. That provider-specific detail is important, but the general principle is the same: preserve the semantic origin of context instead of turning everything into anonymous prose.

---

## 7. Who stores the previous assistant turn?

A product such as ChatGPT makes continuous conversation feel natural, which can create the intuition that “the model remembers the previous call.”

For API engineering, a better statement is:

> **What prior information the model can use depends on what the application or provider-managed conversation mechanism makes available to the current request.**

For example:

```python
first = client.responses.create(
    model="gpt-5.6-luna",
    input="My project is called Tiny-Agent.",
)
```

A completely independent second call should not be assumed to contain that fact automatically:

```python
second = client.responses.create(
    model="gpt-5.6-luna",
    input="What is my project called?",
)
```

### Continue with `previous_response_id`

The Responses API provides a convenient continuation mechanism:

```python
first = client.responses.create(
    model="gpt-5.6-luna",
    input="My project is called Tiny-Agent.",
)

second = client.responses.create(
    model="gpt-5.6-luna",
    previous_response_id=first.id,
    input="What is my project called?",
)

print(second.output_text)
```

### Expected output

```text
Your project is called Tiny-Agent.
```

This does not mean the model acquired permanent memory. It means the API connected the current request to prior response state.

Later you will encounter:

```text
conversation history
checkpoint
short-term memory
long-term memory
RAG evidence
provider-managed conversation state
```

They can all make a model appear to “remember,” but their engineering semantics are very different.

---

## 8. Another subtle point: instructions are request construction, not magical permanent state

Do not replace one misconception with another:

> “If I used `previous_response_id`, every previous configuration is now permanently inherited.”

The Responses API treats `instructions` as request configuration. When continuing a workflow, the application should explicitly provide the high-level instructions still required for that turn instead of building control policy around accidental implicit state.

This leads to an Agent principle that will recur later:

> **Stable behavior should be constructed explicitly by the application.**

In the Tool loop chapter, we will therefore keep supplying the Tool schemas and required instructions on each relevant model turn.

---

## 9. What the application owns is not automatically what the model knows

Suppose Python contains:

```python
user_profile = {
    "name": "Alice",
    "city": "Tokyo",
    "budget": 8000,
}
```

That variable existing in process memory does not automatically make it model context.

The application must select and provide the information:

```python
response = client.responses.create(
    model="gpt-5.6-luna",
    input=f"User profile: {user_profile}\nGive travel advice.",
)
```

The same rule applies elsewhere:

```text
1,000,000 rows exist in a database
!= the model knows those rows

10 GB of documents exist on disk
!= the model has read those documents

a Python function exists
!= the model has executed that function
```

Those inequalities are foundational to Agent engineering.

---

## 10. Why Structured Output is the next chapter

We now have the basic path:

```text
Python application
    ↓
model call
    ↓
natural-language answer
```

But the moment the next consumer is software instead of a human, prose becomes awkward.

Suppose the input is:

> I am going to Tokyo on October 3, 2026. My budget is about 8,000 CNY and I also want weather information.

A perfectly reasonable model answer might be:

```text
The traveler plans to visit Tokyo on October 3 with a budget of about
8,000 CNY and would like weather information.
```

A program would rather receive:

```json
{
  "city": "Tokyo",
  "travel_date": "2026-10-03",
  "budget_cny": 8000,
  "needs_weather": true
}
```

So the next question appears naturally:

> **When software must consume model output, can we stop parsing prose with fragile string logic?**

That is what Structured Output is for.

---

## 11. Five sentences worth keeping

If you remember only five ideas from this chapter, keep these:

1. **The API Client is a programmatic interface to model inference, not the model itself.**
2. **A model reasons over context available to the current request; continuous conversation is not the same thing as inherent permanent memory.**
3. **Application data, functions, and permissions do not automatically become model capabilities.**
4. **Provider APIs, configuration, and native Response objects belong at the Adapter edge, not inside the Agent Runtime.**
5. **The first Agent boundary is simple: the model generates; the application constructs requests and handles results.**

Next, we make model output suitable for deterministic software.

---

## Official references

- OpenAI Responses API: <https://developers.openai.com/api/reference/resources/responses>
- OpenAI model guidance: <https://developers.openai.com/api/docs/guides/latest-model>
- Alibaba Cloud Model Studio, Qwen OpenAI-compatible Responses API: <https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen-api-via-openai-responses>

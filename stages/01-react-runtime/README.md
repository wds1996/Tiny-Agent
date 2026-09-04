# Stage 01 — Turn Tool Calling into a Real Agent Runtime

> Language: English | [简体中文](README.zh-CN.md)

Stage 00 ended with a small hand-written Tool loop:

```text
user request
   ↓
model decides whether to call a Tool
   ↓
Python executes the Tool
   ↓
result goes back to the model
   ↓
model decides again
```

That already looks a little like an Agent.

The problem appears when you keep extending the same loop. It quickly starts carrying responsibilities that are not really the same thing:

```text
How do we call a model?
How do we normalize different provider responses?
How do we look up Tools by name?
Who actually executes Python?
What happens when a Tool fails?
Who owns another model turn?
What if the model never stops?
How can we inspect what happened?
```

You can keep all of that in one `while True` and make it work. You will also make it progressively harder to reason about, test, and extend.

So Stage 01 does not begin with a dictionary definition of ReAct.

It begins with a design problem:

> **How do we turn the hand-written loop from Stage 00 into a small, explicit Agent Runtime without hiding the mechanism behind a framework?**

That is the thread connecting the whole stage.

---

## We keep the same travel assistant

Stage 00 used one evolving travel-assistant example. Stage 01 keeps it.

The user asks:

```text
For the course's mock Tokyo weather, tell me the temperature in Celsius,
convert it to Fahrenheit, and explain what that feels like for a traveler.
```

The application exposes two Tools:

```text
get_mock_weather(city)
celsius_to_fahrenheit(temperature_c)
```

A reasonable trajectory is:

```text
USER
  ask for Tokyo mock weather and Fahrenheit conversion

MODEL ACTION
  get_mock_weather(city="Tokyo")

RUNTIME
  execute the real Python Tool

OBSERVATION
  {"temperature_c": 18.0, "condition": "cloudy"}

MODEL ACTION
  celsius_to_fahrenheit(temperature_c=18.0)

RUNTIME
  execute the real Python Tool

OBSERVATION
  64.4

MODEL
  The course's mock Tokyo weather is 18°C, about 64.4°F ...
```

Stage 00 can already make this work.

Stage 01 makes the responsibilities explicit:

```text
                         AgentRuntime
                              │
                  ┌───────────┴───────────┐
                  │                       │
                  ▼                       ▼
              Model contract          ToolRegistry
                  │                       │
                  ▼                       ▼
          Provider Adapter            Python Tool
                  │                       │
                  ▼                       ▼
          OpenAI / Qwen ...           Observation
                  │                       │
                  └───────────┬───────────┘
                              ▼
                         next decision
```

The important lesson is not the class names. It is **why these responsibilities should be separate**.

---

## Six questions connect the stage

Treat the stage as one sequence of questions:

```text
01  Stage 00 already had a Tool loop. Why do we need a Runtime?
        ↓
02  What responsibilities belong inside a minimal Runtime?
        ↓
03  How can that Runtime avoid depending on OpenAI/Qwen-specific objects?
        ↓
04  How do call_id, observations, and steps connect across repeated Tool calls?
        ↓
05  How can we test Runtime control deterministically without a live LLM?
        ↓
06  Where does this minimal Runtime still fail in production?
        ↓
Stage 02: when should a model choose the path, and when should code define a Workflow?
```

By the end, you should not merely know that `AgentRuntime` exists. You should be able to explain **what breaks if each boundary disappears**.

---

## Prepare the environment

Stage 01 deliberately has three modes of execution.

### 1. Inspect the minimal Runtime — no network required

```bash
python stages/01-react-runtime/code/minimal_react_runtime.py
```

This uses `ScriptedTravelModel`. The point is to inspect Runtime control flow before adding model randomness.

### 2. Run deterministic unit tests

Install the development extra:

```bash
python -m pip install -e ".[dev]"
```

Then run:

```bash
pytest -q tests/test_runtime.py tests/test_runtime_edges.py
```

### 3. Connect a real OpenAI model

Install the provider extra:

```bash
python -m pip install -e ".[openai]"
```

Set the API key:

```bash
export OPENAI_API_KEY="your API key"
```

PowerShell:

```powershell
$env:OPENAI_API_KEY="your API key"
```

The example uses the course's current default model and allows an override:

```bash
export OPENAI_MODEL="gpt-5.6-luna"
```

Run:

```bash
python stages/01-react-runtime/code/openai_multi_tool_agent.py
```

The point is not simply “the model answered.” Check that the **same Runtime boundaries remain intact after replacing the scripted model with a live provider**.

---

## Recommended learning order

### Step 1 — See the loop clearly

Read:

1. [01 — From Tool loop to ReAct Runtime](theory/01-react-and-agent-loop.md)

Then run:

```bash
python stages/01-react-runtime/code/minimal_react_runtime.py
```

Be able to explain:

```text
Why is the first outcome a ToolCall?
Why must a Tool result become an Observation?
Why must that Observation enter the next model turn?
Why are ToolCall and final answer different Runtime outcomes?
```

### Step 2 — Extract architecture from the hand-written loop

Read:

2. [02 — From a hand-written loop to Core Runtime Architecture](theory/02-runtime-architecture.md)

The chapter introduces components in the order they become necessary:

```text
ToolCall / ModelResponse
        ↓
Model Protocol
        ↓
Tool / ToolRegistry
        ↓
AgentResult
        ↓
AgentRuntime.run()
```

Then run:

```bash
pytest -q tests/test_runtime.py tests/test_runtime_edges.py
```

This stage establishes an important engineering habit:

> **The LLM may be stochastic; Runtime control rules should still be tested deterministically whenever possible.**

### Step 3 — Connect a real OpenAI provider

Read:

3. [03 — Provider Adapters: keep the Runtime provider-neutral](theory/03-model-provider-adapter.md)

Then inspect:

```text
src/tiny_agent/types.py
src/tiny_agent/models/openai.py
```

Run the live example:

```bash
python stages/01-react-runtime/code/openai_multi_tool_agent.py
```

The important property is:

```text
ScriptedTravelModel
        ↓ replace with
OpenAIResponsesModel

AgentRuntime does not change
ToolRegistry does not change
Tool handlers do not change
```

That is the Adapter idea from Stage 00 becoming real Runtime architecture.

### Step 4 — Learn why Tool interface design changes Agent behavior

Read:

4. [Advanced — Tool / Agent-Computer Interface Design](advanced/tool-interface-design.md)

A Python handler can be perfectly correct while the model-facing Tool interface is terrible.

```text
correct implementation
!=
good Agent-computer interface
```

### Step 5 — Deliberately inspect the failure boundaries

Read:

5. [04 — Where this Runtime still breaks](theory/04-scope-and-production-limitations.md)

Instead of saying vaguely that “production needs more engineering,” the chapter walks through concrete failures:

```text
infinite loops
invalid arguments
Tool failures
permissions
timeouts
retries
concurrency
conversation state
tracing / evaluation
```

Know which ones Stage 01 solves and which ones are intentionally deferred.

### Step 6 — Rebuild the ideas yourself

Finish with:

6. [Stage 01 review and implementation exercises](exercises/review-questions.md)
7. [Provider Adapter exercises](exercises/provider-adapter-exercises.md)

The completion criterion is not “I read the Markdown.” It is: **without copying Tiny-Agent, you can rebuild a small Runtime and explain every boundary.**

---

## One boundary to keep in your head

The most important sentence in Stage 01 is:

> **The model proposes the next step; the Runtime decides how that proposal enters the real world.**

If the model emits:

```text
get_mock_weather(city="Tokyo")
```

that is only a proposal. The real path is:

```text
model ToolCall
    ↓
Runtime interprets
    ↓
ToolRegistry lookup
    ↓
application boundary checks
    ↓
Python handler executes
    ↓
Observation
    ↓
Runtime records it
    ↓
next model.generate(...)
```

The model never secretly reaches into Python and executes the function itself.

Keeping that boundary clear will make later stages on permissions, HITL, MCP, sandboxing, and multi-agent systems much easier to understand.

---

## Why do we suddenly care about FakeModel?

Learners sometimes see:

```python
class ScriptedModel:
    ...
```

and think:

> “I came here to learn LLM Agents. Why are we replacing the LLM with a fake?”

Because a FakeModel lets us isolate the part we are actually testing.

Suppose we need to verify:

```text
Does the Runtime execute a proposed Tool?
Is the Observation appended correctly?
Does call_id survive the round trip?
Does max_steps stop an endless loop?
Does an empty ModelResponse violate the contract?
```

Those are software control rules.

If every unit test calls a live model, the result is also influenced by network, credentials, sampling, provider outages, model upgrades, and cost.

That is like testing a car's brakes by first asking a random driver whether they feel like pressing the brake pedal today.

The Stage 01 habit is:

```text
Runtime rules
    -> deterministic unit tests

real Agent quality
    -> live integration / evaluation
```

Both matter. They are not the same kind of test.

---

## Why the teaching snapshot and `src/` are not identical

You will encounter both:

```text
stages/01-react-runtime/code/minimal_react_runtime.py
src/tiny_agent/runtime.py
```

They have different jobs.

The stage file is a **teaching snapshot**:

- self-contained;
- readable top to bottom;
- limited to the mechanisms this stage is teaching;
- designed so every boundary is visible in one place.

The `src/` version is the **evolving library implementation**:

- Stage 07 has already hardened the Tool-error boundary;
- later stages add async, policy, and integration capabilities;
- it shows what the same core mechanism becomes after the rest of the course.

So do not ask only:

> “Why are these files not identical?”

Ask:

> **Which parts are Stage 01 invariants, and which parts were intentionally added by later stages?**

That is exactly what the production-limitations chapter is for.

---

## You should be able to redraw this architecture from memory

```text
                    User Task
                       │
                       ▼
                ┌──────────────┐
                │ AgentRuntime │
                └──────┬───────┘
                       │
                normalized protocol
                       │
              ┌────────┴────────┐
              ▼                 ▼
        Model.generate()    ToolRegistry
              │                 │
              ▼                 ▼
      Provider Adapter       Tool handler
              │                 │
              ▼                 ▼
       OpenAI / Qwen ...    Observation
              │                 │
              └────────┬────────┘
                       ▼
                 Runtime state
                       │
                ┌──────┴──────┐
                ▼             ▼
             next step    final answer
```

And, more importantly, explain who owns every arrow.

---

## Completion checkpoint

Do not rush to Stage 02 if these questions still require notes:

1. What is the real difference between a Tool Calling demo and an Agent Runtime?
2. Why should `Model.generate()` represent **one model decision**, not secretly own the whole Agent run?
3. Why must `ToolCall.id` / provider `call_id` survive Tool execution and come back with the Observation?
4. Why is `ToolRegistry` more than a nicer replacement for `if tool_name == ...`?
5. Why should connecting a real OpenAI provider not require changing `AgentRuntime`?
6. Why do multiple ToolCalls in one model turn not imply concurrent Python execution?
7. Why is a FakeModel valuable in Agent engineering?
8. What does `max_steps` prevent, and what does it not prevent?
9. Which Stage 01 choices are durable architecture principles, and which are teaching simplifications?
10. Why does Stage 02 still need to discuss the boundary between Agents and deterministic Workflows?

If you can answer these with code and causal reasoning rather than vocabulary, Stage 01 has done its job.
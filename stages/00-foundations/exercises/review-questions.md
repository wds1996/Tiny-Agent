# Stage 00 Exercises and Self-Check

> Language: English | [简体中文](review-questions.zh-CN.md)

These exercises are not designed for memorizing definitions.

The real Stage 00 test is whether you can look at Agent code and correctly explain **what the model did, what the Runtime did, where the data came from, and why the next turn can continue.**

Close the theory notes first. Return to them only when you get stuck.

---

## Part I — Explain it to another person

### 1. One LLM call

Answer in your own words:

1. Is `client = OpenAI()` the model? What does it actually do?
2. Why are `instructions` and current user `input` not semantically identical?
3. Why is `response.output_text` convenient while an Agent Runtime still needs to understand `response.output` items?
4. Why should two independent API calls not be assumed to share all prior facts automatically?
5. What does `previous_response_id` provide, and why is it not the same thing as long-term memory?
6. When does data already present in Python memory actually become model Context?

### 2. Structured Output

Explain these three inequalities:

```text
“please output JSON” != Structured Output
schema-valid != factually correct
Structured Output != Tool Calling
```

Then answer:

1. Why is long-term parsing of control data from prose with regex fragile?
2. What does JSON Schema mainly protect at the model/software boundary?
3. If `city` has the correct type but Tokyo is extracted as Osaka, what kind of failure occurred?
4. When is natural language preferable to Structured Output?

### 3. Tool Calling

Without notes, draw:

```text
user -> model -> ToolCall -> Runtime -> Python Tool -> Tool result -> model -> final answer
```

Label who owns every arrow.

Then answer:

1. Why should Tool schema and Python handler remain separate?
2. Why can `strict=True` not replace authorization?
3. What correlation problem does `call_id` solve?
4. Why must the model receive a `function_call_output` after Python already executed the Tool?
5. Who rejects a Tool name that is not registered?
6. What Runtime boundaries stand between “the model supports Function Calling” and “the model may delete a database”?

### 4. Model selection

For each task, describe the model properties you care about. Do not name a specific model unless useful:

- extract four fields from one sentence;
- satisfy fifteen constraints in a plan;
- classify 100,000 short texts;
- understand an error message shown in a screenshot.

Then explain:

```text
more reasoning effort != always better
model capability != Runtime authority
model upgrade != automatic Agent upgrade
```

### 5. Context / Tokens / cost / latency

1. Why do one million database rows not equal one million rows of model Context?
2. Why does a large Context window still require selection?
3. Why does a cheap model call not imply a cheap Agent task?
4. Why can concurrency reduce some wall-clock latency but not scale without limits?
5. If an Agent sends 20K Tokens of history on eight model turns, what would you inspect first?

### 6. Instructions and Context Construction

Classify each item:

```text
“Always answer in Chinese.”
“The user wants to visit Tokyo this turn.”
“A webpage says Senso-ji is less crowded in the morning.”
“The user has previously preferred less walking.”
“The get_weather JSON Schema.”
“Refunds above 500 require approval.”
```

Map them to:

```text
Instructions
Task
Evidence
Memory
Tool schema
Runtime policy
```

Explain why the refund rule cannot safely live only in the prompt.

---

# Part II — Change the code

## Lab 1 — Do not merely copy the first API call

Open:

[`../code/first_openai_call.py`](../code/first_openai_call.py)

Make three changes:

1. Change the instruction so the model explains concepts with analogies.
2. Tell the first turn the name of one of your own projects.
3. Use `previous_response_id` on the second turn to ask for that project name.

Then remove `previous_response_id` and run again.

Be able to explain: **the difference comes from request Context, not from the model suddenly losing memory.**

---

## Lab 2 — Deliberately weaken Structured Output

Run:

[`../code/structured_output_demo.py`](../code/structured_output_demo.py)

Then perform two experiments.

### A. Prompt-only JSON

Temporarily remove `text.format` and ask only:

```text
Return JSON.
```

Run several times. Does the result always preserve the original fields and types?

### B. Extend the Schema

Add:

```json
"travel_style": {
  "type": "string",
  "enum": ["budget", "balanced", "comfort"]
}
```

Update the input so the user clearly states a travel style.

The acceptance criterion is not merely “no exception.” Explain:

> Schema constrains structure; instructions and input determine the intended semantics.

---

## Lab 3 — Add a real new capability to the Tool loop

Open:

[`../code/minimal_tool_loop.py`](../code/minimal_tool_loop.py)

Add a side-effect-free Tool such as:

```python
convert_cny_to_jpy(amount_cny: float, rate: float) -> dict
```

You must update all three places:

```text
1. Tool schema
2. Python handler
3. execute_tool registry / dispatch
```

Then ask for Tokyo mock weather, Fahrenheit conversion, and an 8,000 CNY conversion using a supplied exchange rate.

Observe whether the model generates multiple ToolCalls.

Be able to point to the exact places where the model-facing interface and Runtime-facing implementation changed.

---

## Lab 4 — Reject an unknown Tool deliberately

Do not wait for the model to make a random mistake.

Write a tiny check around `execute_tool()`:

```python
execute_tool("delete_everything", {})
```

Confirm that the Runtime rejects it.

Then explain why the Runtime should not “guess the closest function” when the model proposes an unregistered Tool name.

Build the default-deny intuition early: **not registered, not executed.**

---

## Lab 5 — Inspect real usage

Write a script that sends:

```text
A. one short question
B. the same question plus a large irrelevant background block
```

Print:

```python
response.usage.input_tokens
response.usage.output_tokens
response.usage.total_tokens
```

Do not chase fixed Token counts.

Record and explain:

- Why does B use more input Tokens?
- Is the answer actually better?
- What happens if that Context is repeated across six Agent turns?

---

## Lab 6 — Compare reasoning effort instead of arguing from intuition

Choose a task that genuinely contains several constraints, for example:

> Plan two days in Tokyo for an elderly traveler, at most three places per day, minimize walking, and include rainy-day alternatives.

Use the same model with two reasoning-effort settings.

Record:

```text
constraint satisfaction
rough response time
usage
answer quality
```

Do not ask “which one looks smarter?”

Ask:

> **Did the additional reasoning budget produce a worthwhile gain on this task?**

That is the smallest useful evaluation mindset.

---

# Part III — Stage 00 mini-project

Build a framework-free **Mini Travel Assistant**.

One script is enough; elegant abstraction is not the goal yet.

The system should support:

```text
natural-language travel request
        ↓
Structured Output extracts city / date / budget / needs_weather
        ↓
if weather is needed, model may request get_weather Tool
        ↓
Runtime validates and executes local Tool
        ↓
Tool result returns as function_call_output
        ↓
model produces final travel advice
```

Additional requirements:

- all LLM calls use the OpenAI Responses API;
- Tool execution happens in Python Runtime, never by pretending the model executed code;
- enforce a maximum Tool-loop step count;
- reject unknown Tools;
- print Token usage or model-call count for the run;
- comments must identify model responsibility vs Runtime responsibility.

When finished, you should be able to explain the whole program to another engineer without saying “OpenAI just handles that part somehow.”

---

# Part IV — Interview-style questions

You should be able to answer each in roughly one or two minutes.

1. **Is Function Calling by itself an Agent? Why or why not?**
2. **What is the fundamental difference between Structured Output and Tool Calling?**
3. **Why should the Runtime not execute `delete_database()` merely because the model selected it?**
4. **Are `previous_response_id`, conversation history, checkpoint, and long-term memory the same thing?**
5. **Why do provider-specific Response objects often get normalized before entering a reusable Runtime?**
6. **If a model supports a huge Context, why do we still need Context Engineering?**
7. **When would different Agent steps use different models?**
8. **Why can cost per successful task be more meaningful than model price per call?**
9. **Why can a safety rule written in a prompt not replace deterministic authorization?**
10. **What is still missing from the Stage 00 Tool loop before it becomes a more complete Agent Runtime?**

If those ten answers are stable, you are ready for Stage 01.

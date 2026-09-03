# 04 — Models Are Not Interchangeable: Capabilities, Reasoning Effort, and Selection

> Language: English | [简体中文](04-model-capabilities-and-reasoning.zh-CN.md)

The first three chapters quietly assumed a simple step:

```text
choose a model, then call it
```

Real Agent systems quickly make that assumption uncomfortable. Different steps ask the model to do very different kinds of work:

```text
classify whether the user needs weather
extract a city and date
choose a Tool
plan around several constraints
write a natural final answer
```

Using the strongest, most expensive, highest-reasoning configuration for every step can work. It is not automatically good engineering.

This chapter is not a model leaderboard. It teaches a more durable question:

> **What capability does this task require, and what evaluated model configuration meets that requirement under our latency and cost constraints?**

---

## 1. Treat a model name as a capability profile, not a magic label

When you write:

```python
model="gpt-5.6-luna"
```

that model ID represents a collection of provider capabilities and tradeoffs, potentially including:

```text
reasoning quality
Tool Calling
Structured Output
multimodal input
Context limits
output limits
latency
throughput
price
configurable reasoning effort
```

Different models can vary substantially along those dimensions.

So “Is model A stronger than model B?” is often too vague.

A better question is:

> **Is this model good enough for this specific role?**

---

## 2. Different Agent roles may deserve different models

Imagine the travel assistant growing into:

```text
user request
   ↓
intent classification
   ↓
trip planning
   ↓
Tools / retrieval
   ↓
final answer
```

### Intent classification

The output may only be:

```text
WEATHER
TRANSPORT
HOTEL
OTHER
```

Priorities may be:

```text
low latency
low cost
reliable Structured Output
```

Maximum reasoning effort may add little value.

### Trip planning

Now consider:

> Build a two-day Tokyo itinerary for an elderly traveler with limited walking, at most three attractions per day, transport constraints, and rainy-day alternatives.

This is a multi-constraint planning problem.

Priorities may become:

```text
reasoning quality
constraint satisfaction
plan consistency
```

### Final writing

The final answer may emphasize:

```text
natural presentation
completeness
faithful use of Tool-confirmed facts
```

Model selection is therefore a systems problem:

```text
task role
   ↓
required capability
   ↓
candidate model/configuration
   ↓
evaluation
```

not a brand preference.

---

## 3. A current GPT-5.6 example

At the time of this course version, OpenAI's GPT-5.6 family includes models positioned for different workloads, for example:

```text
gpt-5.6-luna   -> efficient, high-volume workloads
gpt-5.6-terra  -> balance of intelligence and cost
gpt-5.6-sol    -> flagship capability / quality-first work
```

Those names and exact positioning are **versioned provider details**.

Do not turn the lesson into:

> “Extraction must always use luna; planning must always use sol.”

Instead define requirements such as:

```text
intent classification: low latency + Structured Output + sufficient accuracy
complex planning: reasoning quality first, higher latency acceptable
batch extraction: throughput and unit cost first
```

Then map those requirements to the current model catalog.

If the catalog changes, the architecture still makes sense.

---

## 4. Reasoning effort is a budget, not an IQ slider

Current GPT-5.6 models expose configurable reasoning effort.

For example:

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.6-terra",
    input=(
        "Design a two-day Tokyo itinerary for an elderly traveler. "
        "Minimize walking, use at most three attractions per day, "
        "and include rainy-day alternatives."
    ),
    reasoning={"effort": "medium"},
    text={"verbosity": "low"},
)

print(response.output_text)
```

### Expected output

Exact wording varies, but a useful answer should visibly honor the constraints, for example:

```text
Day 1
- Morning: Asakusa ...
- Afternoon: ...
- Rain alternative: ...

Day 2
- ...

Transport choices are selected to reduce walking.
```

`reasoning.effort="medium"` does not mean “set the model's intelligence to medium.”

A better interpretation is:

> **Allocate a different amount of internal inference work to this request.**

That may affect quality, latency, Token use, and cost.

Whether more reasoning is worthwhile should be measured on your task distribution.

---

## 5. Why not use maximum reasoning for every request?

Suppose the task is only:

> Does this request require weather information?

and the output is:

```json
{"needs_weather": true}
```

If a lightweight configuration already achieves the target accuracy, more reasoning may simply mean:

```text
slower
more expensive
little measurable quality gain
```

That is like convening an expert committee to decide whether a door is open.

For tasks with many constraints, conflicting evidence, or difficult planning, higher reasoning may be worth the cost.

A useful engineering loop is:

```text
start with the cheapest viable baseline
        ↓
identify representative failures
        ↓
try a stronger model / more reasoning
        ↓
compare quality, latency, and cost
        ↓
upgrade only where the gain matters
```

---

## 6. A simple application-owned model policy

Stage 00 does not need an LLM-powered model router. A deterministic mapping is often clearer:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    model: str
    reasoning_effort: str


MODEL_BY_ROLE = {
    "extract": ModelConfig(
        model="gpt-5.6-luna",
        reasoning_effort="low",
    ),
    "plan": ModelConfig(
        model="gpt-5.6-terra",
        reasoning_effort="medium",
    ),
    "hard_reasoning": ModelConfig(
        model="gpt-5.6-sol",
        reasoning_effort="high",
    ),
}
```

The important part is not the three names. It is:

```text
model selection is application policy
```

Do not let arbitrary user text become an unrestricted provider model ID.

If you later add semantic routing, a safer pattern is:

```text
model chooses approved class
FAST | BALANCED | HARD
        ↓
application maps class to approved configuration
```

The principle is identical to Tool Calling:

> **The model may propose; the application owns the final configuration.**

---

## 7. Model capability and Runtime capability are different

This follows directly from the previous chapter.

```text
model supports Function Calling
!=
model can access your database
```

The model can only propose `query_database(...)` if the application exposes that Tool contract, and execution remains Runtime-controlled.

Likewise:

```text
model supports vision
!= model automatically sees your desktop

model supports computer use
!= model is authorized to operate production systems

model supports a large Context
!= application should send every available token
```

Model capability answers:

> What can the inference interface understand or propose?

Runtime capability answers:

> What has this application actually exposed, authorized, and allowed to execute?

Confusing the two is a serious Agent architecture error.

---

## 8. Why a model upgrade deserves regression evaluation

Swap model A for model B and behavior can change even if the API remains compatible:

```text
Tool-call frequency
plan length
Structured Output semantic accuracy
verbosity
refusal rate
Token use
latency
```

Therefore:

```text
“the new model is stronger”
```

is not equivalent to:

```text
“our Agent is better”
```

Evaluate on your workload.

A comparison might look like:

| Configuration | Route accuracy | Task success | p95 latency | Mean Tokens | Cost / successful task |
|---|---:|---:|---:|---:|---:|
| baseline | 96% | 83% | 1.2s | 900 | X |
| candidate | 97% | 89% | 2.0s | 1450 | Y |

Then ask whether the quality gain is worth the extra latency and cost.

Stage 08 makes Evaluation a full discipline. Stage 00 only needs to establish the habit.

---

## 9. Do not use visible chain-of-thought as your correctness test

Reasoning models may perform substantial internal reasoning. A production architecture should not depend on obtaining or inspecting a full hidden chain-of-thought as a correctness guarantee.

Measure observable behavior instead:

```text
Is the final answer correct?
Are structured fields correct?
Was the right Tool selected?
Does evidence support the claim?
Are latency and cost acceptable?
```

When debugging, use supported observable signals—Tool trajectories, traces, evaluations, and reasoning summaries where available—rather than treating hidden reasoning as a Runtime interface.

---

## 10. Why Context, Tokens, cost, and latency come next

We now know that one Agent task may contain several model calls, potentially with different configurations.

The cost question therefore evolves from:

```text
“How expensive is one API call?”
```

into:

```text
“How many model calls does one task make?”
“How much Context does each turn carry?”
“Does the Tool loop resend large history repeatedly?”
“How does reasoning effort change latency and Token use?”
```

That leads directly to the next chapter:

> **Why are Context, Tokens, cost, and latency part of Agent architecture rather than mere billing statistics?**

---

## Chapter takeaway

An experienced Agent engineer is usually not asking:

> “Which model is the smartest?”

The better question is:

> **What capability does this step require, and which evaluated configuration meets the quality target under the product's latency and cost constraints?**

Keep these distinctions:

```text
model capability != Runtime authority
more reasoning != always better
newer model != automatically better Agent
model selection = application policy
```

---

## Official references

- OpenAI current model guidance: <https://developers.openai.com/api/docs/guides/latest-model>
- OpenAI Responses API: <https://developers.openai.com/api/reference/resources/responses>

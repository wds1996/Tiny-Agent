# 05 — Every Call Has a Budget: Context, Tokens, Cost, and Latency

> Language: English | [简体中文](05-context-tokens-cost-latency.zh-CN.md)

The first four chapters focused mostly on whether the model can perform the task.

Now place the travel assistant inside a real loop:

```text
user question
   ↓
model decides to get weather
   ↓
Tool returns weather
   ↓
model requests a conversion
   ↓
Tool returns result
   ↓
model writes final answer
```

One user request may already contain three model calls.

If each turn carries large history, Tool schemas, documents, and instructions, “just add a little more Context” becomes an expense paid repeatedly across the trajectory.

The core intuition of this chapter is therefore:

> **Context, Tokens, model-call count, and latency are finite resources that the Runtime must manage.**

---

## 1. Context is not “everything the model knows”

In Tiny-Agent, **Context** means the information actually available to the model for the current inference step.

It may include:

```text
application instructions
current user task
conversation history
Tool schemas
Tool results
retrieved evidence
selected Memory
few-shot examples
workspace/progress summaries
```

The word **selected** matters.

Your application may own:

```text
1,000,000 database rows
100,000 indexed documents
20 GB of files
months of user Memory
```

That is the application's available information universe. It is not automatically the current model Context.

```text
exists in Storage / State
!=
visible to the current model call
```

Only selected information placed into the current request becomes model Context.

That is why later chapters distinguish:

```text
Context != State
Context != Memory
Context != RAG corpus
Context != Checkpoint
```

---

## 2. What is a Token, and why not count words?

Models do not meter input directly by English words or Chinese characters. Text is encoded into Tokens.

A Token may correspond to:

```text
a whole word
part of a word
punctuation
one or more characters
```

Exact segmentation depends on the model/tokenizer.

So code such as:

```python
estimated_tokens = len(text.split())
```

should not be treated as precise accounting.

After a real request, provider usage metadata is one of the best sources of actual metered usage.

---

## 3. Inspect OpenAI Token usage directly

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.6-luna",
    instructions="Answer in one concise sentence.",
    input="Why should an Agent Runtime manage Context?",
)

print(response.output_text)
print("input_tokens =", response.usage.input_tokens)
print("output_tokens =", response.usage.output_tokens)
print("total_tokens =", response.usage.total_tokens)
```

### Example output

Exact counts vary with model version, request shape, and generated text. A plausible sample might look like:

```text
An Agent Runtime manages Context because the model only reasons over the information supplied to the current call, while irrelevant excess increases cost, latency, and distraction.
input_tokens = 39
output_tokens = 30
total_tokens = 69
```

Do not memorize `39`.

Notice instead that a model call has observable input and output Token usage. If one task makes five or ten calls, those quantities accumulate.

---

## 4. A Context window is capacity, not a packing target

A simplified budget looks like:

```text
input Context
+ room for model output / reasoning
<= model/API limits
```

A common beginner instinct is:

> “If the model supports a very large Context, why not send everything?”

A large suitcase does not mean a three-day trip improves when you force it to contain 30 kilograms of belongings.

Large capacity means:

> **When the task genuinely needs more relevant information, you have room.**

It does not make irrelevant information useful.

---

## 5. Reserve room before filling the request

Use teaching numbers for a simple budget:

```text
maximum working budget        32,000
reserve final output           4,000
reserve Runtime/Tool turns     2,000
------------------------------------
planned input budget          26,000
```

In Python:

```python
max_context = 32_000
reserve_output = 4_000
reserve_runtime = 2_000

available_input = (
    max_context
    - reserve_output
    - reserve_runtime
)

print(available_input)  # 26000
```

Runnable example:

[`../code/context_budget_basics.py`](../code/context_budget_basics.py)

Why reserve room?

Because an Agent request may still need:

```text
a model answer
Tool observations
another model turn
a larger final synthesis
```

If the first turn fills the working capacity completely, continuation becomes fragile.

The 32K/4K/2K values are teaching numbers, not fixed specifications of any particular model. Production systems should use the actual limits of the selected model/API.

---

## 6. Why loops multiply cost

A normal chat interaction may be:

```text
one user question
→ one model call
```

An Agent trajectory may be:

```text
route         1 call
plan          1 call
Tool loop     3 calls
review        1 call
rewrite       1 call
-------------------
              7 calls
```

If every turn carries an extra 10,000 Tokens of history and documents, those Tokens may be repeatedly included rather than paid once.

The rough intuition:

```text
extra Context × repeated model calls
```

explains why Agent cost optimization is often broader than choosing a cheaper model.

Removing irrelevant Context, reducing unnecessary model turns, and narrowing exposed Tools can all affect total cost.

---

## 7. Measure cost per successful task, not only cost per call

End-to-end cost may include:

```text
model input Tokens
+ model output Tokens
+ Tool / external API charges
+ retrieval / vector infrastructure
+ sandbox / compute
+ retries
```

Comparing only:

```text
model A is cheaper per call
model B is more expensive per call
```

can be misleading.

For example:

```text
cheap configuration: $0.2 per call, often retries four times
stronger configuration: $0.5 per call, usually succeeds once
```

A more meaningful product metric is often:

> **cost per successful task**

Stage 08 formalizes evaluation metrics. Stage 00 only needs to establish the habit.

---

## 8. Latency is more than model response time

End-to-end Agent latency can include:

```text
queue wait
model inference
retrieval
Tool network calls
database access
sandbox startup
retries
human approval
other Agents
```

A serial path might be:

```text
model          2s
weather API    1s
model          2s
another API    3s
----------------
roughly        8s + overhead
```

Dependent work must remain serial.

Independent work can sometimes run concurrently:

```text
             ┌─ search A 1.2s ─┐
planner 2s ──┼─ search B 1.0s ─┼─ synthesize 2s
             └─ search C 1.4s ─┘
```

Then the search portion is closer to the slowest branch than the sum.

But concurrency is not free. Excessive concurrency can cause:

```text
rate limits
connection exhaustion
memory growth
downstream queues
correlated failure bursts
```

Stage 10 later introduces bounded concurrency and backpressure.

---

## 9. More Context can reduce quality

Suppose the model can technically fit:

```text
all conversation history
all Memory
all retrieved documents
all Tools
all Skills
all workspace files
```

“Fits” does not mean “helps.”

Extra Context can introduce:

```text
attention competition
stale instructions
contradictory history
duplicate facts
low-quality evidence
larger prompt-injection surface
higher cost
higher latency
```

So:

```python
context = all_history + all_memory + all_docs + all_tools
```

is usually Context dumping, not Context Engineering.

A better mental model is:

```text
application owns lots of information
       ↓
what does this decision actually need?
       ↓
select high-signal information
       ↓
construct current Context
```

Stage 06A turns selection, compaction, priority, provenance, and trust into an explicit system.

---

## 10. Does prompt caching solve the problem?

No.

Caching stable repeated prefixes can improve latency or price characteristics, and current OpenAI models provide prompt-caching capabilities.

But caching does not turn irrelevant information into useful information.

Even a cheaper piece of Context may still:

```text
occupy Context capacity
compete for attention
increase exposure to untrusted instructions
```

A better optimization order is usually:

```text
Do we need to send this content at all?
        ↓
If yes, can stable content be arranged for efficient reuse/caching?
```

not the reverse.

---

## 11. How a research Agent loses control of Context

Suppose a research Agent retrieves 20 chunks per search and performs four searches.

A beginner implementation may do:

```text
turn 1: carry 20 chunks
turn 2: carry old 20 + new 20
turn 3: carry 60
turn 4: carry 80
final synthesis: carry all 80 again
```

Then add:

```text
full chat history
all Tool schemas
Memory
planning notes
```

The system becomes slower and it becomes harder to know which information actually influenced the answer.

A more deliberate pipeline might be:

```text
retrieve broad candidates
   ↓
filter / rerank / deduplicate
   ↓
select useful evidence
   ↓
compact old progress
   ↓
expose only currently needed Tools / Skills
   ↓
synthesize
```

Sometimes making an Agent more capable means helping it see **less irrelevant information**, not more total text.

---

## 12. Metrics worth noticing from now on

Stage 00 does not ask you to build an observability stack, but you should know what will matter:

```text
task success rate
model calls per task
input/output Tokens per task
Tool calls per task
p50 / p95 latency
retry count
cost per successful task
Context truncation/drop rate
```

These become formal Evaluation and Observability topics in Stage 08.

For now, develop one habit:

> **Do not only ask whether the model answered well. Ask how many resources and steps the system needed to complete the task.**

---

## 13. Why Instructions and Context Construction come next

This chapter established:

```text
Context is a finite decision-time resource
```

The next question should therefore not be:

> “What else can I stuff into the prompt?”

It should be:

> **“What does this turn actually need, and which pieces are instructions, task data, evidence, Memory, or optional background?”**

That moves us from informal prompt tweaking toward a more structural problem:

```text
How should the application construct a model request?
```

The next chapter separates:

```text
Instructions
Task
Evidence
Memory
Tool schemas
Examples
```

into explicit semantic roles.

---

## Chapter takeaway

Keep four distinctions:

```text
application-owned data != current Context
Context-window capacity != useful Context
cost per call != cost per completed task
concurrency != infinite resources
```

Once an Agent loops, Tokens, Context, model-call count, and latency become architecture.

---

## Official references

- OpenAI Responses API usage: <https://developers.openai.com/api/reference/resources/responses>
- OpenAI model guidance / prompt caching: <https://developers.openai.com/api/docs/guides/latest-model>

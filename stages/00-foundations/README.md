# Stage 00 — Understand Agents by Starting with One LLM Call

> Language: English | [简体中文](README.zh-CN.md)

Stage 00 does not begin by asking you to “build an Agent.”

It starts with a more basic question that many tutorials skip:

> **When you write `client.responses.create(...)`, what actually happens between your Python program, the model, and the outside world?**

If that boundary is fuzzy, later topics such as Tool Calling, Memory, RAG, LangGraph, and MCP become a collection of APIs to memorize. You may know how to call a framework method without knowing which part is model behavior and which part is application behavior.

The goal of Stage 00 is therefore simple: understand the smallest pieces from which an Agent runtime is built.

---

## One example grows through the entire stage

To keep the ideas connected, Stage 00 follows one small travel-assistant example instead of switching domains in every chapter.

At first it is only a normal LLM interaction:

```text
User: I am going to Tokyo. What does 18°C feel like for a traveler?
Model: natural-language answer
```

Then we notice that prose is awkward for software to consume, so we introduce Structured Output:

```text
user request
   ↓
model returns structured trip information
{city, date, budget, needs_weather}
```

Next we notice that the model does not inherently possess live weather data, so Tool Calling appears naturally:

```text
model proposes: get_weather(city="Tokyo")
          ↓
Python Runtime executes the Tool
          ↓
Tool result is returned to the model
          ↓
model continues
```

At this point you can already see the outline of an Agent loop.

The final three chapters then ask the systems questions that follow:

- Which model should do each kind of work?
- How do Context, Tokens, cost, and latency compound across repeated calls?
- As available information grows, what should the next model request actually contain?

Stage 01 can then introduce a ReAct Runtime as an answer to problems you have already encountered, rather than as a framework-shaped abstraction that appears from nowhere.

---

## The six questions of Stage 00

Do not treat these chapters as six independent topics. They are six questions that arise in sequence.

```text
01  How do I make one real LLM API call?
        ↓
02  If software must consume the result, how do I avoid parsing prose?
        ↓
03  If the model needs an external capability, who actually runs the Tool?
        ↓
04  How should different models and reasoning settings be selected?
        ↓
05  Why do Tokens / Context / cost / latency become architecture in a loop?
        ↓
06  When information grows, what should the next model call actually see?
        ↓
Stage 01: turn these mechanics into an explicit Agent Runtime
```

The first half answers:

> **How does the model communicate with software?**

The second half answers:

> **How should software manage model calls?**

---

## Recommended learning order

### Step 1 — Make a model answer you

Read:

1. [`theory/01-llm-api-and-messages.md`](theory/01-llm-api-and-messages.md)

Then run:

```bash
python stages/00-foundations/code/first_openai_call.py
```

Do not memorize API fields yet. Understand this path:

```text
your Python program
    ↓ constructs a request
OpenAI Responses API
    ↓
model inference
    ↓ returns a Response
your Python program continues
```

### Step 2 — Make the result safe for software to consume

Read:

2. [`theory/02-structured-output.md`](theory/02-structured-output.md)

Run:

```bash
python stages/00-foundations/code/structured_output_demo.py
```

The first major engineering lesson appears here:

> **Human-facing output can be natural language; control data consumed by software should usually have an explicit structure.**

### Step 3 — Let the model request an external capability

Read:

3. [`theory/03-function-calling.md`](theory/03-function-calling.md)

Run:

```bash
python stages/00-foundations/code/minimal_tool_loop.py
```

Be able to explain:

```text
Tool schema != Python function
ToolCall proposal != Tool execution
model-generated arguments != safe arguments
Tool executed != model automatically knows the result
```

### Step 4 — Treat model choice as application design

Read:

4. [`theory/04-model-capabilities-and-reasoning.md`](theory/04-model-capabilities-and-reasoning.md)

The goal is not to memorize a model leaderboard. Learn to match model capability and reasoning effort to a task role.

### Step 5 — Treat every model call as resource consumption

Read:

5. [`theory/05-context-tokens-cost-latency.md`](theory/05-context-tokens-cost-latency.md)

Run:

```bash
python stages/00-foundations/code/context_budget_basics.py
```

Once an Agent loops, the same Context may be sent repeatedly. “Just add a little more prompt” can affect cost, latency, and attention on every turn.

### Step 6 — Construct one bounded model request deliberately

Read:

6. [`theory/06-instructions-prompts-and-context-construction.md`](theory/06-instructions-prompts-and-context-construction.md)

Finish with:

7. [`exercises/review-questions.md`](exercises/review-questions.md)

---

## Prepare the OpenAI environment

All live LLM examples in Stage 00 use the current OpenAI **Responses API** so learners do not have to switch between unrelated calling styles while learning the fundamentals.

Install the project with the OpenAI extra:

```bash
python -m pip install -e ".[openai]"
```

Set an API key:

```bash
export OPENAI_API_KEY="your API key"
```

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your API key"
```

Examples use a current GPT-5.6 family model by default and allow an override:

```bash
export OPENAI_MODEL="gpt-5.6-luna"
```

Provider model IDs change. Do not treat one model name as the lesson. The durable concepts are the request shape and the Runtime boundary.

Current OpenAI references:

- https://developers.openai.com/api/docs/guides/latest-model
- https://developers.openai.com/api/reference/resources/responses

---

## The mental model to carry through the repository

Most later Tiny-Agent stages elaborate this diagram:

```text
               Application / Runtime
┌───────────────────────────────────────────┐
│ choose model                              │
│ construct instructions                    │
│ select Context                            │
│ expose Tool schemas                       │
│ validate model output                     │
│ enforce permissions                       │
│ execute real Python / APIs                │
│ persist state                             │
│ bound cost, steps, and stopping           │
└───────────────────────────────────────────┘
                       │
                       │ request
                       ▼
                 ┌───────────┐
                 │    LLM    │
                 │           │
                 │ infer over│
                 │ supplied  │
                 │ Context   │
                 └───────────┘
                       │
                       │ text / structured data / ToolCall
                       ▼
               Application / Runtime
```

Think of the model as a powerful semantic inference and decision component, not as the entire program.

The model may say:

> “I propose calling `get_weather(city="Tokyo")`.”

But the application still decides:

- whether that Tool exists;
- whether the arguments are valid;
- whether the caller is allowed to use it;
- whether approval is required;
- whether Python/API execution actually happens;
- how the result is stored and returned to the next turn.

The rule that starts here and survives every later stage is:

> **The model proposes the next step; application code decides whether, how, and under which rules that step may actually happen.**

---

## What counts as finishing Stage 00?

“Read six Markdown files” is not the milestone.

You are ready for Stage 01 when you can explain this path without notes:

```text
user input
    ↓
application selects instructions / Context / Tools
    ↓
OpenAI Responses API call
    ↓
model emits text / Structured Output / ToolCall
    ↓
application parses and validates
    ↓
if ToolCall: Runtime executes the real function
    ↓
Tool result returns as function_call_output
    ↓
model makes another decision or produces the final answer
```

Then answer three questions clearly:

1. Why does “the model supports Tool Calling” not mean “the model is authorized to use every Tool”?
2. Why does “the model has a huge Context window” not mean “send everything”?
3. Why is one Function Calling example still far from a production Agent?

If those answers are clear, Stage 01 has a solid foundation.

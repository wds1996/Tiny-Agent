# Stage 00: Before You Build an Agent, Understand One Model Call

> Language: **English** | [简体中文](README.zh-CN.md)

If this is your first Agent course, I want to begin with advice that may sound suspiciously unambitious: do not build an Agent yet.

You opened the repository to learn Agents, and the first chapter asks you to stare at one ordinary model call. It is a little like joining a driving course and spending the first lesson learning what the steering wheel is connected to. Not glamorous, but useful. If you skip this part, later abstractions start to feel like magic words: Tool, Runtime, Memory, Workflow. If you understand this part, those abstractions become ordinary software responses to ordinary engineering problems.

We will follow one continuous story. First, Python asks a model for text. Then we notice that prose is awkward for software to consume, so we introduce Structured Output. Then we notice that a perfectly structured answer still cannot fetch live or private data, so we introduce Tool Calling. By the end, you will have a complete `model → tool → model` round trip.

The complete runnable programs live only in [`code/`](code/). This chapter shows small excerpts at the moment each idea matters. That keeps the prose readable and gives the repository one authoritative copy of each executable example.

---

## 1. Start with a mental model that will survive the rest of the course

Suppose a user asks:

> Why is a language-model answer only a proposal, not an action my Python program has already performed?

At the beginning, the data flow is almost boring:

```text
user input
   ↓
Python builds a request
   ↓
model service generates a response
   ↓
Python reads the response
```

The important part is not the API name. It is the ownership boundary.

The model generates output. Your application performs application behavior. A model may produce the sentence “the email has been sent,” but if your code never called an email service, no email was sent. The sentence is evidence that the model generated a sentence, not evidence that the world changed.

I find it useful to imagine the model as a clever consultant sitting behind glass. You can pass documents through the slot. The consultant can return advice such as “look up the weather,” “call this function,” or “set the field to 42.” But the consultant does not receive the keys to your database merely because the advice sounds confident.

That boundary—generation versus execution—is the foundation for almost everything we will build later.

### 1.1 Prepare the environment

The examples use Python 3.10 or later. Install the chapter dependencies from the repository root:

```bash
python -m pip install -r stages/00-foundations/code/requirements.txt
```

Then configure an API key and a model available to your project:

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-id"
```

PowerShell:

```powershell
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_MODEL="your-model-id"
```

The examples deliberately avoid hard-coding a model name. Model catalogs and account permissions change. An explicit `OPENAI_MODEL` is less magical and easier to debug.

Every example checks required environment variables near startup:

```python
def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Set {name} before running this example.")
    return value.strip()
```

There is nothing Agent-specific about this. It is simply good boundary design: fail near the bad input instead of carrying the mistake ten function calls deeper into the program.

---

## 2. Your first real model call

Run:

```bash
python stages/00-foundations/code/first_llm_call.py
```

The complete example is in [`code/first_llm_call.py`](code/first_llm_call.py). The central request is:

```python
response = client.responses.create(
    model=model,
    instructions=(
        "You are a patient programming teacher. Explain the idea accurately, "
        "use one concrete analogy, and avoid unexplained jargon."
    ),
    input=(
        "In no more than 120 words, explain why a language model response is "
        "a proposal produced by a model rather than an action performed by my "
        "Python program."
    ),
)
```

A common beginner mental model is “string in, string out.” That is close enough to get a demo running and imprecise enough to cause trouble later.

A better model is: **the application submits a request and receives a Response object.** Text is one view of that response, not the entire protocol.

That is why the example checks the response before printing it:

```python
if response.status != "completed":
    raise RuntimeError(f"The response did not complete: {response.status}")

if not response.output_text.strip():
    raise RuntimeError("The response completed without text output.")
```

“No Python exception occurred,” “the provider reports completion,” and “there is usable text” are separate facts. Keeping them separate makes later failure handling much easier to reason about.

### 2.1 `instructions` and `input` come from different places

They are both strings here, but they serve different roles.

`instructions` expresses application-level behavior: how the model should answer, what style or constraints it should follow. `input` is the task or data for this particular call.

It is tempting to concatenate everything into one giant prompt:

```python
prompt = policy + user_question + documents + tool_result
```

That works until you need to answer a simple question: which part is an application rule, which part came from the user, and which part is merely external data?

For this chapter, one definition of context is enough:

> **Context is everything the model can actually see for one call.**

Instructions, user input, and later Tool Outputs may all become part of that context. Context is not a database. It is not long-term memory. The model only sees what the application actually supplies for that turn.

### 2.2 Generated text is not a fact source by default

Language models generate likely continuations. The same input can produce different wording or details across calls. That immediately gives us an engineering rule: if software must depend on a result, do not make the dependency hinge on one exact sentence.

Imagine the model returns:

> This looks important. We probably need current weather data first.

A human understands it. A program starts making questionable life choices:

```python
if "important" in answer.lower():
    priority = "high"
```

The next response says `urgent` instead of `important`, and the “interface” has changed without warning.

That is not a language-model problem so much as a software-interface problem. So we solve it as one.

---

## 3. Structured Output: let software receive data instead of guessing prose

Suppose the application wants a task card such as:

```json
{
  "goal": "compare current weather in Tokyo and Paris",
  "priority": "medium",
  "needs_external_data": true,
  "reason": "current weather must be retrieved"
}
```

Once the shape is stable, downstream code can use normal field access instead of searching through prose.

Run:

```bash
python stages/00-foundations/code/structured_output.py
```

The complete example is [`code/structured_output.py`](code/structured_output.py). The important part comes before the model call: define what the application needs.

```python
class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    priority: Priority
    needs_external_data: bool
    reason: str = Field(min_length=1)
```

This ordering matters. We are not asking the model to improvise an object and then reverse-engineering a contract from whatever it happened to produce. The application defines the contract first.

The SDK is then asked to parse into that type:

```python
response = client.responses.parse(
    model=model,
    instructions=(
        "Turn the request into a task card. Describe only the request itself; "
        "do not guess the weather or pretend that external data was retrieved."
    ),
    input=(
        "Compare the current weather in Tokyo and Paris and tell me which city "
        "is warmer."
    ),
    text_format=TaskCard,
)
```

And the parsed value is checked explicitly:

```python
task = response.output_parsed
if task is None:
    raise RuntimeError("The response contained no parsed TaskCard.")
```

Now the rest of the program can treat the result as application data.

### 3.1 Structure is not truth

This is the most important trap in Structured Output.

A model can return a perfectly valid object that is still semantically wrong:

```json
{
  "goal": "compare current weather",
  "priority": "high",
  "needs_external_data": false,
  "reason": "the model already knows it"
}
```

The schema may be satisfied: fields exist, types are correct, the enum is valid. Yet the claim that live weather requires no external data is poor reasoning.

It helps to separate three questions:

| Layer | Question | Can the schema enforce it? |
|---|---|---|
| Syntax | Can the data be parsed? | Yes |
| Structure | Are fields, types, and allowed values valid? | Yes |
| Semantics / facts | Is the judgment sensible and the claim true? | Not by itself |

A schema is a meticulous receptionist. It can tell you the form is complete. It is not secretly also an investigative journalist.

So the lesson is:

> **Structured Output solves “how can the program reliably read the result?” It does not automatically solve “why should the program believe the result?”**

The weather example exposes the next missing piece. If the model should not invent current data, how does it obtain external information?

---

## 4. Tool Calling: give the model capabilities it may request

A model does not automatically own your Python interpreter, database connection, or private API credentials. The application must describe a capability and retain control of the implementation.

A Tool has two sides:

```text
model-facing side
    name / description / parameters

application-facing side
    Python handler
```

The model learns how to request the capability. The application decides whether and how to execute it.

This chapter uses deterministic teaching weather:

```python
TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}
```

It is intentionally not live weather. A reproducible example lets us study Tool Calling without turning the lesson into a side quest about HTTP failures, rate limits, and third-party credentials.

Run:

```bash
python stages/00-foundations/code/tool_calling.py
```

The complete example is [`code/tool_calling.py`](code/tool_calling.py).

### 4.1 A Tool schema teaches the model how to ask

The Tool definition includes a name, description, and parameter schema:

```python
WEATHER_TOOL = {
    "type": "function",
    "name": "get_teaching_weather",
    "description": (
        "Return the deterministic teaching weather record for Tokyo or Paris. "
        "Use this function whenever the user asks about those teaching records."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "enum": sorted(TEACHING_WEATHER),
            }
        },
        "required": ["city"],
        "additionalProperties": False,
    },
    "strict": True,
}
```

The description is not decorative documentation. It helps the model decide when the Tool applies. A vague description such as `query things` does not make the Tool flexible; it makes the model guess.

### 4.2 A Function Call is only a request

The first model call deliberately forces the function path so we can study the mechanism instead of the model's preference that day:

```python
first = client.responses.create(
    model=model,
    instructions=(
        "Use the supplied function to read teaching weather records. A function "
        "call only requests an action; never claim a result before the function "
        "output is returned."
    ),
    input=(
        "Read Tokyo's deterministic teaching weather record and report the "
        "temperature and condition."
    ),
    tools=[WEATHER_TOOL],
    tool_choice={"type": "function", "name": "get_teaching_weather"},
    parallel_tool_calls=False,
)
```

At this point, no Python handler has run. The model has said, in effect:

```text
I propose get_teaching_weather(city="Tokyo").
```

That proposal still has to cross the application boundary.

### 4.3 Never confuse a generated function name with execution authority

The application checks the provider output:

```python
calls = [item for item in first.output if item.type == "function_call"]
if len(calls) != 1:
    raise RuntimeError(...)

call = calls[0]
if call.name != "get_teaching_weather":
    raise RuntimeError(...)
```

Then it parses and validates arguments:

```python
arguments = parse_arguments(call.arguments)
city = validate_weather_arguments(arguments)
```

Only after that does the application invoke the handler:

```python
result = get_teaching_weather(city)
```

The order is the architecture:

```text
model proposes
    ↓
application parses
    ↓
application validates
    ↓
application executes
```

Do not feed generated names into `eval()`, `exec()`, arbitrary imports, or an unrestricted global namespace. Model output is data. It does not become executable authority because it resembles code.

### 4.4 Why validate again if the provider uses a strict schema?

Because these checks live at different boundaries.

The provider-side schema helps constrain normal model generation. The application-side validation checks the concrete data that is about to reach a Python handler. A Tool Call may later be replayed, stored, transformed, or constructed by another system. The code that owns execution should validate what it accepts.

It is the same reason a backend validates input even when the frontend already checked the form.

### 4.5 `call_id` is the receipt number for one invocation

After execution, the application returns the Tool Output with the original call ID:

```python
{
    "type": "function_call_output",
    "call_id": call.call_id,
    "output": json.dumps(result, ensure_ascii=False),
}
```

The Tool name tells you which capability was requested. The call ID tells you which invocation this result belongs to.

Two calls may use the same Tool:

```text
call_A → get_teaching_weather(Tokyo)
call_B → get_teaching_weather(Paris)
```

Without IDs, you have two identical menu items and no table numbers.

### 4.6 The second model call finally sees the Observation

The final request continues the previous provider response and supplies the Tool Output:

```python
final = client.responses.create(
    model=model,
    instructions=(
        "Answer only from the returned function output. Make clear that this is "
        "a deterministic teaching record, not live weather."
    ),
    previous_response_id=first.id,
    input=[
        {
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": json.dumps(result, ensure_ascii=False),
        }
    ],
    tools=[WEATHER_TOOL],
    tool_choice="none",
)
```

The two identifiers solve different relationships:

- `call_id` links a Tool Call to its Tool Output;
- `previous_response_id` links one provider response to the response it continues.

The model can now answer from an Observation produced by application execution rather than from an unsupported guess.

The full timeline is:

```text
user asks
  ↓
model proposes a Function Call
  ↓
application validates it
  ↓
application runs Python
  ↓
application returns a Function Call Output
  ↓
model answers from the Observation
```

That is the first complete Tool round trip.

---

## 5. Similar-looking concepts, different jobs

Structured Output and Tool Calling both involve structured data, so beginners often mix them together. The easiest question is: **what is the structure for?**

Structured Output lets software read the model's judgment. A Tool Call lets the model request an application capability. Tool Execution is the application actually doing the work. Tool Output is the observation returned after that work.

An office analogy works surprisingly well. Structured Output is a completed form. A Tool Call is a submitted request. Tool Execution is an employee actually doing the task. Tool Output is the receipt. A beautifully completed form still does not walk to the warehouse and move a box.

---

## 6. Why Stage 00 should stop here

The current `tool_calling.py` is still a fixed script:

```text
first model call
→ execute one Tool
→ second model call
→ stop
```

Now ask for two actions:

> Read Tokyo's teaching weather and convert Celsius to Fahrenheit.

The model may need a weather Tool, then a conversion Tool, then a final answer. You can keep adding `second`, `third`, and `fourth`, but you are now guessing the length of a path that is supposed to be chosen dynamically.

The abstraction we actually need is beginning to reveal itself:

```python
while the run is not finished:
    ask the model for the next step

    if it requests a Tool:
        execute it and record the Observation
    else:
        return the final answer
```

That loop is the subject of Stage 01.

Notice the order in which the abstraction appeared. We are not building a Runtime because “Agent architectures are supposed to have one.” We are building it because the fixed two-call script has reached a real limitation. Useful abstractions are usually pushed into existence by concrete pain.

---

## 7. A few misconceptions to eliminate now

“The model knows the Tool name, so it can run the Tool.” No. It can generate the name. The application still owns the handler and execution boundary.

“Structured Output is valid JSON, so the content is reliable.” No. Structure and truth are separate properties.

“A Tool Call means the action succeeded.” No. It means the model requested the action. Success exists only after execution.

“The model says it already did it.” That is still generated text. Inspect the execution trace, not the confidence of the wording.

These sound obvious when written plainly. Real Agent failures often come from quietly forgetting one of them in a larger system.

---

## 8. Small experiments that teach more than another page of definitions

Copy the chapter examples and change one assumption at a time.

Add a `confidence: float` field to `TaskCard`, constrained between 0 and 1. Then ask what `0.99` proves. It proves the model emitted a high confidence value. It does not provide external evidence that the judgment is correct.

Change the Tool Calling example from Tokyo to Paris and trace the string `Paris` all the way through generated arguments, application validation, the Python handler, and the Tool Output. That exercise usually makes Tool Calling feel much less mysterious.

Finally, draw two calls to the same Tool on paper and erase their `call_id` values. Within a minute, “that field looks redundant” starts to feel less convincing.

---

## 9. Before moving on, explain the execution path in your own words

You should be able to answer these without reciting definitions: Why is `response.output_text` not the entire Response? Why do `instructions` and `input` have different provenance? Which kind of correctness does Structured Output actually enforce? At what exact line does a Function Call become Python execution? What relationships do `call_id` and `previous_response_id` represent? Why does a teaching example prefer deterministic weather over live weather?

If you can answer those by tracing the code, you are ready for the Runtime chapter.

---

## 10. Chapter files

```text
stages/00-foundations/
├── README.md
├── README.zh-CN.md
└── code/
    ├── first_llm_call.py
    ├── structured_output.py
    ├── tool_calling.py
    └── requirements.txt
```

➡️ [Stage 01: Turn the Tool Loop into an Agent Runtime](../01-react-runtime/README.md)

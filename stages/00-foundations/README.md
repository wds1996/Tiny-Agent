# Stage 00: Start with One Model Call and Draw the Boundaries

> Language: **English** | [简体中文](README.zh-CN.md)

Many Agent tutorials begin with frameworks, plugins, memory, workflows, and multi-Agent diagrams. That is a little like handing someone a banquet menu when they have only just learned where the kitchen is. This chapter starts with the smaller and more useful question: **what actually happens when a Python program calls a language model?**

We will follow one continuous chain of necessity:

```text
generate text
    ↓
make the result reliably readable by software
    ↓
let the model request an external Tool
    ↓
have the application execute it and return the result
```

You will not finish this chapter with an all-powerful Agent. You will finish with something more valuable: a clear set of boundaries.

> **The model proposes. The application validates, executes, and owns the consequences.**

A model saying “the email was sent” does not send an email. Valid JSON does not make a claim true. A Tool Call can request an action, but confidence of tone is not a permission system.

Complete runnable programs live only in [`code/`](code/). The chapter uses focused excerpts where each mechanism is introduced; it does not paste every source file into the prose. Open the corresponding file when you want the complete implementation.

---

## 1. Learning goals

After completing this chapter, you should be able to:

- explain the responsibilities of the Python application, the model service, and the Response object;
- distinguish `instructions`, `input`, and the context visible to one model call;
- explain why natural language is useful for people but fragile as a software interface;
- define Structured Output with Pydantic;
- separate syntactic validity, structural validity, and factual correctness;
- explain the relationship among a Tool schema, a Tool Call, a Python handler, and a Tool Output;
- distinguish what `call_id` and `previous_response_id` correlate;
- validate a model-proposed Tool request before execution.

Basic Python functions, dictionaries, exceptions, and command-line use are enough to begin.

---

## 2. Prepare the environment

The examples require Python 3.10 or later, the OpenAI Python SDK, and Pydantic. From the repository root, run:

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

Do not place API keys in source code or commit them to Git. The examples also avoid hard-coding a model ID because model catalogs and project permissions change. Requiring `OPENAI_MODEL` makes configuration explicit instead of hiding it behind a mysterious default.

Each example uses the same helper:

```python
def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Set {name} before running this example.")
    return value.strip()
```

This is ordinary but important software engineering: **reject invalid input near the boundary.**

---

## 3. The first model call: treat the model as a remote computation service

Run:

```bash
python stages/00-foundations/code/first_llm_call.py
```

The complete program is [`code/first_llm_call.py`](code/first_llm_call.py). Its central request is:

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

From the application’s point of view, this is a request-response boundary:

```text
Python builds a request
        ↓
the model service generates output
        ↓
the SDK returns a Response object
        ↓
Python validates and consumes it
```

Two actors are involved:

- the **model service** generates output from visible context;
- the **application** sends requests, reads results, executes functions, and changes external systems.

Do not merge those roles mentally. A model is like a capable colleague working behind glass: it can read what you pass through the slot and return a recommendation, but it does not receive the building keys because the recommendation sounds confident.

### 3.1 Generation is not an external action

A plain text-generation call does not automatically:

- read a local file that was never supplied;
- query a private database;
- retrieve live weather;
- send an email;
- update an order;
- prove that a generated fact is correct.

If the response says, “The order was cancelled,” the only established event is that those words were generated. Whether an order system changed depends on application execution.

### 3.2 Probabilistic generation changes where contracts belong

Repeated calls with the same input may differ in wording or detail. A language model is not a pure function promising one byte-for-byte result for every input.

That produces two direct engineering rules:

1. do not make critical application logic depend on one exact sentence;
2. when software must consume a result, express and validate the machine-readable part as a contract.

Agent engineering does not remove uncertainty. It gives uncertainty a bounded place to live.

### 3.3 `instructions` and `input` have different sources

A practical distinction is:

```text
instructions
    application-level behavior and answer constraints

input
    the task or data being processed in this call
```

Avoid combining every source into one undifferentiated string:

```python
prompt = policy + user_question + documents + tool_result
```

That shortcut erases provenance. Later, the application cannot easily tell which text is a rule, which is user data, and which came from an external document.

For this chapter, one definition is enough:

> **Context is everything the model can actually see for one call.**

`instructions` and `input` both contribute to context. Context is not long-term storage, and it is not necessarily one giant string called “the prompt.”

### 3.4 A Response is not a bare string

The example checks the status and text before using them:

```python
if response.status != "completed":
    raise RuntimeError(f"The response did not complete: {response.status}")
if not response.output_text.strip():
    raise RuntimeError("The response completed without text output.")
```

Only then does it read:

```python
print(response.output_text)
```

`output_text` is an SDK convenience view. The complete Response can include:

```text
Response
├── id
├── status
├── model
├── output items
├── output_text
└── usage
```

“No exception was raised” and “the application received usable output” are different conditions. Explicit checks prevent an empty result from travelling deeper into the program and falling over somewhere much less helpful.

### 3.5 Token usage is accounting, not a quality score

The example prints usage when available:

```python
usage = response.usage
if usage is not None:
    print("input_tokens:", usage.input_tokens)
    print("output_tokens:", usage.output_tokens)
    print("total_tokens:", usage.total_tokens)
```

Token counts help reason about context size, latency, and cost. They do not certify correctness. A longer response can simply explain the same mistake with admirable persistence.

We can now generate text. The next problem is ordinary application design: **how can software consume the result without guessing what a sentence means?**

---

## 4. Structured Output: make the machine-readable part a contract

Suppose the application needs a task card. A person can understand:

```text
This seems important. We probably need current weather data first.
```

A program cannot safely depend on it. This is brittle:

```python
if "important" in answer.lower():
    priority = "high"
```

Replace `important` with `urgent` and the interface silently changes.

The application would rather receive a defined object:

```json
{
  "goal": "compare current weather in Tokyo and Paris",
  "priority": "medium",
  "needs_external_data": true,
  "reason": "current weather must be retrieved"
}
```

Structured Output is not merely JSON-looking text. It is model output constrained to a machine-verifiable structure.

Run:

```bash
python stages/00-foundations/code/structured_output.py
```

The complete program is [`code/structured_output.py`](code/structured_output.py).

### 4.1 Define application data before asking the model to fill it

The chapter uses Pydantic:

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

This contract expresses field names, types, required values, enum choices, and whether undeclared fields are allowed.

The design order matters:

```text
decide what the application needs
        ↓
express it as a schema
        ↓
ask the model to produce that shape
```

Letting the model improvise first and mining fields afterward creates a moving interface.

### 4.2 Parse into the application type

The central call supplies the Pydantic model:

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

The parsed value is checked explicitly:

```python
task = response.output_parsed
if task is None:
    raise RuntimeError("The response contained no parsed TaskCard.")
```

Downstream code can use `task.priority` and `task.needs_external_data` instead of performing archaeology on a paragraph.

### 4.3 Syntax, structure, and truth are different tests

Structured Output is often mistaken for a correctness guarantee. Separate three layers:

| Layer | Question | Can the schema enforce it? |
|---|---|---|
| Syntax | Can the JSON be parsed? | Yes |
| Structure | Are fields, types, and allowed values valid? | Yes |
| Semantics and facts | Is the judgment sensible and the claim true? | Not by itself |

This object may satisfy the schema and still be wrong:

```json
{
  "goal": "compare current weather",
  "priority": "high",
  "needs_external_data": false,
  "reason": "the model already knows it"
}
```

The fields are valid, but `needs_external_data=false` is a poor conclusion for a live-weather request.

The key rule is:

> **Structured Output solves “how can the program read this?” It does not, by itself, solve “why should the program believe this?”**

A schema is a diligent receptionist: it checks the form and required fields. It is not also an investigative journalist.

### 4.4 Appropriate uses and non-uses

Structured Output is useful for:

- classifications;
- argument extraction;
- routing decisions;
- form-shaped data;
- plans or judgments that ordinary code must inspect.

It is not, by itself:

- an external fact source;
- execution permission;
- a database transaction;
- proof that the conclusion is true.

The weather request exposes the remaining gap: the application needs data the model should not invent. That is where Tool Calling enters.

---

## 5. Tool Calling: the model requests, the application executes

When a task requires a database lookup, calculation, API call, or file operation, text generation alone is insufficient. The application can describe capabilities that the model may request.

A Tool has two faces:

```text
model-facing interface
├── name
├── description
└── parameters (JSON Schema)

application-side implementation
└── Python handler
```

The model normally sees the interface, not direct control of the handler.

This chapter uses deterministic teaching data:

```python
TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}
```

It is not live weather. Fixed data keeps the result reproducible and lets us study the control boundary without debugging networking, third-party authentication, rate limits, and meteorology at the same time.

Run:

```bash
python stages/00-foundations/code/tool_calling.py
```

The complete program is [`code/tool_calling.py`](code/tool_calling.py).

### 5.1 The Tool schema is an operating manual for the model

The central definition is:

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

A Tool description is part of the control surface, not decorative documentation. The model uses the name, description, and parameter structure to decide when the capability applies and how to populate arguments.

A useful description states what the Tool returns, when it should be used, what important parameters mean, and any material limitation. A description such as `query things` does not create flexibility; it creates guessing.

### 5.2 The handler is the code that actually acts

The Python function performs the lookup:

```python
def get_teaching_weather(city: str) -> dict[str, Any]:
    try:
        record = TEACHING_WEATHER[city]
    except KeyError as exc:
        raise ValueError(f"Unsupported city: {city}") from exc
    return {"city": city, **record}
```

Three events must remain distinct:

```text
a Tool is described to the model
        ≠
the model requests the Tool
        ≠
the application executes the handler
```

The first two do not automatically cause the third.

### 5.3 First model turn: produce an action proposal

The example deliberately forces one function request so the mechanism remains deterministic:

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

- `tools` describes available capabilities;
- `tool_choice` forces the named function for this teaching path;
- `parallel_tool_calls=False` keeps the turn to one call.

At this point, the model has emitted a Function Call. The Python function has not run. The output is an action request, not an execution record.

### 5.4 Provider output is still external input

The application extracts and checks the request:

```python
calls = [item for item in first.output if item.type == "function_call"]
if len(calls) != 1:
    raise RuntimeError(...)

call = calls[0]
if call.name != "get_teaching_weather":
    raise RuntimeError(...)
```

Then it parses, validates, and executes:

```python
arguments = parse_arguments(call.arguments)
city = validate_weather_arguments(arguments)
result = get_teaching_weather(city)
```

The order matters:

```text
read the proposal
    ↓
parse JSON
    ↓
validate fields, types, and allowed values
    ↓
call an explicitly allowed Python function
```

Do not feed a generated name into `eval()`, `exec()`, `globals()`, or arbitrary imports. Model output is data, not executable authority.

The example keeps two layers of constraint:

```text
provider-side strict schema
    helps constrain generated argument shape

application-side validation
    checks the concrete data about to reach the handler
```

The application owns execution, so it owns the final check on accepted arguments.

### 5.5 `call_id` preserves cause and effect

After execution, the application sends a Tool Output:

```python
{
    "type": "function_call_output",
    "call_id": call.call_id,
    "output": json.dumps(result, ensure_ascii=False),
}
```

`call_id` identifies which request produced the result. Two calls can share a Tool name and still be different actions:

```text
call_A → get_teaching_weather(Tokyo)
call_B → get_teaching_weather(Paris)
```

The name answers “which capability?” The call ID answers “which invocation?” Without it, the application has two bowls labelled “noodles” and no idea which table ordered which one.

### 5.6 Second model turn: continue from the real Tool Output

The second request chains from the first Response:

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

The identifiers correlate different relationships:

```text
previous_response_id
    which provider Response this new Response continues

call_id
    which Tool request this Tool Output answers
```

`tool_choice="none"` asks the model to stop requesting Tools for this example and produce text from the returned result.

The full timeline is:

```text
user supplies a task
    ↓
model emits a Function Call proposal
    ↓
application validates name and arguments
    ↓
application executes Python
    ↓
application returns a Function Call Output
    ↓
model generates final text from the observation
```

That is the first complete `model → tool → model` round trip.

---

## 6. Four similar-looking objects with different responsibilities

| Concept | What it is | What it is not |
|---|---|---|
| Text output | Generated language | A real-world action |
| Structured Output | Generated data satisfying a contract | Proof of factual truth |
| Tool Call | A structured action request | Evidence that Python already ran |
| Tool Output | An observation after application execution | The model’s unsupported guess |

An administrative analogy helps:

```text
Structured Output  a correctly completed form
Tool Call           a submitted action request
Tool Execution      staff actually performing the action
Tool Output         the returned receipt
```

A beautifully completed form still does not stamp itself.

---

## 7. Where the Runtime-shaped problem begins

The final example is still a fixed script:

```text
first model call
→ execute one Tool
→ second model call
→ stop
```

Now consider:

```text
read Tokyo's teaching weather
→ convert Celsius to Fahrenheit
→ answer from both results
```

That path may require two Tool Calls. Naming variables `first`, `second`, and `third` works until the route changes again and the control flow starts maintaining a family tree.

The repeated shape needs abstraction:

```python
while the run has not finished:
    ask the model for the next decision
    if it requested a Tool:
        execute and record the observation
    else:
        return the final answer
```

The next chapter builds that Runtime. Stage 00 stops here deliberately. At this point, keep four boundaries clear: model call, Tool request, Tool execution, and Tool Output.

---

## 8. Common mistakes worth naming early

### “The model knows the function name, so it can run the function.”

It can generate the name. The application must possess the implementation, allow it, validate the arguments, and invoke it.

### “Strict schema generation means local validation is unnecessary.”

Provider constraints help produce valid data. The execution boundary still checks the concrete input it will use.

### “Valid JSON means trustworthy content.”

JSON establishes syntax and structure. Trust requires evidence, source quality, or application rules.

### “A Tool Call tells me whether execution succeeded.”

A Tool Call only requests execution. Success or failure exists after the handler runs.

### “A confident sentence is evidence.”

Tone is a generation style, not a provenance record. Inspect the data flow and execution trace, not the firmness of the punctuation.

### “More context always makes the model smarter.”

The model acts on context visible to the current call. More text is not automatically more relevant or authoritative. This chapter establishes the boundary without yet designing a context-selection system.

---

## 9. A small failure map

| Failure | First owner of the check |
|---|---|
| Missing environment variable | Application startup boundary |
| Incomplete provider response | API calling code |
| Empty final text | Output validation boundary |
| Unparseable Structured Output | Structured Output boundary |
| Tool arguments are invalid JSON | Argument parsing boundary |
| Tool name is unknown | Tool routing boundary |
| Fields, types, or values are invalid | Application validation boundary |
| Python handler raises | Tool execution boundary |

Keeping errors attached to their layer is much more useful than the universal diagnosis, “the Agent seems confused.”

---

## 10. Exercises

### Exercise 1: prove prose parsing is brittle

Ask the model to express priority with `important`, `urgent`, and `high priority`. Try to parse all three with string rules and record how quickly the patch list grows.

### Exercise 2: add a confidence field

Add `confidence: float` constrained to 0–1 to `TaskCard`. Then explain why `0.99` still does not prove the judgment is correct.

### Exercise 3: create a structurally valid semantic error

Use a request that clearly needs live data, but steer the model toward `needs_external_data=false`. Observe why the schema may still accept it.

### Exercise 4: request the Paris teaching record

Change only the user input. Trace `Paris` through generated arguments, local validation, the handler, and the Tool Output.

### Exercise 5: remove the call ID on paper

Draw two calls to the same Tool and remove their IDs. Try to associate each result with its request.

### Exercise 6: make argument validation fail

Test these shapes conceptually or in a copy:

```json
{}
{"city": 42}
{"city": "Atlantis"}
{"city": "Tokyo", "debug": true}
```

Identify the correct rejection layer for each one.

### Exercise 7: separate wording from execution

Have the model generate “the Tool completed successfully” without running the handler. Inspect application state and explain why the sentence is not execution evidence.

---

## 11. Check your understanding

Explain these from the data flow rather than from memorized definitions:

1. Why is `response.output_text` not the entire Response?
2. What different roles do `instructions` and `input` play?
3. Which layers of correctness can Structured Output enforce, and which can it not?
4. Who consumes the Tool schema, and who owns the handler?
5. At what exact point does a Tool Call become Python execution?
6. Why should the application validate Tool arguments again?
7. What does `call_id` correlate, and what does `previous_response_id` correlate?
8. Why is deterministic teaching data better than live weather for this chapter?
9. Why is the fixed two-call example not yet a general Agent Runtime?

If you can answer those questions by tracing the program, the foundation is ready.

---

## 12. Chapter files

```text
stages/00-foundations/
├── README.md
├── README.zh-CN.md
└── code/
    ├── first_llm_call.py      # first Responses API call
    ├── structured_output.py   # Pydantic Structured Output
    ├── tool_calling.py        # complete model → tool → model round trip
    └── requirements.txt
```

Complete implementations are maintained only under `code/`; snippets in the chapter explain individual mechanisms.

➡️ [Stage 01: Turn the Tool Loop into an Agent Runtime](../01-react-runtime/README.md)

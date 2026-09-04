# Stage 01: Turn the Tool Loop into an Agent Runtime

> Language: **English** | [简体中文](README.zh-CN.md)

Stage 00 deliberately stopped at an awkward but useful point. The application could let the model request one Tool, Python could execute it, and the result could go back to the model. What the program could not do was handle an unknown number of decisions cleanly.

Imagine hiring an assistant and hard-coding today's route: first visit the archive, then perform one calculation, then report back. That works until tomorrow's task needs no archive visit, or two lookups, or a second decision after new information arrives. You do not want to begin every morning by guessing how many variables named `first_response`, `second_response`, and `third_response` the assistant will need.

So this chapter is not really about adding another Tool. It is about a deeper problem:

> **When the model may choose the next step on every turn, how does the application contain that uncertainty inside a controlled loop?**

That loop is the heart of an Agent Runtime.

Complete runnable programs still live only in [`code/`](code/). The prose uses focused excerpts so we can reason about one mechanism at a time without maintaining a second copy of the implementation in Markdown.

---

## 1. Where the fixed script becomes clumsy

The Stage 00 example can be summarized as:

```python
first = call_model(user_request)
call = read_tool_call(first)
result = execute(call)
final = call_model(result)
return final.output_text
```

There is nothing wrong with that code for a task that always needs exactly one Tool call. In fact, for a tiny deterministic task, it is clearer than a framework-heavy abstraction.

The problem is that the path is encoded in the program structure.

Ask instead:

> Read Tokyo's teaching weather and convert the temperature to Fahrenheit.

A sensible path may be:

```text
user
  ↓
model: get_teaching_weather("Tokyo")
  ↓
application: 18.0°C, cloudy
  ↓
model: celsius_to_fahrenheit(18.0)
  ↓
application: 64.4°F
  ↓
model: final answer
```

Another task may require no Tool at all. A third may need a Tool result before the model can decide what to do next.

The application does not know the number of turns in advance. What it does know is a repeated rule: ask the model for one decision, execute requested Tools, record observations, and continue until the model finishes or the application stops the run.

In pseudocode:

```python
for step in range(max_steps):
    turn = model.generate(messages, tools)

    if turn.final_text is not None:
        return turn.final_text

    for call in turn.tool_calls:
        observation = execute(call)
        messages.append(observation)

raise MaxStepsExceeded
```

Everything else in this chapter exists to make the responsibilities around that loop explicit. We are not adding classes to make a short loop look impressive.

---

## 2. Workflow, Agent, and Runtime: ask who chooses the next step

Before writing the Runtime, clear up one idea that tends to become fuzzier the longer people work with LLM applications: does using a model automatically make a system an Agent?

No.

Consider a deterministic workflow:

```python
weather = get_weather("Tokyo")
fahrenheit = celsius_to_fahrenheit(weather["temperature_c"])
return format_answer(weather, fahrenheit)
```

The developer already chose the steps, their order, and the routing. `format_answer()` could even call an LLM and the overall control flow would still be deterministic.

An Agent loop changes one important thing: the model receives limited authority to choose the next semantic step.

```python
turn = model.generate(messages, available_tools)
```

It may return a final answer, request the weather Tool, or request the conversion Tool. But “may choose the next step” does not mean “owns the process.” The model is still selecting from outputs the Runtime understands and capabilities the application exposes.

A short phrase helps keep the roles straight:

> **The Model proposes the next step. The Runtime manages the next step. The Tool implements the next step.**

The Runtime is closer to a stage manager than an actor. It does not provide the intelligence, but it controls when the scene begins, which props exist, and when the performance must stop.

### 2.1 When you should prefer a Workflow

Do not treat Agent loops as the default “advanced” version of a program. If the next step can be chosen reliably with ordinary code, use ordinary code. Deterministic workflows are easier to test, easier to budget, and easier to explain.

An Agent becomes useful when the task genuinely requires the model to interpret open-ended language or observations and decide what semantic action should happen next.

That is a trade: more flexibility in exchange for more control complexity. Use it when the task earns the complexity.

---

## 3. ReAct without the mythology

You will see the term ReAct frequently. It comes from Reasoning and Acting. Older examples often show a transcript like:

```text
Thought: I need the weather first.
Action: get_weather
Observation: ...
Thought: Now I should convert the temperature.
```

That is a useful teaching picture, but it is a poor requirement for a Runtime. The Runtime does not need the model's private chain of thought. It needs observable events that software can record and validate.

For this chapter, ReAct means:

```text
Decision
   ↓
Action / Tool Call
   ↓
Application executes
   ↓
Observation
   ↓
Next Decision
```

If your controller depends on text formatting such as:

```python
if "Action:" in model_text:
    ...
```

then your execution protocol is built on punctuation. One missing colon and the system suddenly forgets how to operate.

Structured Tool Calls solve that problem by making the action request data rather than prose.

---

## 4. The Runtime needs its own small internal language

Provider responses are usually rich objects. They may contain output items, function calls, response IDs, status fields, and provider-specific state.

You can certainly write a Runtime that directly inspects those objects:

```python
for item in response.output:
    if item.type == "function_call":
        ...
```

The price is coupling. The core loop now knows how one provider encodes function calls.

Instead, ask what the Runtime actually needs.

For one Tool request:

```python
@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
```

For one model decision:

```python
@dataclass(frozen=True)
class ModelTurn:
    final_text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
```

That is enough for the loop to decide whether to stop or act.

### 4.1 Why `ModelTurn` forces one exit

The implementation rejects a turn that contains neither final text nor Tool Calls, and it also rejects one that contains both:

```python
has_final = self.final_text is not None
has_calls = bool(self.tool_calls)

if has_final == has_calls:
    raise InvalidModelTurnError(
        "A model turn must contain exactly one of final_text or tool_calls"
    )
```

A real provider may support more complicated output combinations. Our internal protocol does not have to copy every external possibility.

The benefit is a clean state transition:

```text
ModelTurn(final_text=...)
    → END

ModelTurn(tool_calls=...)
    → ACT → OBSERVE → NEXT TURN
```

This is one of the quiet advantages of an Adapter layer: the external protocol may be complicated without forcing the Runtime to be equally complicated.

### 4.2 Why Tool Call IDs must remain unique

The Runtime also rejects repeated call IDs within a run. Tool Outputs are correlated back to Tool Calls through those IDs. Reusing the same ID for unrelated actions is like printing the same tracking number on two different packages. The simple example may survive it; a longer trajectory will not.

---

## 5. A Tool is more than a Python function

For a quick demo, a dictionary of handlers is enough:

```python
handlers = {
    "get_weather": get_weather,
    "convert": convert,
}
```

A reusable Runtime needs a little more. The model needs a description and parameter schema. The application needs a handler and a validation boundary.

The chapter's Tool object puts those pieces together:

```python
@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: Callable[[Any], Any]
```

The model-facing side comes from `name`, `description`, and the JSON Schema generated from `arguments_model`. The application-side behavior is the handler.

### 5.1 Validate again at the execution boundary

The weather Tool uses a strict Pydantic model:

```python
class WeatherArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    city: Literal["Tokyo", "Paris"]
```

Before the handler runs:

```python
arguments = self.arguments_model.model_validate(raw_arguments)
```

The provider may already constrain normal generation with a strict schema. That does not remove the Runtime's responsibility to validate the concrete input it is about to execute.

This is ordinary backend thinking. A browser form may validate input too; the server still validates before writing to a database because the server owns the consequence.

### 5.2 The Registry is the first capability boundary

The Runtime never looks up arbitrary generated names in the Python global namespace. It executes only registered Tools:

```python
tool = self._tools.get(call.name)
if tool is None:
    raise UnknownToolError(f"Unknown tool: {call.name}")
```

A Registry is not a complete authorization system, but it establishes an essential rule: **a generated name does not create a capability.**

If the model requests `delete_everything` and the application never registered such a Tool, nothing becomes executable merely because the string exists.

---

## 6. Walk through the Runtime one turn at a time

The complete implementation is in [`code/runtime.py`](code/runtime.py). Run it before reading further:

```bash
python stages/01-react-runtime/code/runtime.py
```

It uses a deterministic `ScriptedWeatherModel`, so no API key is required. You should see a trajectory similar to:

```text
[1] ACTION  get_teaching_weather({'city': 'Tokyo'})
[1] OBSERVE {"city": "Tokyo", "temperature_c": 18.0, "condition": "cloudy"}
[2] ACTION  celsius_to_fahrenheit({'temperature_c': 18.0})
[2] OBSERVE {"temperature_f": 64.4}
[3] FINAL   Tokyo's deterministic teaching record is 18.0°C (64.4°F), cloudy.
```

The easiest way to understand the Runtime is to follow `AgentRuntime.run()` rather than reading every class top to bottom.

### 6.1 The application owns the run transcript

A run begins with explicit state:

```python
messages: list[dict[str, Any]] = [
    {"role": "user", "content": user_input}
]
```

When the model requests Tools, the Runtime records the request:

```python
messages.append(
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [asdict(call) for call in turn.tool_calls],
    }
)
```

After execution, it records the Observation:

```python
messages.append(
    {
        "role": "tool",
        "tool_call_id": call.call_id,
        "name": call.name,
        "content": observation,
    }
)
```

This is worth pausing on because people often say “the model remembers what happened.” In this implementation, the more precise statement is: **the application records what happened and includes that record in the next model call.**

The state is explicit and inspectable. That makes the Runtime easier to test and debug.

### 6.2 One turn, one decision

The center of the loop is:

```python
for step in range(1, self.max_steps + 1):
    turn = self.model.generate(messages, self.registry.schemas())
```

If the turn contains final text, the Runtime stops:

```python
if turn.final_text is not None:
    return RunResult(...)
```

If the turn contains Tool Calls, the Runtime executes them:

```python
for call in turn.tool_calls:
    result = self.registry.execute(call)
```

The Runtime does not decide which Tool the model should choose. It enforces the process around that choice.

That distinction is the core of the architecture: semantic choice belongs to the model; execution control belongs to the application.

### 6.3 Multiple Tool Calls do not imply concurrent execution

`ModelTurn` can represent more than one Tool Call, but the current Runtime uses a normal loop:

```python
for call in turn.tool_calls:
    result = self.registry.execute(call)
```

So execution is sequential.

This is an easy place to over-read the term “parallel Tool Calls.” A model may propose several calls in one turn. Whether the Runtime executes them concurrently is a separate engineering decision involving shared state, cancellation, partial failures, and ordering. This chapter keeps execution synchronous and easy to reason about.

### 6.4 What `max_steps` actually counts

If the model never finishes, the Runtime eventually raises:

```python
raise MaxStepsExceeded(
    f"The run did not finish within max_steps={self.max_steps} model turns"
)
```

`max_steps` counts model decision turns, not the total number of Tool invocations. One turn may contain several calls.

This is a basic execution budget, not a complete cost or timeout system. Still, it matters. An unbounded `while True` looks pleasantly simple until the model discovers a loop and the invoice becomes a performance metric.

---

## 7. “The Agent failed” is not a useful error category

Follow the path through the Runtime and you can see several distinct failure locations.

If the model returns something that violates the internal protocol, that is an `InvalidModelTurnError`. If it requests an unregistered Tool, that is an `UnknownToolError`. If Pydantic rejects the arguments, that is a `ToolArgumentsError`. If the arguments are valid but the Python handler itself fails, that is a `ToolExecutionError`.

They may all result in an unfinished task, but they belong to different owners.

That distinction tells you where to look. An unknown Tool suggests a capability or model-selection problem. Invalid arguments suggest a schema or input problem. A handler exception points to application code or an external service.

This is much better than the universal diagnosis, “the Agent seems confused.”

### 7.1 Why Tool failure stops the run in this chapter

Another valid design is to convert a Tool error into an Observation and let the model try again. Many systems do that.

The moment you add automatic recovery, however, new questions appear: Is the operation safe to repeat? Did it partially change state before failing? How many retries are allowed?

Those are important reliability questions, but they are not free. This chapter chooses an intentionally simple rule: **a Tool execution failure ends the run.**

That makes one fact easy to reason about: you know exactly how many times the handler ran. We can add more sophisticated recovery only after the base semantics are clear.

---

## 8. Why a scripted Model is better than a real Model for testing the Runtime

If your first Runtime test uses a live model, a failed trajectory leaves you with an annoying ambiguity: did the Runtime break, or did the model simply make a different choice this time?

`runtime.py` therefore includes a deterministic model double:

```python
class ScriptedWeatherModel:
    ...
```

It has no language intelligence. With no Tool observations it requests weather; after one observation it requests conversion; after two it returns final text.

That lack of intelligence is exactly what makes it useful. The controller can now be tested with a stable input-output sequence.

The Runtime depends on a small Protocol:

```python
class Model(Protocol):
    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        ...
```

A real provider Adapter and a scripted test double both satisfy the same contract. The Runtime does not need a separate loop for each one.

A useful testing habit for Agent systems is: **when you are testing control logic, remove model randomness whenever you can.**

---

## 9. Test the trajectory, not only the final sentence

Run the chapter checks:

```bash
python stages/01-react-runtime/code/runtime_checks.py
```

The complete tests live in [`code/runtime_checks.py`](code/runtime_checks.py).

The happy-path test checks the final answer:

```python
self.assertIn("64.4°F", result.answer)
```

But it also checks the Tool call correlation IDs in the transcript:

```python
self.assertEqual(
    [message["tool_call_id"] for message in tool_messages],
    ["call-weather", "call-convert"],
)
```

Why inspect the trajectory? Because a final answer can be correct for the wrong reason.

Suppose a system is required to query a database before answering. The model guesses correctly once without using the Tool. A string-only test passes. A trajectory test reveals that the required action never happened.

The chapter checks also force unknown Tools, invalid arguments, handler failures, repeated call IDs, and a model that never finishes. Those “bad” examples are not edge-case decoration; they are executable definitions of the Runtime's boundaries.

A useful rule of thumb is: if you cannot write a deterministic counterexample for a claimed Runtime invariant, you may not have defined the invariant clearly enough yet.

---

## 10. Only now connect a real Provider

Once the core Runtime works offline, we can attach the OpenAI Responses API without modifying `AgentRuntime.run()`.

Configure:

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-id"
```

Then run:

```bash
python stages/01-react-runtime/code/openai_runtime.py
```

The complete Adapter is in [`code/openai_runtime.py`](code/openai_runtime.py). The key class is:

```python
class OpenAIResponsesModel:
    ...
```

It satisfies the same `Model.generate(...) -> ModelTurn` contract as the scripted model.

Its job is translation:

```text
Runtime Tool schema
      ↓
OpenAI function Tool

OpenAI function_call
      ↓
ToolCall

Runtime Tool Observation
      ↓
function_call_output
```

The core Runtime does not import the provider SDK or inspect provider-specific output objects. That is the real value of the Adapter. It is not “another class for architecture points”; it is a boundary that keeps unstable external protocol details from spreading into the control loop.

### 10.1 Why the Adapter remembers `previous_response_id`

After the first provider response contains a Tool Call, the next request must continue the same provider conversation chain.

The Adapter stores:

```python
self._previous_response_id: str | None = None
```

and later sends:

```python
request["previous_response_id"] = self._previous_response_id
```

That means the current Adapter instance carries run-level state. In this teaching implementation, one Adapter instance belongs to one Runtime run. Reusing it for unrelated user tasks could accidentally chain the second task onto the first provider response.

That is not a universal law about Adapters. It is the actual behavior of this implementation, and the tutorial should tell you so plainly.

### 10.2 Why only new Tool Outputs are submitted

The Runtime transcript contains the whole trajectory. Old Tool observations remain in `messages` on later turns.

The Provider should not receive the same `function_call_output` repeatedly, so the Adapter tracks submitted IDs:

```python
self._submitted_tool_call_ids: set[str] = set()
```

Only new Tool Outputs are sent in the next request.

This tiny detail illustrates why the Adapter boundary matters. The Runtime thinks in terms of “the run has an Observation.” The Provider cares about wire format, continuation IDs, and whether that Observation has already been submitted. Those are different concerns.

### 10.3 Why the live example disables parallel Tool Calls

The Adapter sends:

```python
"parallel_tool_calls": False,
```

This is a teaching choice, not a claim that the Runtime can only represent one call. `ModelTurn` still supports multiple `ToolCall` objects.

For the live example, a single-line trajectory is easier to inspect. Turning on concurrency would introduce execution ordering, shared side effects, cancellation, and partial failure before we have a reason to teach them.

Good teaching code should not enable every feature merely to prove the features exist.

---

## 11. What the minimal Runtime now gives you—and what it does not

At this point, the Runtime has more substance than a raw loop. The model speaks through a provider-neutral contract. Tools carry descriptions, schemas, and handlers. A Registry limits executable capabilities. The Runtime owns the transcript and stopping rule. Arguments are validated immediately before execution. Errors are separated by responsibility. A deterministic model double makes the control path testable offline. A Provider Adapter isolates external protocol details.

That is enough to call it a small, coherent Agent Runtime.

It is still deliberately small. Tool execution is synchronous and sequential. Run state lives in the current process. Tool failure ends the run. There is no automatic retry policy, no concurrent scheduler, and no extra persistence mechanism in this chapter.

Those are not hidden defects. They are the current specification.

One of the most useful habits in Agent engineering is to ask not only “what can this system do?” but also “what does this code explicitly not promise?” Marketing adjectives are poor substitutes for that answer.

---

## 12. Experiments that make the architecture stick

Instead of copying the Runtime again, change one assumption.

Make `ScriptedWeatherModel` return two Tool Calls in the same turn and observe the execution order. Then deliberately reuse a `call_id` and see where the internal protocol rejects it.

Add a third Tool such as `describe_temperature`, which maps a Fahrenheit value to `cold`, `mild`, or `hot`. Update the scripted model but do not modify `AgentRuntime.run()`. If adding one more Tool requires changing the core loop, the abstraction is not yet as general as it should be.

Make a handler raise an exception and compare two possible semantics on paper: stop the run immediately, or convert the error into an Observation and let the model try again. Before deciding which is “better,” ask whether the Tool has side effects and whether a retry could duplicate them.

Finally, set `max_steps=1`. The experiment makes one thing unmistakable: the model may choose a next action, but the application still owns the outer execution budget.

---

## 13. By the end of the chapter, you should be able to narrate one run

If I ask, “What is Tokyo's teaching weather, and what is that temperature in Fahrenheit?” you should be able to narrate the program, not recite an Agent formula.

The user input enters the Runtime. The Runtime gives the transcript and Tool schemas to the Model. The Model returns a `ToolCall`. The Runtime resolves it through the Registry. Pydantic validates the arguments. The handler executes. The result becomes a Tool Observation in the transcript. The next Model turn sees that Observation and requests the conversion Tool. A second Observation is recorded. Finally, the Model returns `final_text`, and the Runtime returns a `RunResult`.

If you can point to who owns control at each step, you understand the important part of the chapter.

You do not need to memorize a slogan such as “Agent = LLM + Tools + Memory + Planning.” It is more useful to open the code and know where decisions happen, where execution happens, where state lives, where invalid input is rejected, and where the loop is forced to stop.

---

## 14. Chapter files

```text
stages/01-react-runtime/
├── README.md
├── README.zh-CN.md
└── code/
    ├── runtime.py
    ├── openai_runtime.py
    ├── runtime_checks.py
    └── requirements.txt
```

Complete implementations are maintained only under `code/`; the chapter excerpts explain the mechanisms in context.

# Stage 01: Turn the Tool Loop into an Agent Runtime

> Language: **English** | [简体中文](README.zh-CN.md)

Stage 00 completed one fixed `model → tool → model` round trip: call the model, execute one requested Tool, call the model again, and produce the final answer.

It works because the program quietly assumes the entire route:

```text
the first turn requests a Tool
the Tool runs exactly once
the second turn finishes
```

Ask for “read the teaching weather, then convert Celsius to Fahrenheit,” and the code naturally grows variables named `first`, `second`, and `third`. Add a few more decisions and the variable names start needing a family registry.

This chapter addresses the actual problem:

> **When a model may request zero, one, or many Tools, how can the application organize those decisions into a bounded, testable, replaceable execution loop?**

We will build a small Agent Runtime from first principles. It first runs offline with a deterministic Model Double, then connects to the OpenAI Responses API through an Adapter.

Complete implementations live only in [`code/`](code/). The chapter explains each mechanism with focused excerpts instead of duplicating every source file. This keeps the lesson continuous without creating two copies of the code to maintain.

---

## 1. Learning goals

After completing the chapter, you should be able to:

- distinguish a deterministic Workflow, an Agent, a Model, a Tool, and a Runtime by asking who controls the next step;
- interpret ReAct as an observable `decision → action → observation` loop;
- explain why the Runtime should not depend directly on one provider’s Response classes;
- describe the contracts of `ToolCall`, `ModelTurn`, `Tool`, `ToolRegistry`, and `RunResult`;
- explain why a Tool needs both a model-facing schema and an application-side handler;
- distinguish provider-side generation constraints from runtime-side execution validation;
- trace one complete execution through `AgentRuntime.run()`;
- explain why the transcript is application-owned state rather than memory inside the model;
- show how `max_steps`, unique call IDs, and categorized errors bound execution;
- test the Runtime with a deterministic Model Double without a network call;
- explain how an Adapter translates provider protocol objects without changing the core loop.

---

## 2. Why the fixed script is not enough

The Stage 00 control flow can be summarized as:

```python
first = call_model(user_request)
call = read_function_call(first)
result = execute(call)
final = call_model(result)
return final.output_text
```

This is not bad code for a one-Tool task. Its limitation is that the **task trajectory** is embedded in the **program structure**.

A model may finish immediately:

```text
user → model → final answer
```

Or it may need two actions:

```text
user
  → model requests weather
  → application returns weather
  → model requests conversion
  → application returns conversion
  → model returns final answer
```

It may also change its next choice after seeing an Observation. The application cannot know how many variables named `next_response` to prepare.

The repeated shape needs one rule:

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

This small loop carries four responsibilities:

1. request one decision from the model based on current state;
2. map requested actions to application capabilities;
3. write execution results back into state;
4. continue, finish, or fail according to explicit rules.

Once those responsibilities are represented clearly, the fixed Tool loop becomes a Runtime.

---

## 3. Workflow, Agent, and Runtime: ask who chooses the next step

Using a language model does not automatically make a system an Agent. A more useful question is: **who decides the next step?**

### 3.1 Deterministic Workflow

```python
weather = get_weather("Tokyo")
converted = celsius_to_fahrenheit(weather["temperature_c"])
return format_answer(weather, converted)
```

The programmer fixes the steps, order, and branches. A model may participate in one step, but it does not control the route. This is a deterministic Workflow.

Its strengths are straightforward:

- behavior is easier to predict;
- testing is simpler;
- cost and call counts are easier to estimate;
- the model is not given control authority the task does not need.

### 3.2 Agent loop

```python
turn = model.generate(messages, available_tools)
```

The model can choose, within a constrained interface, whether to:

- return final text;
- request the weather Tool;
- request the conversion Tool;
- choose a different next action after observing a result.

The model receives limited authority over the next semantic step. It does not take ownership of the Python process; it can only use exits accepted by the Runtime.

### 3.3 Runtime carries the control process

The Runtime is not itself intelligent. It turns model decisions into a controlled execution trace:

```text
Model
    chooses the next semantic action

Runtime
    owns the loop, state, routing, execution, and stopping rules

Tool
    exposes a capability through a described and validated interface
```

A compact rule is:

> **The Model proposes the next step, the Runtime governs it, and the Tool implements it.**

A stage can host an actor, but the stage does not suddenly deliver the monologue. Likewise, a Runtime can carry Agent behavior without being the source of intelligence.

### 3.4 When an Agent is unnecessary

If ordinary conditions can choose the next step reliably, prefer deterministic code.

```text
Can a clear if/else choose the next step?
        ↓ yes
prefer a Workflow

        ↓ no, the choice depends on open language and observations
consider model participation
```

An Agent loop is not a more advanced default. It trades additional complexity for a more open decision space. The trade is useful only when the task needs that space.

---

## 4. ReAct: orchestrate observable events, not hidden thoughts

ReAct combines reasoning and acting. For this implementation, its useful engineering meaning is:

```text
Model Decision
      ↓
Action / Tool Call
      ↓
Application Execution
      ↓
Observation
      ↓
Next Model Decision
```

The Runtime handles observable, recordable objects:

- whether the model requested a Tool;
- the Tool name and arguments;
- the result returned by application execution;
- whether the model produced final text.

This chapter does not depend on the model emitting a `Thought:` string or exposing private chain-of-thought. A controller such as:

```python
if "Action:" in model_text:
    ...
```

makes program behavior depend on prose formatting. One missing colon should not disable the control plane.

We represent actions as structured `ToolCall` objects and observations as Tool messages. The loop operates on protocol data rather than on a literary convention.

### 4.1 Reasoning is not execution authority

A model may perform sophisticated reasoning internally. Its effect on the application is still limited to the outputs the Runtime recognizes. This chapter accepts two semantic exits:

```text
final_text
or
tool_calls
```

Model capability influences the choice. The Runtime contract determines how that choice can enter the system.

---

## 5. Three roles: Model, Runtime, and Tool

A minimal architecture looks like this:

```text
                   ┌──────────────┐
                   │    Model     │
                   │ decide next  │
                   └──────┬───────┘
                          │ ModelTurn
                          ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  messages    │◀─▶│   Runtime    │──▶│     Tool     │
│  run state   │   │ control loop │   │ validate/run │
└──────────────┘   └──────────────┘   └──────┬───────┘
                                             │
                                             ▼
                                        Observation
```

**Model** consumes current run state and Tool descriptions, then returns one provider-neutral decision.

**Tool** connects a model-facing capability description and argument contract to an application-side Python handler.

**Runtime** owns the loop. It invokes the Model, checks the returned value, routes a Tool, runs the handler, appends the Observation, and decides when execution stops.

When all three are mixed into one function, a provider response change can disturb Tool routing and control flow at the same time. Every failure then lands in one bucket labelled “AI logic,” which is not a useful place to debug anything.

---

## 6. Define an internal protocol before connecting a provider

The complete offline Runtime is in [`code/runtime.py`](code/runtime.py). Install the chapter dependencies and run it:

```bash
python -m pip install -r stages/01-react-runtime/code/requirements.txt
python stages/01-react-runtime/code/runtime.py
```

We first model only the data the Runtime actually needs. No OpenAI Response class appears in the core loop.

### 6.1 `ToolCall`: one proposed action

```python
@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
```

The Runtime needs three facts:

```text
call_id    which invocation is this?
name       which capability is requested?
arguments  what inputs were proposed?
```

`__post_init__` checks that the ID and name are non-empty strings and that arguments are a dictionary.

`frozen=True` prevents ordinary code from mutating a call after creation. Immutability is not a complete state model, but it reduces the chance that the call shown in the trace differs from the call eventually executed.

### 6.2 `ModelTurn`: one decision, one semantic exit

```python
@dataclass(frozen=True)
class ModelTurn:
    final_text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
```

This Runtime permits exactly one of two outcomes:

```text
A. final_text — finish the run
or
B. one or more tool_calls — execute, observe, continue
```

The invariant is explicit:

```python
has_final = self.final_text is not None
has_calls = bool(self.tool_calls)
if has_final == has_calls:
    raise InvalidModelTurnError(
        "A model turn must contain exactly one of final_text or tool_calls"
    )
```

If neither exists, the Runtime has no next state. If both exist, it is unclear whether the answer is final or actions must run first.

A provider may support richer mixed output. The internal protocol does not need to reproduce every provider possibility. It should represent only semantics the application deliberately supports.

The calls are stored in a tuple to match the frozen value object and to communicate that the call set for this turn is complete, not an open list awaiting unrelated mutation.

### 6.3 Call IDs must remain unique

`ModelTurn` rejects duplicate IDs within one turn. `AgentRuntime` also rejects reusing an ID anywhere in the run:

```python
repeated = [
    call.call_id for call in turn.tool_calls if call.call_id in seen_call_ids
]
if repeated:
    raise InvalidModelTurnError(
        f"Tool call IDs must be unique within a run: {repeated}"
    )
```

Observations are correlated through `call_id`. If one ID can refer to two actions, the transcript cannot uniquely answer which result belongs to which request.

### 6.4 The `Model` Protocol depends on behavior, not a vendor class

```python
class Model(Protocol):
    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        ...
```

Any object satisfying this contract can drive the Runtime:

- a deterministic test double;
- a local model Adapter;
- an OpenAI Responses Adapter;
- another provider integration.

The Runtime does not branch on `isinstance(model, OpenAI...)`. The point of the Protocol is not an extra layer of ceremony; it allows the controller to be tested without a network and without provider wire types.

---

## 7. A Tool combines interface, validation, and implementation

The chapter’s Tool value object is:

```python
@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: Callable[[Any], Any]
```

Each field serves a different boundary:

| Field | Primary consumer | Purpose |
|---|---|---|
| `name` | Model and Registry | identifies the capability |
| `description` | Model | explains when and why to use it |
| `arguments_model` | Model and Runtime | generates schema and validates execution input |
| `handler` | Runtime | performs the Python operation |

### 7.1 One argument model supports two separate checks

The Pydantic type produces a model-facing JSON Schema and validates concrete input at execution:

```python
class WeatherArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    city: Literal["Tokyo", "Paris"]
```

- `extra="forbid"` rejects undeclared fields;
- `strict=True` avoids unwanted coercion;
- `Literal` limits values to cities supported by the teaching dataset.

The Tool schema comes from:

```python
def schema(self) -> dict[str, Any]:
    return {
        "name": self.name,
        "description": self.description,
        "parameters": self.arguments_model.model_json_schema(),
    }
```

The execution boundary validates again:

```python
arguments = self.arguments_model.model_validate(raw_arguments)
```

These operations are not redundant:

```text
schema tells upstream what should be generated
validation checks what was actually received locally
```

Provider-side strict generation is a generation constraint. Runtime-side validation protects execution. The application owns the handler call, so it owns the final argument check.

### 7.2 Handlers receive validated objects

```python
def celsius_to_fahrenheit(
    arguments: TemperatureArguments,
) -> dict[str, float]:
    converted = round(arguments.temperature_c * 9 / 5 + 32, 1)
    return {"temperature_f": converted}
```

The handler no longer rummages through an untrusted dictionary and guesses field types. It receives a validated value and can focus on the operation.

### 7.3 Descriptions influence model behavior

This description is not useful:

```text
Convert stuff.
```

The chapter uses:

```text
Convert a Celsius value to Fahrenheit.
```

A good Tool description states what the capability returns, when it applies, what important arguments mean, and any material limitation.

Vague Tool design forces the model to guess. Replacing the model with a larger one afterward often produces a more eloquent guess, not a clearer interface.

---

## 8. `ToolRegistry`: a capability whitelist and a router

The model returns a string name. The Runtime must not dynamically execute any object with a matching name. It looks up only explicitly registered Tools:

```python
class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            self._tools[tool.name] = tool
```

Execution is a whitelist lookup:

```python
def execute(self, call: ToolCall) -> Any:
    tool = self._tools.get(call.name)
    if tool is None:
        raise UnknownToolError(f"Unknown tool: {call.name}")
    return tool.invoke(call.arguments)
```

This establishes a minimal capability boundary: only Tools explicitly registered by the application can enter the execution path. Generating `move_the_moon` does not cause the Runtime to acquire an orbital engineering department.

Be precise about the limit: the Registry is a capability whitelist, not a complete user-identity authorization system. It answers whether this application process possesses and exposes a capability; it does not decide whether a particular user may use it on a particular resource.

Duplicate names fail during construction. Otherwise, one name could refer to two handlers and behavior would depend on registration order.

The Registry exposes schemas to the Model, not handlers:

```python
def schemas(self) -> list[dict[str, Any]]:
    return [tool.schema() for tool in self._tools.values()]
```

The model sees capability descriptions. The application retains implementations.

---

## 9. Walk through `AgentRuntime.run()` one turn at a time

The complete implementation remains in [`code/runtime.py`](code/runtime.py). Follow the control flow through one run.

### 9.1 Create explicit run state

```python
messages: list[dict[str, Any]] = [
    {"role": "user", "content": user_input}
]
seen_call_ids: set[str] = set()
```

`messages` is the run transcript. The application owns it; it is not hidden memory inside the model.

This chapter uses three message roles:

```text
user
    the task

assistant
    final model text or a model Tool request

tool
    the Observation returned by application execution
```

`seen_call_ids` protects call/result correlation.

### 9.2 Ask for exactly one model decision per turn

```python
for step in range(1, self.max_steps + 1):
    turn = self.model.generate(messages, self.registry.schemas())
```

The Model receives current state and allowed Tool descriptions. It returns a `ModelTurn`, but it does not own the Python loop. The Runtime decides whether another turn happens.

The boundary checks the actual return value:

```python
if not isinstance(turn, ModelTurn):
    raise InvalidModelTurnError(
        "Model.generate() must return a ModelTurn"
    )
```

An Adapter’s promise to follow a Protocol is useful; validating the actual object is safer.

### 9.3 Final-text branch: record and finish

```python
if turn.final_text is not None:
    messages.append({"role": "assistant", "content": turn.final_text})
    return RunResult(
        answer=turn.final_text,
        model_turns=step,
        messages=tuple(messages),
    )
```

The final answer is added to the transcript. `RunResult` returns the answer, number of model turns, and full trace rather than discarding everything except one string.

### 9.4 Tool branch: record the request before execution

The Runtime first appends the assistant Tool Call:

```python
messages.append(
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [asdict(call) for call in turn.tool_calls],
    }
)
```

Then it executes each call:

```python
for call in turn.tool_calls:
    result = self.registry.execute(call)
```

Request first, Observation second. If the application stores only results, the trace suddenly contains weather data with no record of who requested it or with which arguments.

### 9.5 Return the Tool result as an Observation

```python
observation = json.dumps(result, ensure_ascii=False, default=str)
messages.append(
    {
        "role": "tool",
        "tool_call_id": call.call_id,
        "name": call.name,
        "content": observation,
    }
)
```

The next model turn can use a Tool result because the Runtime explicitly places it in state, not because Python execution creates telepathy.

A full trace looks like:

```text
user request
    ↓
assistant requests call-weather
    ↓
tool(call-weather) returns weather
    ↓
assistant requests call-convert
    ↓
tool(call-convert) returns Fahrenheit
    ↓
assistant returns final text
```

### 9.6 Multiple calls in one turn do not imply concurrency

`ModelTurn` can represent multiple calls, but this Runtime executes them with a normal `for` loop:

```python
for call in turn.tool_calls:
    result = self.registry.execute(call)
```

Therefore:

```text
multiple calls can be represented in one turn
        ≠
the calls execute concurrently
```

Sequential execution keeps completion order and side effects easier to reason about. This chapter does not put a “parallel” label on an ordinary loop and hope nobody inspects the engine.

### 9.7 `max_steps`: the model may propose continuing; the system may decline

If every turn requests another Tool, the Runtime eventually raises:

```python
raise MaxStepsExceeded(
    f"The run did not finish within max_steps={self.max_steps} model turns"
)
```

A step is one **model decision turn**, not one Tool call. A turn containing two calls still consumes one model step.

`max_steps` is a logical execution budget. It is not a wall-clock timeout and does not guarantee a fixed bill, but it prevents an unbounded decision loop. An unrestricted `while True` has a charming sense of adventure; invoices sometimes share the enthusiasm.

---

## 10. Why explicit state matters

The Runtime explicitly owns:

- the user request;
- every model Tool Call;
- every Tool Output;
- the final answer;
- all used call IDs.

This serves three purposes.

### 10.1 It gives the next turn necessary information

Without the Observation, the model cannot base the next decision on the Tool result.

### 10.2 It creates a testable trace

Tests can assert message order, call IDs, and model-turn count rather than checking only the final sentence.

### 10.3 It localizes failure

A bad result can be traced to Tool selection, arguments, handler behavior, or final synthesis.

The transcript exists only for one `run()` in memory. It is not cross-task long-term memory and does not automatically survive a process restart. The lesson here is narrower: **run state belongs to the application and must be represented explicitly.**

---

## 11. Why use `ScriptedWeatherModel` before a real model

Connecting a real model first looks more impressive but makes a poor controller test. If execution fails, two questions become entangled:

```text
Is the Runtime wrong?
Or did the model choose a different valid path this time?
```

`ScriptedWeatherModel` follows a deterministic script:

```python
observations = [m for m in messages if m.get("role") == "tool"]

if not observations:
    return ModelTurn(tool_calls=(weather_call,))

if len(observations) == 1:
    return ModelTurn(tool_calls=(conversion_call,))

return ModelTurn(final_text="...")
```

It is not trying to imitate language intelligence. It is a Model Double with a fixed transition:

```text
0 Observations → request weather
1 Observation  → request conversion
2 Observations → return final text
```

That isolates the Runtime:

- no API key is required;
- every trajectory is identical;
- the test cannot fail because a remote model used an unexpected synonym;
- failure points first toward the controller rather than “the model’s mood.”

Run:

```bash
python stages/01-react-runtime/code/runtime.py
```

Expected trace:

```text
[1] ACTION  get_teaching_weather({'city': 'Tokyo'})
[1] OBSERVE {"city": "Tokyo", "temperature_c": 18.0, "condition": "cloudy"}
[2] ACTION  celsius_to_fahrenheit({'temperature_c': 18.0})
[2] OBSERVE {"temperature_f": 64.4}
[3] FINAL   Tokyo's deterministic teaching record is 18.0°C (64.4°F), cloudy.
```

| Model turn | Model returns | Runtime does |
|---|---|---|
| 1 | weather Tool Call | validate, execute, append weather Observation |
| 2 | conversion Tool Call | validate, execute, append conversion Observation |
| 3 | `final_text` | append final message and return `RunResult` |

---

## 12. Errors need ownership, not one large bucket

The Runtime defines five error categories:

| Error | Meaning | First place to inspect |
|---|---|---|
| `InvalidModelTurnError` | Model output violates the internal protocol | Model or Adapter boundary |
| `UnknownToolError` | requested name is absent from the Registry | Tool routing |
| `ToolArgumentsError` | arguments fail Pydantic validation | Tool input contract |
| `ToolExecutionError` | the handler fails after valid input | Tool implementation or dependency |
| `MaxStepsExceeded` | the run does not finish within the turn budget | Model behavior and control budget |

### 12.1 Argument failure and execution failure are different

```text
{"city": "Atlantis"}
```

should fail before the handler as `ToolArgumentsError`.

Valid arguments entering a handler that then fails produce `ToolExecutionError`.

The repair paths differ. One points toward schema or generated inputs; the other points toward implementation or an external dependency. `except Exception: return "error"` does not simplify this distinction. It merely puts the error in witness protection.

### 12.2 This chapter chooses “failure stops the run”

`Tool.invoke()` wraps a handler exception and raises it:

```python
try:
    return self.handler(arguments)
except Exception as exc:
    raise ToolExecutionError(
        f"Tool {self.name!r} failed with {type(exc).__name__}"
    ) from exc
```

The Runtime does not retry automatically and does not return an error Observation to the model. That is an intentional simple policy: the number of handler executions remains easy to determine.

Retries are not a free reliability switch. Repeating a side-effecting Tool may be more damaging than the first failure. Without an explicit retry contract, “try again” is hope with a loop around it.

### 12.3 Error text is also part of the boundary

The wrapper preserves the Python causal chain with `raise ... from exc` while presenting a stable error category. Arbitrary internal exception details are not copied into a model Observation because this Runtime stops instead of asking the model to recover.

---

## 13. Deterministic tests should inspect the trajectory

Run the chapter checks:

```bash
python stages/01-react-runtime/code/runtime_checks.py
```

The complete suite is [`code/runtime_checks.py`](code/runtime_checks.py). It uses standard-library `unittest` and does not access the network.

### 13.1 The happy path checks more than the answer

```python
result = AgentRuntime(
    ScriptedWeatherModel(), build_tools(), verbose=False
).run("weather then conversion")

self.assertEqual(result.model_turns, 3)
self.assertIn("64.4°F", result.answer)
```

It also checks call correlation in Tool messages:

```python
self.assertEqual(
    [message["tool_call_id"] for message in tool_messages],
    ["call-weather", "call-convert"],
)
```

A correct final sentence can still emerge from a bad trajectory: duplicated side effects, bypassed validation, or mismatched results. Agent quality cannot be judged from the final prose alone.

### 13.2 Counterexamples reveal the contract

The suite includes:

- a Model that never finishes;
- a Model requesting an unknown name;
- a Model emitting invalid city arguments;
- a Model reusing a call ID;
- a Tool whose handler always raises;
- a fake provider client.

For example:

```python
with self.assertRaises(UnknownToolError):
    runtime.run("request an unregistered tool")
```

The important contract is not the exception class name. It is that a generated string cannot make an unregistered capability executable.

### 13.3 Why a real model is not a unit-test fixture

A live model is useful for end-to-end experiments. A unit test needs to answer whether a precise Runtime transition always follows from a precise input.

If the first explanation for a failed test is “the model may have phrased it differently today,” the test has not isolated the controller.

---

## 14. The Adapter keeps provider protocol outside the Runtime

The offline Runtime is complete. To connect a real model, configure credentials and run:

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-id"
python stages/01-react-runtime/code/openai_runtime.py
```

The complete Adapter is [`code/openai_runtime.py`](code/openai_runtime.py). Its goal is simple: **add a provider without changing `AgentRuntime.run()`.**

```text
OpenAI Response
      ↓
OpenAIResponsesModel
      ↓
ModelTurn / ToolCall
      ↓
AgentRuntime
```

### 14.1 Three translations belong in the Adapter

First, convert an internal Tool schema to a provider function Tool:

```python
@staticmethod
def _to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": tool["name"],
        "description": tool["description"],
        "parameters": tool["parameters"],
        "strict": True,
    }
```

Second, normalize provider `function_call` output into `ToolCall`:

```python
calls.append(
    ToolCall(
        call_id=item.call_id,
        name=item.name,
        arguments=arguments,
    )
)
```

Third, convert a Runtime Tool message into `function_call_output`:

```python
outputs.append(
    {
        "type": "function_call_output",
        "call_id": call_id,
        "output": str(message.get("content", "")),
    }
)
```

Provider-specific fields remain in the Adapter. The Runtime continues to speak only `ModelTurn` and `ToolCall`. The extra class exists to stop wire-format details from spreading through the controller.

### 14.2 `previous_response_id` chains provider Responses

The Adapter stores the most recent provider Response ID:

```python
self._previous_response_id: str | None = None
```

Later requests include:

```python
if self._previous_response_id is not None:
    request["previous_response_id"] = self._previous_response_id
```

The next turn can then send only newly produced Tool Outputs rather than manually reconstructing every provider output item.

When using `previous_response_id`, the request still supplies `instructions` explicitly. The Adapter does not assume that instructions from an earlier Response are automatically carried into the next request.

### 14.3 Submit only new Tool Outputs

The Runtime passes a complete transcript on every turn. If the Adapter re-sends every historical Tool message, one `call_id` may be submitted repeatedly.

It therefore tracks:

```python
self._submitted_tool_call_ids: set[str] = set()
```

`_next_input()` selects only unseen Tool Outputs. Internal state is updated only after the provider returns a valid completed Response:

```python
self._previous_response_id = response_id
self._submitted_tool_call_ids.update(pending_call_ids)
```

Validate first, commit Adapter state second. A failed request should not be recorded as successfully submitted.

### 14.4 One Adapter instance represents one run

`_previous_response_id` and `_submitted_tool_call_ids` belong to one execution trajectory. This chapter therefore defines:

```text
one OpenAIResponsesModel instance
        ↔
one AgentRuntime.run(...)
```

Do not share one instance across unrelated user tasks. That could attach a new task to an old provider Response chain. This is a constraint of this Adapter design, not a universal claim about every provider client.

### 14.5 Provider Responses are external input too

The Adapter verifies:

- `status` is `completed`;
- the Response ID is a non-empty string;
- function arguments decode to a JSON object;
- a turn without Tool Calls contains non-empty final text.

For example:

```python
try:
    arguments = json.loads(item.arguments)
except json.JSONDecodeError as exc:
    raise ProviderResponseError(
        f"Arguments for function {item.name!r} are not valid JSON"
    ) from exc
```

An Adapter is more than a field-name converter. It prevents malformed provider data from entering the internal protocol.

### 14.6 Why the live example disables parallel Tool Calls

The request sets:

```python
"parallel_tool_calls": False,
```

That keeps the live demonstration to one linear action per provider turn, matching the offline trace. The internal `ModelTurn` can still represent multiple calls; this particular integration deliberately chooses a narrower behavior.

That is a useful design pattern: an internal protocol can retain reasonable generality while one integration adopts a simpler policy for its current use case.

---

## 15. A control-authority inventory

In this Runtime, the Model may:

- choose final text or a Tool Call from the available interface;
- choose an exposed Tool name;
- propose Tool arguments;
- revise its next decision after seeing an Observation.

The Model may not directly:

- invoke an arbitrary Python object;
- bypass the Registry;
- bypass Pydantic argument validation;
- change `max_steps`;
- reuse a call ID without rejection;
- decide that an exception should be ignored;
- continue execution after returning final text.

Agent autonomy is not one switch. It is a set of deliberately allocated decisions. The clearer the allocation, the easier the system is to reason about.

---

## 16. The exact specification of this Runtime

The implementation provides:

```text
provider-neutral Model contract
Tool schema plus handler
runtime-side argument validation
Tool Registry routing
decision → action → observation loop
explicit transcript
call/result correlation
unique call IDs
model-turn budget
categorized errors
deterministic Model Double
offline tests
OpenAI Responses Adapter
```

It deliberately does not provide:

- asynchronous or concurrent Tool execution;
- automatic retries;
- model recovery from an error Observation;
- persisted run state;
- process-restart recovery;
- complete user authorization and side-effect policy;
- combined time, token, and cost budgets;
- streaming output;
- multi-user Adapter lifecycle management.

Listing omissions is not an apology. It is an accurate specification. One successful demo proves one path works; reliable reasoning also requires knowing how other paths stop.

---

## 17. Common mistakes

### “A Runtime is just a while loop.”

The loop is the shell. The important parts are the protocol, state ownership, Tool routing, validation, error categories, and stopping rules.

### “A Tool Call should be executed because the model returned it.”

The Runtime still checks the internal protocol, call ID, Registry name, and arguments. A Tool Call is a proposal, not privileged command authority.

### “A fake Model has no intelligence, so the test is meaningless.”

The object under test is the Runtime controller, not model capability. Determinism is precisely what isolates it.

### “Supporting multiple Tool Calls means the Runtime is concurrent.”

The data structure can represent multiple calls. Execution policy is a separate concern; this implementation remains sequential.

### “The final answer is correct, so the Agent succeeded.”

Correct prose can come from duplicated execution, mismatched observations, or bypassed validation. Result quality and trajectory quality are separate signals.

### “The Adapter is only unnecessary field conversion.”

The Adapter performs protocol translation and external-input validation. It keeps the Runtime independent of provider wire details.

---

## 18. Exercises

### Exercise 1: emit two Tool Calls in one turn

Make `ScriptedWeatherModel` request Tokyo and Paris weather in the first turn using different call IDs. Inspect execution and transcript order.

### Exercise 2: reuse a call ID deliberately

Use `call-weather` again in the second turn. Confirm that the Runtime rejects it before handler execution and explain which correlation invariant is protected.

### Exercise 3: add a third Tool

Create `describe_temperature`, accepting Fahrenheit and returning `cold`, `mild`, or `hot`. Modify the Tool set and scripted Model, but do not change `AgentRuntime.run()`.

If a normal new Tool requires a controller rewrite, task detail has leaked into the Runtime abstraction.

### Exercise 4: compare argument and execution failures

Produce both:

```text
{"city": "Atlantis"}
a valid input passed to a handler that always raises
```

Verify that they produce different error categories and identify different repair locations.

### Exercise 5: turn a Tool error into an Observation

In a copy, serialize the error and return it to the Model. Also add a maximum recovery-attempt count and track whether the handler may execute more than once. Compare this policy with “failure stops the run.”

### Exercise 6: remove Adapter deduplication

Delete `_submitted_tool_call_ids` and use `FakeResponsesAPI` to inspect a later request. Observe whether old Tool Outputs are sent again.

### Exercise 7: guard Adapter reuse

Make an `OpenAIResponsesModel` instance reject a second unrelated user task after one run finishes. Add a deterministic test for that lifecycle rule.

### Exercise 8: build the deterministic comparison

Write the same “weather → conversion → answer” task as a plain Workflow. Compare code size, predictability, and the additional decision authority purchased by the Agent loop. Do not assume the Agent version wins automatically.

---

## 19. Check your understanding

Answer from the control and data flow rather than memorized definitions:

1. Why can a fixed two-call script not represent a general Tool loop?
2. What is the key control difference between a Workflow and an Agent loop?
3. What does ReAct mean here, and why does the Runtime not parse `Thought:` text?
4. Why must `ModelTurn` choose exactly one of `final_text` and `tool_calls`?
5. At which boundaries do Tool schema, Pydantic validation, and the handler operate?
6. Why is the Registry both a router and a minimal capability whitelist?
7. Why record the assistant Tool Call before the Tool Observation?
8. What does `max_steps` count, and what does it not guarantee?
9. Why is a deterministic Model Double better than a live model for Runtime unit tests?
10. Why does the Adapter track both `previous_response_id` and submitted call IDs?
11. Why does one Adapter instance correspond to one run in this design?
12. How can correct final text still come from a failed trajectory?
13. Which tasks should remain deterministic Workflows rather than Agent loops?

If you can answer those by tracing the program, you understand more than how to “run an Agent.” You understand what governs it.

---

## 20. Chapter files

```text
stages/01-react-runtime/
├── README.md
├── README.zh-CN.md
└── code/
    ├── runtime.py          # provider-neutral Runtime and offline example
    ├── runtime_checks.py   # deterministic boundary tests
    ├── openai_runtime.py   # OpenAI Responses Adapter
    └── requirements.txt
```

Complete implementations are maintained only under `code/`; snippets in the chapter explain the mechanism currently under discussion.

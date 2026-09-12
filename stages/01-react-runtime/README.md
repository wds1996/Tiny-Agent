# Stage 01: After the Weather Lookup, There Is Still Work to Do — Building an Agent Runtime

> Language: **English** | [简体中文](README.zh-CN.md)

In [Stage 00](../00-foundations/README.md), Lin's travel-practice page learned to display Tokyo's teaching weather. The model requested a lookup, Python read a local record, and the application sent that record back. The temperature came from an actual function call, not from a lucky guess in a fluent answer.

Then Lin added a small request: “Some readers use Fahrenheit. Could you convert the temperature you found?” Small requests have a habit of finding architectural assumptions. Our previous program allowed one lookup and then required an answer. Now there is still a calculation to perform after the lookup. The assistant has more work to do, but the program is already reaching for its coat.

We will stay with this request throughout the chapter. First we make it possible to continue, then define the rules for continuing. Once lookup, conversion, and answering fit together, we try a request that needs no conversion and another that only asks for a greeting. The goal is one controller that handles different task lengths, not a separate sequence of API calls for every variation.

## 1. What actually changed when Lin asked for one more step?

Put classes and frameworks aside for a moment and carry out the task on paper. At the start, we know the city but not its record. After the lookup, we have 18.0°C and can supply a real input to the conversion. After the calculation, we have 64.4°F and can report both units. What we know changes as work happens, so what we can reasonably request next changes too.

```text
Lin: Read Tokyo's teaching weather and use the conversion tool for Fahrenheit
    ↓
First decision: get the record       → Python returns 18.0°C, cloudy
    ↓
Second decision: convert that 18.0°C  → Python returns 64.4°F
    ↓
Third decision: enough information   → answer and finish
```

That is two tool executions but three decisions. Producing the final answer takes a decision too; it simply does not ask for another tool. If Lin only wants Celsius, we can answer immediately after the lookup. If she only says hello, the first decision can finish the task. The improvement is therefore not “always arrange three calls.” It is “after each turn, decide whether more work is required.”

There is an important qualification. If the product always follows exactly the same lookup–convert–display route, ordinary Python calls are a perfectly good solution. A model need not chair a meeting about every line of code. Here we are exploring a different arrangement: let the model propose the next action using the request and the results obtained so far. That buys flexibility and creates a corresponding responsibility to check those proposals.

For now, think of a **Runtime** as the program that organizes this work. It asks for the next decision, checks tool requests, runs functions, records results, and decides whether another turn is permitted. The model proposes a choice, the tools perform concrete work, and the runtime holds the process together. The class names will give these responsibilities a home; the names are not the starting point.

Before the program can distinguish continuing from finishing, it needs a reply it can read without interpreting the model's tone of voice. We will agree on two explicit kinds of reply.

## 2. Is the assistant returning a request or an answer?

“I should probably look at the weather” makes sense to a person. It is not enough for software to know which function to invoke or which city to pass. Stage 00 addressed this with structured tool calls. We now represent such a request as a small Python object that the runtime can handle consistently.

`ToolCall` in [`runtime.py`](code/runtime.py) carries three pieces of information:

```python
@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
```

`name` identifies the tool, `arguments` holds its input, and `call_id` correlates this particular request with its eventual result. `@dataclass` generates routine methods such as initialization. `frozen=True` prevents assigning new values to the fields; it does not recursively freeze the dictionary inside them. The annotations describe expected types, while `__post_init__()` performs actual checks, such as rejecting an empty ID or non-dictionary arguments.

A request for the configured city's record can now be expressed directly:

```python
ToolCall("call-weather", "get_teaching_weather", {"city": self.city})
```

In the exercise, `self.city` comes from configuration and defaults to `Tokyo`. Constructing this object still does not perform a lookup. It neither calls a handler nor produces a weather record. It is an application-readable request to do that work.

The model might instead return its final answer. `ModelTurn` represents one decision, and the controller makes its continue-or-finish choice from these two fields:

```python
@dataclass(frozen=True)
class ModelTurn:
    final_text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
```

`None` means there is no final answer yet. An empty `tool_calls` tuple means there are no tool requests. Our internal contract permits exactly one kind of result. Neither leaves the controller with nothing to do; both leave it with an ambiguous instruction to finish and act at the same time.

The check is small enough to inspect in full:

```python
has_final = self.final_text is not None
has_calls = bool(self.tool_calls)
if has_final == has_calls:
    raise InvalidModelTurnError("Return either final_text or tool_calls, not both or neither.")
```

Equal booleans mean both are present or both are absent, so both cases are rejected. Final text must also be a non-empty string. This is an internal application contract, not a claim that every model provider returns only these two shapes. We will translate richer provider replies when we connect the service.

We can now tell what the assistant wants on this turn. But where will its second turn obtain the fact that the first lookup found 18°C?

## 3. Give the next turn a record of the work

Storing a lookup result in a Python variable does not make it visible to a remote model. A colleague on the telephone cannot see the notes you made after the previous call either. To continue sensibly, they need the original request, the work already requested, and the results actually returned.

The runtime maintains that record in `messages`. A new run starts with only Lin's request:

```python
messages: list[dict[str, Any]] = [{"role": "user", "content": user_input}]
```

Here, `role` identifies a message's source, not a personality: `user` for the request, `assistant` for the model's reply, and `tool` for the result recorded by the application. This is the chapter's internal representation. It need not be identical to a provider's network format.

After the first lookup, the relevant information looks like this. This is a compact reading of the record rather than its full JSON representation:

```text
user       Read Tokyo's teaching weather and convert it to Fahrenheit
assistant  call-weather → get_teaching_weather({"city": "Tokyo"})
tool       call-weather → {"temperature_c": 18.0, "condition": "cloudy", ...}
```

Why retain the request as well as the result? A number such as `18.0` alone does not say what unit it uses or which operation produced it. The tool name, input, and correlation ID place that result back into the task. The `call_id` from Stage 00 still does the same job: a request and its receipt carry the same identifier. Changing it casually would break the association.

The application owns this record. The next model call receives it and can use the new observation. In this implementation, “the model remembers” really means the application supplies the relevant history again. The list remains in the current process; it is not automatically saved when the program exits and does not establish cross-session memory.

We pass a copy to the model interface so ordinary adapter code cannot accidentally edit the runtime's original transcript through that argument. This is object management, not security isolation. Hostile Python code running in the same process is not confined by a copied dictionary.

Now that we know how to carry results forward, we need the functions that will actually produce them. Let us build the extra capability Lin requested.

## 4. Give each tool one concrete job

The weather tool still reads the fixed records from Stage 00: Tokyo has 18.0°C and cloudy conditions; Paris has 12.0°C and light rain. It returns the city, Celsius reading, condition, and `source="fixed teaching record"`. None of these values claims to describe today's live weather.

The conversion tool need not understand language at all. Multiply Celsius by `9/5` and add `32`; the exercise rounds to one decimal place. The model's job is to request the calculation with the observed reading, while an ordinary function performs it:

```python
def celsius_to_fahrenheit(arguments: TemperatureArguments) -> dict[str, float]:
    converted = round(arguments.temperature_c * 9 / 5 + 32, 1)
    return {"temperature_f": converted}
```

`TemperatureArguments` is a Pydantic input model, not another language-model service. As in Stage 00, we describe what the function accepts before calling it:

```python
class TemperatureArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    temperature_c: float
```

The value must be numeric. `strict=True` rejects a string such as `"18"`; `extra="forbid"` rejects additional fields; `allow_inf_nan=False` excludes infinity and NaN. A numeric integer `18` is acceptable for this float field—it need not arrive as `18.0`. Strict validation follows the rules of each type, rather than requiring every representation to be identical; see [Pydantic's strict-mode explanation](https://docs.pydantic.dev/latest/concepts/strict_mode/).

Weather input has a different rule: its city must be `Tokyo` or `Paris`. The runtime does not need a special execution branch for every parameter shape. Each tool groups its description, input model, and handler:

```python
Tool(
    name="celsius_to_fahrenheit",
    description="Convert a supplied numeric Celsius value to Fahrenheit.",
    arguments_model=TemperatureArguments,
    handler=celsius_to_fahrenheit,
)
```

The `handler` is the function that does the work. The model receives the name, description, and JSON Schema generated from the input model—not the function object. The application retains the function and calls it after validation. These are the two sides of a tool from Stage 00, now packaged consistently for more than one capability.

A `ToolRegistry` stores the tools the application explicitly registered. It answers a practical question: when the model returns a name, where does the program look? Not in all Python globals, and certainly not in `eval()`. It looks only in this registry:

```python
def prepare(self, call: ToolCall) -> tuple[Tool, BaseModel]:
    tool = self._tools.get(call.name)
    if tool is None:
        raise UnknownToolError(f"Unknown tool: {call.name}")
    return tool, tool.validate(call.arguments)
```

The result contains the selected tool and its validated input. No handler has run yet. Registering the same name twice is also rejected, so one name cannot ambiguously identify two implementations. This limits available capabilities; it is not a full user-authorization system. Nor does it decide whether a valid city matches the user's request. Valid arguments and a correct task result are different properties.

We now have enough pieces for the controller to stop caring about weather-specific implementation details. It can organize the same request–check–execute–record sequence around either tool.

## 5. Make one turn precise, then repeat it

The loop starts by giving the model interface the current record and tool descriptions:

```python
for step in range(1, self.max_steps + 1):
    turn = self.model.generate(deepcopy(messages), self.registry.schemas())
```

`step` counts how many model decisions this run has requested. `max_steps` sets the upper bound. `schemas()` supplies descriptions, and `deepcopy(messages)` supplies an independent copy of the transcript so far. The runtime also checks that the return value really is a `ModelTurn`; a bare string is not silently accepted as the whole contract.

The easiest branch is a final answer. The runtime records it and returns a `RunResult`:

```python
return RunResult(
    answer=turn.final_text,
    model_turns=step,
    messages=tuple(deepcopy(messages)),
    tool_executions=tool_executions,
)
```

Besides the answer, this preserves the decision count, the number of handler invocations, and the work record. `return` leaves the entire `run()` method, not just the current iteration. Once this branch is taken, the runtime does not continue down to execute tools.

The other branch receives tool requests. The runtime first records the requests, checks identifiers and budgets, and prepares their arguments. Once those checks pass, it executes them in order. Execution and recording meet here:

```python
observation = tool.execute(arguments)
messages.append({
    "role": "tool", "tool_call_id": call.call_id,
    "name": call.name, "content": observation,
})
```

An `observation` is what application execution produced, not what the model expected would happen. `Tool.execute()` calls the handler and encodes its return value as JSON text. It uses `allow_nan=False` and does not use `default=str` to disguise arbitrary Python objects as meaningful output. A result that cannot be represented as JSON produces an explicit failure rather than an object-address string masquerading as evidence.

This branch does not return, so control reaches the next iteration. `messages` now includes the request and its result. The second turn can request conversion using 18.0; the third can answer using 64.4. The controller never hard-codes “the second turn must be conversion.” It repeats the same rule.

This pattern borrows the action-and-feedback idea from **ReAct**. The [original ReAct paper](https://arxiv.org/abs/2210.03629) studied interleaving reasoning and actions. Our implementation uses structured tool calls for the executable, observable loop; it is not a full reproduction of the paper's prompting method. The controller does not search prose for `Thought:` or `Action:`, or inspect private chain-of-thought text to authorize execution.

We have a controller whose job we can explain. Before asking a live model to use it, let a predictable stand-in follow the route once. That will show whether the connections work.

## 6. Rehearse the route: where did the conversion input come from?

Live model replies can vary. When first checking a controller, we want to separate a wiring error from a model choosing a different path. The offline entry therefore uses a clearly labeled `ScriptedWeatherModel`. It is not a silent fallback when a real service fails.

This stand-in follows the `--task` and `--city` configuration; it does not understand arbitrary natural-language requests. With no weather result it asks for a lookup. If conversion was requested and no conversion result exists, it asks for the calculation. With the required observations available, it answers. The conversion request is built here:

```python
if self.task == "convert" and conversion is None:
    return ModelTurn(tool_calls=(
        ToolCall(
            "call-convert", "celsius_to_fahrenheit",
            {"temperature_c": weather["temperature_c"]},
        ),
    ))
```

The important detail is not the name `call-convert`. It is that the input comes from `weather["temperature_c"]`, rather than a hard-coded `18.0` in the second turn. The final city, Celsius value, and condition also come from observations. Changing the record should change what follows. Otherwise the program would be ceremonially reading data while continuing to recite a prepared answer.

From the repository root, install the dependencies and run the example. Use Python 3.10 or later. This offline path needs Pydantic but no model-service credentials:

```bash
python -m pip install -r stages/01-react-runtime/code/requirements.txt
python stages/01-react-runtime/code/runtime.py --language en
```

The first line of output explicitly identifies an `offline model double: no API request`. The English exercise follows this route:

```text
[1] ACTION  get_teaching_weather({'city': 'Tokyo'})
[1] OBSERVE {"city": "Tokyo", "temperature_c": 18.0, "condition": "cloudy", "source": "fixed teaching record"}
[2] ACTION  celsius_to_fahrenheit({'temperature_c': 18.0})
[2] OBSERVE {"temperature_f": 64.4}
[3] FINAL   Tokyo's teaching record: 18.0°C / 64.4°F, cloudy; not live weather.
model_turns=3, tool_executions=2
```

Add `--show-transcript` to see the user message, two requests, two receipts, and the final answer. These are application-observed events, not the model's inner monologue. In particular, the first turn obtains the record; the next turn turns that returned value into an argument. That dependency is the important part of the rehearsal.

Lin now asks a reasonable question: “If I don't request Fahrenheit this time, will it calculate it anyway?”

## 7. A shorter task should finish earlier

Try weather without conversion, a greeting, and then a different city using the same runtime:

```bash
python stages/01-react-runtime/code/runtime.py --task weather --language en
python stages/01-react-runtime/code/runtime.py --task greet --language en
python stages/01-react-runtime/code/runtime.py --city Paris --language en
```

Weather alone takes a lookup turn and an answer turn. A greeting finishes on the first turn without executing a tool. The last command still requests conversion, but for Paris; it should produce `12.0°C / 53.6°F`, not change the city label while continuing to report Tokyo's temperature.

| Rehearsed task | Decision turns | Tool executions |
| --- | ---: | ---: |
| Greeting | 1 | 0 |
| Weather only | 2 | 1 |
| Weather and conversion | 3 | 2 |

The decisions produced by the stand-in change. `AgentRuntime.run()` does not switch between three separate loops. A live model uses the same interface. Python describes it with a `Protocol`:

```python
class Model(Protocol):
    def generate(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn: ...
```

Read this first as “the object must offer this `generate` method.” The ellipsis is an interface declaration, not an unfinished exercise. Both the adapter and the test double implement the method, so the controller can call either. Type annotations help developers reason about interfaces; they do not validate incoming network data. The runtime checks still matter.

Flexibility alone is not enough, though. If the assistant keeps saying “one more lookup,” Lin might never receive an answer. We need a clear point at which continuing is no longer allowed.

## 8. Where should an unfinished task stop, and what should remain?

The most intuitive limit is the number of model decisions. Deliberately give our three-turn task only two turns:

```bash
python stages/01-react-runtime/code/runtime.py --max-steps 2 --show-transcript --language en
```

The weather lookup succeeds and the conversion produces 64.4°F, but then `MaxStepsExceeded` ends the program with exit code 1. The calculation did not fail. There is simply no allowance for a third model request, so there is no final answer. The runtime neither labels the last tool output as a model answer nor quietly adds another turn to improve the demonstration.

Both successful observations remain in the exception's `messages`, and `--show-transcript` displays them. Stopping means performing no more work, not reversing time. Queries and calculations that happened still happened. A tool that writes files would not have its writes undone merely because a later step raised an exception.

Model turns and tool executions are also distinct counts. A single turn might request two tools. A turn limit cannot independently express “execute at most one tool in this run,” so the example also has a `max_tool_calls` budget:

```python
if tool_executions + len(turn.tool_calls) > self.max_tool_calls:
    raise ToolBudgetExceeded("This batch would exceed the tool-call budget.")
```

With `runtime.py --max-tool-calls 1`, the lookup happens, but the next turn's conversion request is rejected. The execution counter increases immediately before entering a handler, so a handler that raises still counts as an attempted execution. An argument-validation failure does not. If an entire batch would exceed the remaining budget, none of that batch starts; the runtime does not arbitrarily perform its first half.

These limits count operations, not seconds. A stuck Python function will not be interrupted after three seconds because `max_steps=3`. Nor does three model requests imply a fixed bill. This implementation bounds decision and handler counts, not total duration, total cost, or the effects of arbitrary code.

Limits handle work that goes on too long. Next we need to distinguish that from work that was never a valid request in the first place.

## 9. A bad request is different from a broken tool

Suppose the model requests `move_the_moon`. No such tool is registered, so `UnknownToolError` should occur before any handler runs. Now suppose it requests the weather tool with `city="Atlantis"`. The name is valid but the arguments are not, producing `ToolArgumentsError`. Neither is the same as a handler failing while accessing a real data source.

For a batch of requests, the runtime prepares all names and arguments first:

```python
prepared = [self.registry.prepare(call) for call in turn.tool_calls]
```

Execution starts only after this line completes. A valid first request followed by an obviously invalid second request therefore causes no handler execution. This is not transactionality, however. If both requests validate, the first handler succeeds, and the second fails during execution, the first result remains. A third handler will not start. There is no automatic rollback or retry.

`ToolExecutionError` identifies handler failure and retains the underlying exception as its cause for controlled debugging. Its ordinary printed message does not include arbitrary text from that exception. An incomplete provider response or failed model request is reported by the adapter as `ProviderResponseError`. Distinguishing these locations is more useful than diagnosing every failure as “the model got confused.”

Repeated call IDs create another subtle problem. This runtime requires a new ID for each request within a run. Reusing `call-weather` as a new request on a later turn is rejected. Conversely, identical arguments with a new ID may execute again and consume more budget. ID uniqueness avoids ambiguous correlation; it does not identify duplicate business operations or provide idempotency.

Several requests in one turn also do not imply concurrency. A normal `for` loop executes them sequentially, and the model gets another decision only after their results have been recorded. More importantly, **all arguments in that batch were generated before any result from the batch returned**. Putting lookup and a dependent conversion in the same batch will not make the runtime insert the newly discovered 18 into the second request. There is no variable-reference or argument-substitution mechanism here. A dependent request should be proposed after the needed observation arrives.

Finally, remember the distinction from Stage 00: a valid shape can still describe the wrong action. A numeric `99.0` is a valid conversion argument but need not match the record just retrieved. A wrong final answer may satisfy the `ModelTurn` contract too. This general-purpose runtime does not prove every argument's provenance or every sentence's truth. It checks execution boundaries; judging task correctness also requires looking at the request and observed path.

We now know what the controller accepts, rejects, and retains. Let us replace the stand-in with DeepSeek and let the model choose the next action from the actual request.

## 10. Replace the model without replacing the loop

Stage 00 called the DeepSeek Responses API directly. We continue using it, now behind [`DeepSeekResponsesModel`](code/deepseek_runtime.py), which offers `generate(messages, tools)`. A layer translating one interface into another is an **Adapter**. Think of a translator: it communicates a request but does not perform the weather lookup on the speaker's behalf.

Each turn converts the internal transcript into provider input, then converts the provider reply into a `ModelTurn`. The request is assembled as follows:

```python
request = {
    "model": self.model,
    "instructions": self.instructions,
    "input": self._to_deepseek_input(messages),
    "tools": [self._to_deepseek_tool(tool) for tool in tools],
    "tool_choice": "auto",
    "max_output_tokens": 4096,
}
```

Unlike Stage 00's forced single round trip, `tool_choice="auto"` permits an answer or tool requests. Application instructions ask the model to obtain the teaching record, use its observed Celsius reading for a requested conversion, and avoid tools for a greeting. Instructions guide the choice; they are not a programmatic guarantee that the model always chooses correctly. Every returned request still crosses runtime validation.

The response must have status `completed`. Partial calls from an incomplete response do not execute. Function arguments are decoded from JSON text before a `ToolCall` is created. Duplicate JSON fields, non-object arguments, and malformed call identifiers are rejected rather than handed to an execution boundary with an ambiguous interpretation.

If the response contains both explanatory text and tool requests, the adapter treats it as a turn with pending actions, not a final answer. Only a response without calls and with non-empty text becomes `final_text`. That is how the simple internal either-or contract handles richer external output.

### 10.1 Carry the previous work into the next request

DeepSeek's current [Responses compatibility guide](https://api-docs.deepseek.com/guides/responses_api/) requires clients to send conversation history for subsequent turns. The adapter does not use `previous_response_id` to retrieve server-held state. As in Stage 00, it reconstructs input from this run's `messages` rather than keeping a shared response identifier across tasks.

Provider replies can contain additional items needed for continuation. The adapter therefore retains the original output items as well as extracting the actionable calls:

```python
provider_items = tuple(item.model_dump(mode="json", exclude_none=True) for item in output)
```

These items travel with the turn that produced them. Alongside the two control fields, `ModelTurn` has a `provider_items` field for this transport data. The runtime carries it without using reasoning text to select actions; the adapter replays it on the next request. A simplified internal contract need not mean discarding provider continuation data. The ordinary transcript display does not print reasoning content.

Tool observations are translated into the receipt format expected by the service:

```python
items.append({
    "type": "function_call_output",
    "call_id": message["tool_call_id"],
    "output": message["content"],
})
```

The second request thus contains the user request, the first model output, and the weather observation. The third adds the conversion request and result. Each request grows from the current run's record rather than sending only “continue.” Since the data belongs to that run, sequential reuse of the adapter for an independent task does not automatically include the preceding task's history.

DeepSeek currently ignores `parallel_tool_calls` and provider-side `max_tool_calls`, so this adapter does not rely on them for execution limits. Our `max_tool_calls` is checked in Python. Identical parameter names do not imply that the same layer enforces them. The provider's [function-call reference](https://api-docs.deepseek.com/api/create-response/) also directs applications to validate generated arguments before invoking a function.

### 10.2 Connect the service and observe the same request

Set credentials and an available model in the current terminal. The model below is an example; it must match what the current service and your account support. Do not place the key in source code:

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="deepseek-v4-flash"
python stages/01-react-runtime/code/deepseek_runtime.py --language en --show-transcript
```

PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-api-key"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"
python stages/01-react-runtime/code/deepseek_runtime.py --language en --show-transcript
```

The client comes from the `openai` package, but `base_url="https://api.deepseek.com"` directs requests to DeepSeek. It uses `timeout=30.0` and `max_retries=0`, so SDK retry behavior does not silently add attempts to one explicit request. That client timeout is not an end-to-end deadline for the whole Agent run.

This entry announces `live DeepSeek: API usage applies`. It requires network access and incurs service usage. Missing configuration or SDK support causes an error rather than a fallback to the offline stand-in. `--city Paris`, `--task weather`, `--task greet`, and `--language zh-CN` change the request sent to the model.

Do not expect a live model to reproduce every word of the scripted answer or necessarily finish in exactly three turns. Inspect which tools actually ran, whether the conversion input came from the lookup, and whether the final numbers agree. Extra queries remain visible and count against the budget. A wrong direct answer does not cause the runtime to invent two reassuring tool calls. If a lookup succeeds but the next model request fails, the error record retains the lookup while correctly reporting that no final answer was obtained.

We can now run the controller and observe how a real model uses it. A few deliberate checks will make sure the behavior is not merely an accident of the default example.

## 11. Turn “it should work this way” into executable checks

The final string containing `64.4` is not enough. We should also inspect whether the second request contains the Celsius reading returned by the first tool. Temporarily changing Tokyo's record to 22.0°C should propagate 22.0 into the calculation and produce 71.6°F. An answer that still says 18.0 would reveal a staged lookup whose result was never really used.

[`runtime_checks.py`](code/runtime_checks.py) includes that experiment, along with Paris, lookup-only and greeting paths, invalid batches, repeated IDs, handler failures, exhausted budgets, and provider adaptation. For Lin's default task, it examines the second request directly:

```python
call = result.messages[3]["tool_calls"][0]
self.assertEqual(call["arguments"], {"temperature_c": 18.0})
self.assertEqual(result.messages[4]["tool_call_id"], call["call_id"])
```

These checks cover value transfer and receipt correlation. They do not score model intelligence. Fake-client tests inspect whether later requests include earlier requests, observations, and continuation items. The optional real-SDK test uses mock HTTP, not the live service.

Run the checks:

```bash
python stages/01-react-runtime/code/runtime_checks.py
```

One deliberate counterexample has a model immediately answer “99 degrees” without using any tools. The runtime returns that non-empty text normally. This test is not an endorsement of guessing. It makes the limit explicit: the controller organizes, rejects, and records actions; it does not automatically verify all final prose.

Try another request from Lin: “Paris, but no conversion.” Predict the decision and tool counts before running it. Then set the tool budget to zero and compare greeting with weather lookup. The greeting should finish; the weather request should stop before handler execution. Explaining why those outcomes differ is more useful than memorizing the class names.

## 12. The assistant can continue—but should it choose every step?

Lin's page now has more than a fixed lookup followed by an answer. The same controller can take another step or finish sooner. Invalid requests do not start handlers; tool errors are not dressed up as success; each new decision can see the results that preceded it. The scripted stand-in and the real model both use this controller.

Then Lin points at a checkbox: “The page already knows whether the user selected ‘show Fahrenheit.’ Why ask the model whether to convert every time?” This does not invalidate the loop we built. It separates two questions: can we let the model choose, and is that particular choice worth delegating?

That is where [Stage 02: Workflows, Routing, and Planning](../02-workflows-routing-planning/README.md) continues.

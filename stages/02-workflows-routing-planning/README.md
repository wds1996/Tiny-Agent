# Stage 02: The Page Already Has a Checkbox. Why Ask the Model Again? — Workflows, Routing, and Planning

> Language: **English** | [简体中文](README.zh-CN.md)

In [Stage 01](../01-react-runtime/README.md), Lin's travel-practice page learned to look up Tokyo's teaching weather, then convert 18°C to 64.4°F. The model proposed each next action after seeing the previous result. The runtime checked the request, executed the function, and returned an observation. Lin now notices something rather practical: “There is already an ‘include Fahrenheit’ checkbox. If the user checks it, convert. Otherwise, don't. What exactly are we asking the model to decide?”

This does not invalidate the loop we built. It separates being able to delegate a decision from having a reason to delegate it. A colleague who speaks five languages does not need to be consulted every time someone presses a clearly labelled elevator button. Sometimes the application already has the answer.

We will keep working on the same page. First, ordinary code handles the checkbox. When Lin adds a text box, a model can interpret what people ask for. When she wants to inspect the work before preparing a two-city brief, we represent a plan explicitly. Then one data source fails, forcing us to decide what to retain and what to change. All temperatures remain fixed local teaching records. Only the final DeepSeek entry point uses a live model service.

## 1. Do not guess what the checkbox already tells you

Select Tokyo and check “include Fahrenheit.” The application now knows which city to read and whether conversion is required. The unknown is the value in the weather record, not the sequence of operations. Reading the record, optionally converting it, and formatting the result is enough.

A `WeatherTask` holds the cities, the unit option, and the output language. `cities=("Tokyo",)` is a one-element tuple; the comma matters. `fahrenheit=True` asks for both units. Using the Pydantic validation introduced earlier, the task accepts only Tokyo and Paris, rejects repeated cities, and does not silently turn the string `"false"` into a checkbox value.

The working part of [`workflow.py`](code/workflow.py) is short:

```python
def run_workflow(task: WeatherTask, service: WeatherService) -> str:
    task = WeatherTask.model_validate(task)
    readings = []
    for city in task.cities:
        reading = service.read(city)
        if task.fahrenheit:
            reading = convert_temperature(reading)
        readings.append(reading)
    return render_brief(task, tuple(readings))
```

`service.read()` retrieves a fixed record. `convert_temperature()` calculates Fahrenheit. `render_brief()` formats the actual results. A reading retains the city, Celsius value, condition, and source; conversion adds a Fahrenheit value without replacing the original record. The `if` is not obsolete technology waiting to be replaced by an Agent. It expresses Lin's requirement exactly.

A process whose main route is defined by the application is a **workflow**. Workflows can contain branches and can call a model for a particular operation, such as improving the wording of a summary. The useful distinction is not simply whether an LLM appears. It is whether the application already defines the route, or whether the model must choose actions as information arrives. [Anthropic's discussion of workflows and agents](https://www.anthropic.com/engineering/building-effective-agents) similarly starts with the simplest structure that meets the need.

With Python 3.10 or later, install the chapter dependencies from the repository root and run the fixed path:

```bash
python -m pip install -r stages/02-workflows-routing-planning/code/requirements.txt
python stages/02-workflows-routing-planning/code/workflow.py --fahrenheit --language en
```

The output includes `Tokyo: 18.0°C / 64.4°F` and `model calls: 0`. Remove `--fahrenheit` and the program skips conversion, rather than converting and merely hiding the result. `--cities Paris` selects Paris. `--cities Tokyo Paris` reads and compares both cities. None of these form choices requires language understanding.

That settles the checkbox. Now Lin adds a text box: some users would rather type “Read Tokyo's teaching weather and include Fahrenheit” than find the controls. This is where interpretation actually enters the task.

## 2. A text box creates a destination question

The same page may receive “Show Tokyo's teaching weather,” “Compare Tokyo and Paris,” or “What does this page do?” It may also receive “Is it cold there right now?” The last question has no identified city and may request live weather, which this application does not provide.

We do not need to start by inventing a universal assistant. The page already has a few capabilities. We need to identify the right one, or ask for clarification rather than enthusiastically answering a question nobody asked. Choosing among known destinations is **routing**. A Router proposes the destination; the application still enters the appropriate function.

We give the program four destination labels:

| Destination | What the page does next |
| --- | --- |
| `weather` | Read one identified teaching city, optionally converting its temperature |
| `compare` | Read and compare both cities, optionally including Fahrenheit |
| `help` | Explain the page's capabilities without reading weather |
| `clarify` | Ask the user to complete or adjust the request, without reading weather |

Clarification is not an emergency exception handler. It is a valid outcome when the request is incomplete or asks for capabilities we do not offer. Conversely, a malformed model response must not be disguised as “the user was unclear.” Those are different failures with different causes.

As with the Tool Calls in Stage 01, a sentence that sounds like a decision is not a reliable control interface. We need structured fields. The central fields in [`routing.py`](code/routing.py) are:

```python
class RouteDecision(Contract):
    route: Literal["weather", "compare", "help", "clarify"]
    cities: tuple[City, ...] = Field(default=(), max_length=2)
    fahrenheit: bool = False
    reason: str = Field(min_length=1, max_length=300)
```

`Literal` restricts the destinations. `cities` contains the city names extracted from the request. `fahrenheit` describes the unit requirement. `reason` explains the classification; it is not another executable instruction channel. A comparison needs two distinct cities, a weather query needs one, and help or clarification should not smuggle in a lookup.

`Contract` is the shared Pydantic configuration for these small data structures: reject extra fields, validate types strictly, and revalidate instances at the receiving boundary. Each structure adds its own checks for relationships between fields. Think of the common configuration as checking the form's columns, and the relationship check as asking whether a two-city comparison actually names two cities. The [Pydantic model documentation](https://docs.pydantic.dev/latest/concepts/models/) explains both field validation and instance revalidation.

The text box now has an interface. But adding it must not force the old, unambiguous form through a model call as well.

## 3. Use the form when available; interpret only the free text

We keep two distinct inputs. The form path receives a validated `WeatherTask`. The text path receives the user's message. A request must choose exactly one. Supplying both “Tokyo” in the form and “Paris” in the message would leave an unnecessary precedence problem, so the interface rejects that combination. Invalid form data also fails directly; it is not automatically sent to a model to repair.

Combining a deterministic path with a semantic path is often called a **hybrid router**. Here the name describes a very ordinary rule: reliable structured fields select the path directly; free text goes to the semantic router. The form branch is:

```python
if form is not None:
    form = WeatherTask.model_validate(form)
    decision = RouteDecision(
        route="weather" if len(form.cities) == 1 else "compare",
        cities=form.cities, fahrenheit=form.fahrenheit,
        reason="Validated form fields already identify the workflow.",
    )
    return RoutingResult(decision, "form")
```

`RoutingResult` also records where the decision came from, which makes unnecessary model calls visible. This branch does not interpret language or treat a user-written prefix as permission. Form fields are still user input and still require validation; they are simply easier to interpret than a sentence.

The text branch calls `semantic_router.decide(request)`. After receiving the result, the application checks its structure and one concrete relationship to the original message: the decision cannot introduce a city the message never mentioned.

```python
def validate_for_request(decision: RouteDecision, request: str) -> RouteDecision:
    decision = RouteDecision.model_validate(decision)
    if not set(decision.cities).issubset(mentioned_cities(request)):
        raise ValueError("the router invented a city absent from the request")
    return decision
```

`mentioned_cities()` recognizes Tokyo, Paris, and their Chinese names 东京 and 巴黎. It is not a general geographic entity recognizer. It catches “the user mentioned only Tokyo, but the model selected Paris.” It cannot catch every misunderstanding: if the user asks for a poem about Tokyo and the model chooses the weather route, the city check can still pass. Schema compliance does not establish that intent was interpreted correctly.

The `reason` field cannot override the route either. If `route` says `help` while the reason says “perform a weather lookup,” the application enters help. It follows the agreed control fields, not every sentence on the form that resembles a command.

So far, we have selected a destination. No data has been read. Let us deliver this decision to a handler that actually does the work.

## 4. A handler should do more than acknowledge receipt

If Lin clicks the button and only sees “weather handler received your request,” she still has no temperature to put on the page. Receipt is not completion. Our weather destination calls the fixed workflow from the first section. The comparison destination calls the same workflow with two cities. Help and clarification return their messages without touching the weather service.

The weather branch of `dispatch()` is:

```python
decision = RouteDecision.model_validate(result.decision)
if decision.route in {"weather", "compare"}:
    return run_workflow(task_from_decision(decision, language), service)
```

`task_from_decision()` converts the route fields into a `WeatherTask`; the application supplies the output language. We now have a useful division of labor: the model interprets the sentence, then ordinary code carries out the resulting request. We have not given the Router access to arbitrary functions, and routing is not a substitute for identity-based authorization in a real system.

Run the offline comparison:

```bash
python stages/02-workflows-routing-planning/code/routing.py --language en
python stages/02-workflows-routing-planning/code/routing.py --example clarify --language en
```

Each command first demonstrates the form path with `semantic calls: 0`, then a message path. The default message compares both cities: Tokyo produces 18.0°C / 64.4°F, Paris produces 12.0°C / 53.6°F, and Tokyo is warmer by 6.0°C. The clarification example asks “Is it cold there right now?” No weather read occurs; its `source calls` list is empty.

`ScriptedSemanticRouter` is explicitly a test double. It looks up exact sentences in `EXAMPLES` and returns fixed decisions. Unknown wording raises an error. This verifies dispatch and data flow, not language understanding. Later, DeepSeek will interpret genuinely new text.

We have now connected a sentence to a fixed workflow. Does a multi-step task automatically require a Planner? No. Our workflow already reads, converts, and compares two cities. A Router can perfectly well select a multi-step workflow. Planning needs a different motivation.

## 5. Lin wants to inspect the proposed work first

Lin adds a “show the plan first” demonstration mode. Before the page executes, she wants to see which cities it will read and which conversions it will perform. When a task changes, the work should be inspectable instead of being hidden across several model exchanges.

We separate arranging work from performing it. First obtain a list of operations, check whether it can complete the current request, then execute it. Producing those steps and their dependencies is **planning**. The Planner proposes the arrangement. The Executor performs allowed operations under application control.

Start without any classes. To produce a two-city Fahrenheit brief, read Tokyo, read Paris, convert each record, and finally compare and format them. Neither read depends on the other, so they can exchange positions. A conversion, however, needs its own city's reading first. We cannot put a temperature we hope to discover later into the calculator now.

```text
weather_tokyo      read Tokyo
weather_paris      read Paris
fahrenheit_tokyo   convert the result of weather_tokyo
fahrenheit_paris   convert the result of weather_paris
brief              use both converted readings
```

The labels on the left identify steps; they are not temperature values. The descriptions on the right state work and input sources. For this small task, ordinary code can generate the list too. `ScriptedPlanner` does exactly that. Asking a live model to generate it lets us study a model-proposed plan boundary; it does not establish that this fixed weather problem needs an LLM to be solved well.

Compared with Stage 01's turn-by-turn choices, plan-and-execute makes a segment of work inspectable before acting. The tradeoff is that the plan depends on assumptions, such as a source remaining available. We will break that assumption shortly. First, the list needs a representation software can read and reject.

## 6. A plan contains references, not invented results

“First read weather, then calculate” is understandable to a person but underspecified for an Executor. Which reading goes into which calculation? Every step therefore needs an identity, an allowed operation, and a description of where its inputs originate. These are the `PlanStep` fields:

```python
class PlanStep(Contract):
    step_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    operation: Literal["read_weather", "convert_temperature", "write_brief"]
    inputs: tuple[str, ...] = Field(default=(), max_length=2)
    city: City | None = None
    source: Source | None = None
```

`step_id` is a simple identifier within the proposal. `operation` selects one of three implemented operations. `inputs` names results produced by earlier steps. A read has empty inputs and takes a city and a source. A conversion takes one result reference. The final brief references one usable reading for each requested city.

The example has `primary` and `backup` access paths to the same fixed `teaching-v1` material. Think of them as two counters from which the application can obtain the same record, not two dates or two live forecasts. The ordinary proposal uses primary. The application, not the model's preference, decides when backup becomes eligible.

This conversion step says “use the Tokyo reading,” without guessing that the result will be 18:

```python
PlanStep(
    step_id="fahrenheit_tokyo",
    operation="convert_temperature",
    inputs=("weather_tokyo",),
)
```

The actual number is read after `weather_tokyo` executes. Change the record to 22°C and the plan can remain identical while the result becomes 71.6°F. The plan describes dependencies; execution supplies data. Neither role needs to pretend that a forecast number is already known.

A `Plan` also has a short `goal` and no more than five steps. The goal is explanatory text, not a replacement for the request. Writing “read just one city” in it cannot cancel the second city in the application-owned `WeatherTask`. That original task is what validation checks against.

## 7. Check the entire list before starting its first operation

Lin asks whether Pydantic has not already validated the plan. It has checked fields, types, finite choices, and the shape allowed for each operation. Whether this particular plan satisfies this particular task is an additional question.

A simple bad proposal converts a record before reading it. Both steps may look individually valid, but the first has no input. We build a `known` table representing results already completed or produced earlier in the proposed list. At each step, all references must already be in that table:

```python
if step.step_id in known:
    raise PlanRejected("a new step cannot overwrite a completed result")
if not set(step.inputs).issubset(known):
    raise PlanRejected("an input refers to a missing or future result")
```

This is an inspection of the entire plan, not a weather lookup. The validator simulates which result types will become available; it does not generate temperature values. Requiring references to point backward rejects self-dependencies and cycles as well as missing results. An ordering that puts producers before consumers is often called a topological ordering. We do not need a graph framework to check this short ordered list.

Existence alone is insufficient. `known` also records the city and whether a result includes Fahrenheit. That allows the validator to reject repeated conversion, unrelated cities, and the wrong final units. The final-product check is:

```python
products = [known[key] for key in step.inputs]
expected = {(city, task.fahrenheit) for city in task.cities}
if len(products) != len(expected) or set(products) != expected:
    raise PlanRejected("the brief omits a city or has the wrong units")
```

For a two-city Fahrenheit request, the expected set contains two corresponding converted results. Two Tokyo readings are not a substitute for Tokyo and Paris. A Celsius-only record is not a converted record. `write_brief` must also be the final step; ending after a lookup does not finish the requested product.

[`validate_plan()`](code/planning.py) checks these relationships before the Executor performs any operation. If the first four steps look fine but the final step omits Paris, even the first read does not run. A model may choose different valid orders for independent operations, but it cannot change the required inputs and deliverables.

A dependency-correct plan can still encounter a service failure. Validation establishes the declared structural and task constraints, not a promise that every external system will cooperate. We now need execution records to distinguish what was proposed from what actually happened.

## 8. Store each result under its ID, then pass it forward

The Executor no longer asks the model what “the first step” means. It selects an implemented branch using `operation`. After a read or conversion, it stores the result under `step_id`. The Planner cannot populate this result table or add `temperature_c=99` to a conversion instruction.

The two data-processing branches in [`PlanExecutor`](code/planning.py) are:

```python
if step.operation == "read_weather":
    return self.service.read(step.city, step.source)
if step.operation == "convert_temperature":
    return convert_temperature(results[step.inputs[0]])
```

The first reads a record; the second consumes a recorded result. A `Reading` carries city, Celsius value, condition, source, and snapshot version. Conversion returns a new reading with Fahrenheit included. `write_brief` resolves its references and calls the same `render_brief()` used by the fixed workflow, so both execution arrangements use the same calculations.

The final prose here is deliberately produced by a fixed formatter. We can inspect whether values flowed through the dependencies without confusing planning correctness with a model's final wording. The formatter checks the requested cities, units, and matching snapshot versions. Those checks still do not establish the truth of a real external data source.

Run the failure-free path:

```bash
python stages/02-workflows-routing-planning/code/planning.py --failure none --language en
```

The program generates and validates a five-step proposal, then executes all five steps. The terminal prints the saved plans and execution records after the run finishes; there is no interactive approval screen. Application validation before execution is not human approval. The result matches the form workflow: Tokyo is 18.0°C / 64.4°F, Paris is 12.0°C / 53.6°F, with a 6.0°C difference. Execution is sequential. The reads are independent, meaning either valid ordering works; that does not mean Python has started them concurrently.

Keep the proposed list and the execution record separate. Five steps on a plan do not prove five steps occurred. We will now make the second lookup fail and see whether the program still claims to have produced a complete comparison.

## 9. Tokyo is available, but the Paris counter is closed

The default failure demonstration makes `primary/Paris` unavailable while Tokyo remains readable. This failure position matters: one operation has already succeeded. It forces us to consider retained progress, not just how to restart something that never began.

```bash
python stages/02-workflows-routing-planning/code/planning.py --language en
```

The first proposal stops at the Paris read. At that point the result table contains only `weather_tokyo`. The operation record contains both a successful attempt and a failed attempt. Conversion and formatting remain on the proposal but have not executed. A step saying “read Paris” is not a Paris result.

The application records the recognized failure as a small object:

```python
@dataclass(frozen=True)
class Failure:
    step_id: str
    city: str
    source: str
    code: str = "source_unavailable"
```

It identifies the step, the affected city, and the unavailable access path. It comes from the Executor catching `SourceUnavailable`, not from the model speculating that a source might be broken. Invalid arguments, program errors, and rejected plans are not automatically reasons to switch sources.

Both access paths in the fixture expose the **same teaching snapshot**, so retaining Tokyo and reading Paris through backup preserves the data convention. A real fallback requires checking freshness, units, coverage, and access rules. The label “backup” alone promises none of those. We are not contacting two weather companies or demonstrating production disaster recovery.

The situation has now changed: Tokyo is available, the Paris primary path failed, and the remaining work is Paris plus both conversions and the brief. A new proposal should receive those facts, not a vague instruction to try harder.

## 10. Revise the remaining work without erasing completed work

Changing the remaining arrangement after an observation is **replanning**. The new proposal must still serve the same request. It is not permission to forget the original goal or rewrite recorded facts.

The controller passes the task, completed results, and failures to the Planner:

```python
plan = planner.make_plan(task, completed=dict(run.completed), failures=tuple(run.failures))
plan = validate_plan(plan, task, run.completed, tuple(run.failures))
run.plans.append(plan)
```

The Planner receives a copy of the result mapping; its `Reading` values are immutable records. It can reference `weather_tokyo` but cannot change the application's saved 18.0 into another value through this interface. This protects against accidental shared-data modification in normal code. It is not a security sandbox for hostile Python running in the same process.

A valid remaining-work proposal is:

```text
weather_paris      read Paris through backup
fahrenheit_tokyo   use the completed weather_tokyo
fahrenheit_paris   use the newly completed weather_paris
brief              use both converted readings
```

Tokyo is not read again. A completed result ID cannot be overwritten, and assigning a new ID to another read of the same completed city is rejected too. The failed `weather_paris` has no successful result, so the next proposal may reuse that step label. It is not the invocation ID from Stage 01: execution events also record the plan number, which distinguishes these attempts.

The application rejects sources already observed unavailable. Backup is allowed only after the corresponding city's primary path actually failed. The model cannot choose it merely because the word sounds reassuring. An invalid new plan ends this run; the controller does not keep asking for formatting repairs indefinitely.

This also separates two commonly conflated behaviors. Repeating `primary/Paris` is a **retry**. Choosing `backup/Paris` and finishing the outstanding work is replanning in this example. If a single fallback rule is all the product needs, ordinary exception handling can implement it without a model. The Planner makes the proposed arrangement inspectable; it is not the only way to switch data sources.

We retain only read-only results in the current process. Plans that send emails or charge money cannot blindly replay their operations. A process exit also loses this in-memory progress. Continuing after a simulated read failure does not establish general durable recovery.

We can now change the plan. The next question is unavoidable: how often may it change, and how much work may the entire request perform?

## 11. A new plan does not come with a fresh budget

The first proposal attempted two operations: Tokyo succeeded and Paris failed. The replacement executes four: backup read, two conversions, and formatting. The total is **six attempted operations**, not four. Failure consumed an attempt too; it does not disappear because we would rather count only successful work.

Three limits express three different constraints. A plan contains no more than five steps. `max_replans=1` allows one replacement after the initial proposal. `max_execution_steps=8` limits attempts across the entire run, including failed reads, conversions, and formatting. They are not interchangeable interpretations of an ambiguous “eight iterations.”

Before each operation, the Executor checks the shared counter:

```python
if run.execution_steps >= max_execution_steps:
    raise ExecutionBudgetExceeded("the whole run's execution budget is exhausted")
run.execution_steps += 1
```

The controller creates `run` once for the request, not once per plan. Think of a single work order: changing the arrangement does not refund the effort already spent. The counter measures operations, not elapsed time or currency, so those guarantees should not be inferred from it.

Try a limit of three:

```bash
python stages/02-workflows-routing-planning/code/planning.py --max-steps 3 --language en
```

Tokyo primary, failed Paris primary, and Paris backup consume the three attempts. Both raw records remain available, but neither has been converted. The program cannot claim to have delivered the requested Fahrenheit brief. It returns `failed`, leaves `answer` empty, and exits with code 1. That is the budget working, not a reason to label a partial result as success.

`--max-replans 0` ends on the first source failure. `--failure both` makes the Paris backup fail too. Neither prints a successful comparison. When the execution allowance is already exhausted, the controller does not even ask for another proposal it cannot execute.

An operation counter cannot interrupt a Python function that is stuck. It checks before starting the next operation; it is not a timeout or cancellation mechanism. These local functions are quick enough to study control flow. Live model requests need their own attempt limits and failure handling.

## 12. Let real DeepSeek interpret the message and propose the plan

The fixed workflow, route boundary, and Executor now work independently of a live service. Replace two test doubles: a real model call turns free text into `RouteDecision`, and another proposes a `Plan`. They may use the same DeepSeek model, but they are different tasks with different contracts, not one giant prompt entrusted with the entire application.

[`deepseek_decisions.py`](code/deepseek_decisions.py) uses the Responses interface from the earlier chapters. The common structured request is:

```python
response = self.client.responses.parse(
    model=self.model, instructions=instructions, input=input_text,
    text_format=schema, max_output_tokens=4096,
)
```

For routing, `schema` is `RouteDecision`; for planning it is `Plan`. The application supplies separate instructions and does not register weather tools on these requests. DeepSeek produces candidate data. The Executor performs reads later. The [DeepSeek Responses reference](https://api-docs.deepseek.com/api/create-response/) describes JSON Schema output; the SDK's `parse()` additionally attempts to construct the corresponding Pydantic value.

“No network exception” is not sufficient. The Adapter requires completion, the correct parsed type, and no unexpected tool request, then revalidates the object. The controller separately checks the task, completed work, and source policy. Python relationship validators do not execute inside the model service merely because a schema was sent there. A well-formed JSON plan can still be rejected locally; that does not constitute a tool failure that authorizes replanning.

The live Planner receives more than the word “continue.” It builds its input from current execution facts:

```python
context = {
    "task": task.model_dump(mode="json"),
    "completed": {key: asdict(value) for key, value in completed.items()},
    "failures": [asdict(failure) for failure in failures],
}
```

`asdict()` converts data classes to ordinary dictionaries before JSON encoding. Every planning request is self-contained; the needed context is supplied explicitly rather than recovered from a server-side conversation. [DeepSeek's compatibility guide](https://api-docs.deepseek.com/guides/responses_api/) documents the stateless interface. We print validated decisions, not model reasoning as an execution protocol.

Routing and planning share a `StructuredClient` request counter. The default limit is three attempts: one route, one initial proposal, and at most one replacement. The count increases before sending, so failed requests consume it too. The SDK has `max_retries=0`, avoiding hidden automatic retries. Its `timeout=30.0` is a client request setting, not a strict thirty-second deadline for the entire task.

Configure the key and a model accessible to your account in the current terminal. The model below is the official example value; available models and account access must still match the service. Do not put the key in source code:

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="deepseek-flash"
python stages/02-workflows-routing-planning/code/deepseek_decisions.py --mode route --language en
```

In PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-api-key"
$env:DEEPSEEK_MODEL="deepseek-flash"
python stages/02-workflows-routing-planning/code/deepseek_decisions.py --mode route --language en
```

`--mode route` uses the model only to interpret the request, then runs the fixed workflow. Missing configuration or SDK produces an error, not an offline substitute. Override the example with `--question "Read Paris's teaching record in Celsius only."` and inspect whether the model actually identifies one city with no conversion.

Now select plan mode and inject a primary-source failure:

```bash
python stages/02-workflows-routing-planning/code/deepseek_decisions.py --mode plan --failure primary --show-decisions --language en
```

`--show-decisions` displays route and plan data that passed structural validation. That does not imply every decision passed the application checks; inspect the final run status as well. A live model may order independent reads differently from the scripted proposal. If it submits an invalid plan, the program reports failure rather than replacing it with a prewritten success.

For plan mode, the route becomes an explicit task before execution begins:

```python
task = task_from_decision(routing.decision, args.language)
blocked = (("primary", task.cities[-1]),) if args.failure == "primary" else ()
service = WeatherService(unavailable=blocked)
run = run_with_replanning(task, planner=DeepSeekPlanner(model), executor=PlanExecutor(service))
```

The second line injects a demonstration failure. It is not an instruction for the model to declare a service unavailable. Help and clarification never enter this branch. We do not fabricate a weather plan merely to exercise a component. The complete path now has distinct responsibilities: interpretation, route validation, optional planning, execution, and a result built from observed data.

## 13. Check why it succeeded, not only whether it printed an answer

Lin wants the page to satisfy the request. Change Tokyo's fixture to 22.0°C and compare the workflow and the plan implementation: both should produce 71.6°F and a 10.0°C difference from Paris. An assertion that merely searches for `64.4` could reward a program that never used its lookup result at all.

Next, make the final step reference unconverted readings while the task still requests Fahrenheit. The entire plan should be rejected before any lookup. Finally, set the execution allowance to three and verify that successful reads remain recorded while the final answer remains absent. Those experiments separately test data flow, plan acceptance, and stopping behavior. None asks the code to make errors vanish politely.

Run the checks:

```bash
python stages/02-workflows-routing-planning/code/checks.py
```

They also cover the bilingual routing fixtures, form bypass, clarification without reads, forward references, repeated IDs, wrong cities, source eligibility, shared budgets, and equal city temperatures. Fake clients inspect the live Adapter's task, completed results, and failures. The optional SDK check uses mock HTTP, never a live paid request. These checks measure program contracts and control behavior, not DeepSeek's real intent accuracy.

One deliberate counterexample shows a city-valid decision that can still misunderstand a poem request. Knowing what a validator cannot establish matters as much as knowing what it rejects. Live interpretation needs separate observation across greetings, ambiguous references, missing cities, Celsius-only requests, and comparisons. Passing scripted tests does not settle those semantic questions.

Looking back, the page did not climb from a “low-level workflow” to a “high-level Agent.” We explored different divisions of labor. Let code follow explicit form fields. Let a model interpret the uncertain part of a sentence. Represent a proposal as data when pre-execution inspection is useful. Use the Stage 01 loop when each next action genuinely needs to depend on new observations. These arrangements can coexist; the problem determines the choice, not the prestige of its name.

A new difficulty is now visible. One request has a route decision, completed readings, unavailable sources, a current plan, remaining budget, and a final brief. Add drafting and review, and these values become harder to track through local variables. When Lin asks where a run stopped and why it will go somewhere next, we need a clearer representation of its current situation.

That is where [Stage 03: Put the State on the Table](../03-stateful-orchestration/README.md) continues.

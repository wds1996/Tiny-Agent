# Stage 02: Stop Letting the Model Decide Everything — Workflows, Routing, and Planning

> Language: **English** | [简体中文](README.zh-CN.md)

Stage 01 gave us a working Agent Runtime. The model can inspect the current transcript, ask for a Tool, receive an Observation, and decide what to do next. Once that works, a very tempting idea appears:

> If the model can choose the next step, why not let it choose every next step?

Because “can decide” and “should decide” are different engineering questions.

Imagine hiring an extremely capable new teammate and, on day one, giving them authority over support triage, production deploys, expense approval, database access, and the lunch order. Intelligence is useful. Unnecessary authority is still unnecessary authority.

This chapter is about control. Stage 01 taught us how to run a loop in which the model may choose an action. Stage 02 asks a more important design question: **which decisions actually need model judgment, and which decisions should remain ordinary deterministic software?**

That question leads naturally to three patterns: Workflow, Routing, and Planning. They are not three unrelated buzzwords. They are three different answers to one question:

> **How much of the control flow should the model own?**

---

## 1. An Agent is not “a program with fewer if-statements”

Start with a task whose sequence is already known:

```python
weather = get_weather("Tokyo")
fahrenheit = celsius_to_fahrenheit(weather["temperature_c"])
return format_answer(weather, fahrenheit)
```

There is nothing wrong with this. In fact, it is excellent software when the required sequence really is fixed.

You could insert a model between every line:

```text
“What should I do now?”
“Read the weather.”
“What should I do now?”
“Convert the temperature.”
“What should I do now?”
“Format the answer.”
```

But the model has added no useful judgment. We replaced a clear three-step program with a slower and less predictable narrator.

This fixed control structure is a **Workflow**. The defining property is not whether a model appears somewhere inside it. A Workflow may call an LLM to summarize a report, classify a record, or draft some text. It is still a Workflow if the application has already decided when that call happens and what happens afterward.

A useful test is:

> **Who decides the next step?**

If the application already knows the answer, use normal code. If the next step depends on semantic interpretation or an observation that cannot be captured well with stable rules, then model judgment may earn its place.

---

## 2. Deterministic rules are not “less intelligent” when the signal is already clear

Suppose incoming requests can go to one of three handlers: weather, account, or general support.

If the request explicitly begins with `weather:`, no model is needed:

```python
def rule_route(request: str) -> Route | None:
    normalized = request.strip().lower()

    if normalized.startswith("weather:"):
        return Route.WEATHER
    if normalized.startswith("account:"):
        return Route.ACCOUNT

    return None
```

That decision is cheap, predictable, and easy to test.

The interesting case is natural language:

> I was charged twice this month and I’m not sure who handles that.

You can keep adding keyword rules:

```python
if "invoice" in text or "charged" in text or "refund" in text:
    ...
```

At first, this works nicely. Then users write “double payment,” “money taken again,” “incorrect debit,” and twenty other phrasings. Eventually the routing code becomes a home-grown language model made entirely of `or`.

That is where model-based **Routing** becomes useful. The application already knows the valid destinations. The uncertain part is semantic: which destination best matches this request?

---

## 3. A Router chooses a branch; it does not execute the branch

Let the legal routes be explicit:

```python
class Route(str, Enum):
    WEATHER = "weather"
    ACCOUNT = "account"
    GENERAL = "general"
```

The model’s job is deliberately small: choose one of these values.

We represent that choice as structured application data:

```python
class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Route
    reason: str = Field(min_length=1)
```

The model may return something equivalent to:

```json
{
  "route": "account",
  "reason": "The request describes a duplicate charge."
}
```

The application then performs ordinary dispatch:

```python
handler = HANDLERS[routing.route]
return handler(request)
```

Notice what has *not* happened. The model did not gain permission to call arbitrary Python functions. It produced a decision object from a constrained set, and the application mapped that object to an allowed handler.

This is the same boundary we established in Stage 00, just one level higher.

In Tool Calling:

```text
model proposes Tool name + arguments
application validates and executes
```

In Routing:

```text
model proposes Route
application validates and dispatches
```

The model performs semantic judgment. The application still owns control flow.

---

## 4. A practical Router usually combines rules and model judgment

Now suppose the request is:

```text
weather: Tokyo
```

Would you send this to a model just to ask whether it looks weather-related?

You could. You could also call a meeting to decide whether water is wet.

The useful pattern is **deterministic first, semantic fallback second**:

```python
class HybridRouter:
    def __init__(self, semantic_router: SemanticRouter) -> None:
        self.semantic_router = semantic_router

    def route(self, request: str) -> RoutingResult:
        deterministic = rule_route(request)
        if deterministic is not None:
            return RoutingResult(
                route=deterministic,
                source="rule",
                reason="The request contains an explicit route prefix.",
            )

        decision = self.semantic_router.decide(request)
        return RoutingResult(
            route=decision.route,
            source="semantic",
            reason=decision.reason,
        )
```

The principle is simple: **use the cheapest trustworthy signal first**. Bring in model judgment only when the deterministic information is insufficient.

Run the offline example:

```bash
python stages/02-workflows-routing-planning/code/routing.py
```

The example includes an explicitly tagged weather request, a natural-language billing request, and a general writing request. `ScriptedSemanticRouter` is intentionally deterministic; it exists so that we can test routing mechanics without mixing in model variability.

This is the same testing trick from Stage 01: when you are testing the controller, do not make the controller take an exam while a random-number generator sits next to it whispering answers.

---

## 5. Why should a Router return an enum instead of prose?

Suppose you ask:

> Which team should handle this?

and the model answers:

```text
I think the billing support team should probably take this one.
```

A human understands it immediately. A program now has to recover the intended branch from prose. Does it search for `"billing"`? What if the next answer says `"account support"`?

We are back to the exact problem Structured Output solved in Stage 00.

A finite Route enum keeps the decision inside the application’s vocabulary:

```python
class Route(str, Enum):
    WEATHER = "weather"
    ACCOUNT = "account"
    GENERAL = "general"
```

The model may choose a door. It may not draw a new door on the wall and expect the building to contain a room behind it.

This is a useful design rule:

> **Use the model for semantic ambiguity; keep executable choices finite and application-owned.**

---

## 6. Routing answers “which path?” Planning answers “what sequence?”

A Router is ideal when the system has a small set of branches. But consider this task:

> Read Tokyo’s teaching weather, convert Celsius to Fahrenheit, then produce a short briefing.

Choosing the “weather” branch is not enough. The branch itself contains several dependent steps.

We now need **Planning**.

A Planner does not directly perform those steps. It proposes an ordered, inspectable representation of how the goal might be achieved.

Our example allows four operations:

```python
class Operation(str, Enum):
    READ_PRIMARY_WEATHER = "read_primary_weather"
    READ_BACKUP_WEATHER = "read_backup_weather"
    CONVERT_TEMPERATURE = "convert_temperature"
    WRITE_BRIEF = "write_brief"
```

The Planner cannot invent arbitrary executable capabilities. Its planning vocabulary is defined by the application.

That makes a Planner less like “a model writing code” and more like a project coordinator choosing from an approved catalog of actions.

---

## 7. A Plan should be data, not a motivational essay

A model can easily produce:

```text
1. Look up the weather.
2. Convert the temperature.
3. Summarize the result.
```

That is readable, but not yet a strong execution interface. The program needs to know which step produces which data and what later steps depend on.

So we define structured steps:

```python
class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    operation: Operation
    depends_on: list[str] = Field(default_factory=list)
    city: Literal["Tokyo", "Paris"] | None = None
    source_step: str | None = None
    conversion_step: str | None = None
```

A valid plan might look conceptually like this:

```text
weather
    operation = read_primary_weather

convert
    operation = convert_temperature
    source_step = weather

brief
    operation = write_brief
    source_step = weather
    conversion_step = convert
```

The step IDs and references make dependencies explicit. `convert` cannot consume the weather result before `weather` exists. `brief` cannot use the Fahrenheit result before `convert` has completed.

A plan is no longer merely “what the model intends.” It becomes application data with rules.

---

## 8. Validate the Plan before execution

A model-generated plan is still generated output. It can be structurally wrong.

For example:

```text
convert depends on weather
weather appears later
```

That is the software equivalent of a meeting invitation saying, “Please prepare your work based on the decision we will make tomorrow.”

The `Plan` model therefore checks more than JSON syntax:

```python
class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    steps: list[PlanStep] = Field(min_length=1, max_length=5)
```

Additional validation rejects duplicate step IDs, forward dependencies, and references to results that do not exist yet.

This should feel familiar by now.

Stage 00 validated Structured Output and Tool arguments. Stage 01 validated ToolCall and ModelTurn boundaries. Stage 02 validates Plan data before an Executor acts on it.

The recurring principle is:

> **Generated output becomes trustworthy enough for the next layer only after the next layer has checked what it actually requires.**

Reliable Agent systems do not depend on the model never making mistakes. They make mistakes easier to contain.

---

## 9. Keep the Planner separate from the Executor

Once the Plan is valid, something still has to do the work.

That is the Executor:

```python
class PlanExecutor:
    def execute(self, plan: Plan) -> str:
        results: dict[str, Any] = {}

        for index, step in enumerate(plan.steps, start=1):
            if index > self.max_execution_steps:
                raise RuntimeError("execution step budget exhausted")

            results[step.step_id] = self._execute_step(step, results)

        ...
```

The split is important:

```text
Planner:
    “I propose weather → convert → brief.”

Executor:
    “I validate the plan, execute allowed operations, record results,
     and enforce execution limits.”
```

If Planner and Executor collapse into one opaque component, several questions become hard to answer:

Did the plan pass validation?
Which operation actually ran?
How many times did it run?
Could the model invent a new operation?
Who stops a fifty-step plan?
What happens after one step fails?

Those are control questions, and the application needs explicit answers.

---

## 10. A Plan is also a data-dependency graph in miniature

The example stores step results by ID:

```python
results: dict[str, Any] = {}
```

After each step:

```python
results[step.step_id] = self._execute_step(step, results)
```

Later steps read earlier results by reference:

```python
weather = results[step.source_step]
temperature_c = float(weather["temperature_c"])
```

This makes the dependency chain visible:

```text
weather produces data
        ↓
convert consumes weather
        ↓
brief consumes weather + convert
```

Thinking of a plan as “a list of sentences” misses half the point. It is a sequence of operations *plus* dependencies among their outputs.

For this chapter, a dictionary is enough to hold the intermediate results. Once control flow becomes more branched and state transitions become harder to see, we will need a more explicit representation. That is the problem Stage 03 begins with.

---

## 11. A valid Plan can still fail in the real world

Structural validation tells us the plan is executable in principle. It does not guarantee every external operation will succeed.

The example deliberately makes the primary teaching weather source unavailable.

The initial plan is:

```text
read_primary_weather
        ↓
convert_temperature
        ↓
write_brief
```

Execution fails on the first step.

At this point, two extreme strategies are both unsatisfying.

One is to give up immediately even though a backup source exists. The other is to tell the model to “keep thinking” forever until it finds something. The first wastes available alternatives; the second turns failure into an unbounded loop.

The middle ground is **bounded replanning**.

We replan only after receiving a concrete execution failure, and the application limits how many replans are allowed:

```python
for attempt in range(max_replans + 1):
    plan = planner.make_plan(task, failure=failure)

    try:
        return executor.execute(plan)
    except StepFailure as exc:
        failure = exc
        if attempt == max_replans:
            raise
```

The deterministic Planner responds to the observed primary-source failure by producing a new plan using the backup source.

Run:

```bash
python stages/02-workflows-routing-planning/code/planning.py
```

You will see the first plan fail and the second succeed with:

```text
Tokyo: 18.0°C / 64.4°F, cloudy.
```

The important idea is not “the model reflected on its mistake.” The useful engineering statement is much simpler:

> **A new observation changed the next plan, and the application bounded how often that could happen.**

---

## 12. Replanning is not the same as Retry

These words are often used loosely, but the control semantics differ.

A Retry repeats the same action:

```text
primary lookup
fails
primary lookup again
```

Replanning changes the intended path:

```text
primary lookup
fails
new plan chooses backup lookup
```

This chapter implements the second behavior.

The distinction matters because repeating an action can have very different consequences depending on the action. Reading the same data twice is usually very different from charging a credit card twice.

We do not need a full reliability policy here. We only need the concepts to stay separate: **replanning changes the plan; retry repeats an operation.**

---

## 13. Every mechanism that can “continue” needs a boundary

Once a Planner can emit steps and can replan after failure, the system has several ways to keep doing more work.

So we ask a boring but extremely healthy question:

> How much more work is allowed?

The example has three separate limits.

The Plan schema bounds plan length:

```python
steps: list[PlanStep] = Field(min_length=1, max_length=5)
```

The Executor bounds executed steps:

```python
if index > self.max_execution_steps:
    raise RuntimeError("execution step budget exhausted")
```

The controller bounds replans:

```python
for attempt in range(max_replans + 1):
    ...
```

These are intentionally separate because they measure different things: proposed plan size, actual execution work, and recovery attempts.

A single vague `max_iterations` value would hide which resource was actually exhausted.

Budgets are not only about money. They define system behavior. The model may believe another attempt is a wonderful idea; the application still gets the final vote.

---

## 14. Replacing the deterministic models with a real model should not change the controller

So far, `ScriptedSemanticRouter` and `ScriptedPlanner` make the examples reproducible. They are not language models.

The real integration lives in `openai_decisions.py`.

Set:

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-id"
python stages/02-workflows-routing-planning/code/openai_decisions.py
```

The Router requests a structured `RouteDecision`:

```python
response = self.client.responses.parse(
    model=self.model,
    instructions=(
        "Classify the user's request into exactly one route. "
        "weather: weather or forecast questions. "
        "account: invoices, billing, refunds, or account records. "
        "general: everything else."
    ),
    input=request,
    text_format=RouteDecision,
)
```

The Planner requests a structured `Plan`:

```python
response = self.client.responses.parse(
    model=self.model,
    instructions=(
        "Create a short executable plan using only these operations: ..."
    ),
    input=f"Task: {task}\n{failure_text}",
    text_format=Plan,
)
```

Notice what does **not** change: `HybridRouter`, `dispatch`, `PlanExecutor`, plan validation, and the budget logic.

Provider-specific responses are translated quickly into application-owned types. The controller does not have to know the provider’s raw response format.

That is the same Adapter principle from Stage 01, now applied to control decisions rather than Tool Calls.

---

## 15. Workflow, Router, Planner, or Agent Runtime?

The wrong way to choose is by prestige. “Agent Runtime” sounds more advanced than “if/else,” but the software does not award points for using the most dramatic abstraction.

Choose based on where uncertainty actually exists.

| Situation | Usually the better fit |
|---|---|
| Steps and order are stable | Deterministic Workflow |
| There are a few legal branches, but natural language decides which | Router |
| The goal is known, but the work must be decomposed into dependent steps | Planner + Executor |
| The next action genuinely depends on each new Observation | Agent Runtime |

A scheduled report pipeline is often a Workflow.
Support triage is often a Router.
A multi-step research or transformation task may benefit from a Planner.
An open-ended Tool-use loop may need an Agent Runtime.

Real systems can combine these patterns. But learn them separately before combining them. A “universal Agent” often means that several different responsibilities have simply been hidden inside one object.

---

## 16. The deeper lesson: give the model only the control it earns

The most useful habit from this chapter is not memorizing four architecture names.

If a decision can be expressed reliably as normal code, keep it in normal code.

If the uncertain part is semantic classification, ask the model only for the classification.

If the task needs decomposition, ask for a constrained Plan and let an Executor enforce it.

If the next action truly must adapt to each new Observation, then use the Agent Runtime loop from Stage 01.

This is not anti-Agent design. It is good Agent design.

A strong Agent system is rarely the one where the model controls the most. It is the one where the model controls exactly the part that benefits from model judgment.

---

## 17. Run the chapter checks

The deterministic checks require no API key:

```bash
python stages/02-workflows-routing-planning/code/checks.py
```

They verify that explicit routing signals bypass semantic routing, natural-language requests can fall back to semantic decisions, dispatch remains deterministic after the Route is chosen, invalid Plan dependencies are rejected before execution, duplicate step IDs are rejected, disabling replanning causes an observed failure to stop the run, one bounded replan can switch to the backup source, and the application enforces an execution-step budget.

Pay special attention to the failing cases. A happy path proves that the program can succeed once. A boundary test tells you what the program refuses to do.

---

## 18. Exercises

Extend `routing.py` with a `DOCUMENT` route. Give some requests a reliable deterministic marker so they bypass semantic routing, then write a natural-language document request that requires the semantic Router. The interesting question is not whether you can add another enum value; it is where you draw the line between a stable rule and a growing pile of brittle keywords.

Next, extend `planning.py` with a `CHECK_UNIT` operation before conversion. Require the Plan to verify that the weather value is Celsius before `CONVERT_TEMPERATURE` may run. Try to add the operation without rewriting the overall `PlanExecutor.execute()` loop.

Then deliberately create a Plan whose `brief` step references a nonexistent step. Observe where validation rejects it and explain why this should fail before execution.

Finally, run the replanning example with `max_replans` set to `0`, `1`, and `2`. More replanning capacity does not automatically produce a better system. It simply increases the amount of control space the system is allowed to explore.

---

## 19. Where we are now

Stage 01 answered:

> How can the model repeatedly choose an action after each Observation?

Stage 02 adds a more disciplined question:

> Which decisions should the model make at all?

We now have four useful control patterns:

```text
deterministic Workflow
semantic Router
Planner + Executor
Agent Runtime
```

So far, Python functions, local variables, and loops are still enough to represent the execution. As workflows gain more branches, conditions, and intermediate state, it becomes harder to see where the run currently is and why it moved there.

That is the starting point for the next chapter.

➡️ [Stage 03: Explicit State and Stateful Orchestration](../03-stateful-orchestration/README.md)

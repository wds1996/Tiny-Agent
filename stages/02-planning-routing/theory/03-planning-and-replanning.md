# Planning and Replanning: A Plan Is a Bounded Hypothesis, Not Ground Truth

ReAct already contains a form of planning. At each turn the model decides what action is useful next.

Why, then, introduce an explicit Planner?

Because local next-action reasoning and global task decomposition solve different coordination problems.

---

## 1. Local planning in ReAct

A ReAct-style Agent behaves roughly like:

```text
current state
    |
    v
choose next action
    |
    v
observe result
    |
    v
choose next action
```

The model can keep the overall goal in context, but the runtime does not necessarily have an explicit high-level plan object.

Advantages:

- flexible;
- adapts naturally after every observation;
- good for exploration;
- does not need to predict the full path in advance.

Disadvantages:

- may become myopic;
- can repeat work;
- harder to inspect global strategy;
- long-horizon tasks can drift;
- difficult to approve a strategy before execution.

---

## 2. Explicit planning

Planner-executor systems separate a planning phase:

```text
Task
  |
  v
Planner
  |
  v
Plan = [step 1, step 2, step 3]
  |
  v
Execution
```

The plan is application-visible state.

For example:

```python
Plan(
    objective="Investigate checkout outage",
    steps=(
        PlanStep("health", "Inspect checkout service health."),
        PlanStep("changes", "Inspect recent changes that could explain the outage."),
        PlanStep("evidence", "Gather evidence for the most plausible cause."),
        PlanStep("brief", "Produce a concise evidence-based incident brief."),
    ),
)
```

This gives software something concrete to:

- validate;
- display;
- approve;
- budget;
- trace;
- evaluate.

---

## 3. Plan first does not mean plan everything

A common failure is over-decomposition.

Bad:

```text
1. Think about the task.
2. Decide what to inspect.
3. Open the monitoring system.
4. Read the title.
5. Read the first metric.
6. Think about the metric.
7. ...
```

The Planner has specified microscopic executor behavior.

A high-level plan should usually define **meaningful milestones**.

Better:

```text
1. Establish current service health.
2. Identify recent changes correlated with the failure window.
3. Gather evidence for/against likely causes.
4. Produce the incident brief.
```

The Executor decides how to achieve each milestone.

---

## 4. Plan granularity is an architectural knob

Too coarse:

```text
1. Solve the entire problem.
```

The Planner adds no value.

Too fine:

```text
1. Call tool A.
2. Copy field X.
3. Call tool B with X.
4. ...
```

The Planner becomes a brittle program generator and may overfit to imagined future observations.

A useful step is usually:

- independently meaningful;
- easy to explain;
- small enough for one executor invocation;
- large enough that the executor retains tactical flexibility;
- associated with a clear result.

---

## 5. A plan should be structured data

Free-form prose:

```text
First maybe inspect logs, then perhaps check deployments and after that summarize.
```

is difficult for application code to validate.

Tiny-Agent represents:

```python
Plan(
    objective="...",
    steps=(
        PlanStep(id="logs", description="Inspect relevant logs."),
        PlanStep(id="deploys", description="Inspect recent deployments."),
    ),
)
```

Provider-side Structured Outputs can constrain the model to the corresponding JSON shape.

The plan then becomes a control-plane object rather than prompt prose.

---

## 6. Validate before executing

A Planner is still a model. Its output should pass application checks.

Tiny-Agent validates:

- non-empty objective;
- at least one step;
- maximum number of plan steps;
- unique step IDs;
- non-empty descriptions.

Production systems may add:

- allowed action types;
- dependency validation;
- required approvals;
- policy constraints;
- estimated budget;
- tool permission checks;
- impossible or contradictory step detection.

The principle is:

> **A model proposing a plan is not the same as the application authorizing the plan.**

---

## 7. Planning is prediction under uncertainty

A plan describes future work before all future observations exist.

Therefore a plan can become stale.

Example:

```text
Plan:
1. Read primary logs.
2. Inspect deployment correlated with error.
3. Draft report.
```

Execution:

```text
Step 1 -> primary log service unavailable
```

The original strategy may no longer be executable.

That is when replanning becomes useful.

---

## 8. Replanning is an exception transition

Bad pattern:

```text
plan
execute step 1
replan
execute step 2
replan
execute step 3
replan
...
```

This is often just an expensive way to recreate a ReAct loop while pretending the architecture is plan-based.

Better:

```text
plan
  |
  v
execute existing plan
  |
  +-- observation fits assumptions --> continue
  |
  +-- observation invalidates plan --> replan remaining work
```

Replanning should have a reason.

---

## 9. Good replanning triggers

Examples:

### Required resource unavailable

```text
primary search API unavailable
```

Need a fallback strategy.

### Assumption disproved

Plan assumed:

```text
problem started after deployment X
```

Evidence shows:

```text
failure began before deployment X
```

The causal investigation plan should change.

### New information changes task scope

A search reveals the issue affects multiple services rather than one.

### Step becomes impossible

A required permission is unavailable.

### User changes the goal

This is often a new planning event rather than ordinary failure recovery.

---

## 10. Poor replanning triggers

Do not automatically replan because:

- a step completed successfully;
- the model can imagine a prettier plan;
- the wording of the previous step changed;
- every loop iteration calls a `replan()` function by design.

A plan that remains valid should usually remain stable.

Plan stability improves:

- auditability;
- cost;
- predictability;
- human comprehension.

---

## 11. Replan the remaining work

Suppose:

```text
Step 1 health check -> SUCCESS
Step 2 primary logs -> FAILURE
Step 3 report -> not executed
```

A replanner should normally produce:

```text
1. Obtain equivalent evidence from fallback logs.
2. Draft the report using completed health evidence and new logs.
```

It should not blindly repeat:

```text
1. Health check again.
```

unless the failure makes the previous health result invalid.

Tiny-Agent's replanner prompt explicitly requests **remaining work only**.

---

## 12. Completed results are part of replanning context

The replanner needs to know what already happened.

Conceptually:

```text
Original task
+ completed observations
+ failed step
+ failure reason
        |
        v
Replanner
        |
        v
remaining plan
```

Without completed context, replanning often duplicates work.

---

## 13. Replanning needs budgets

An Agent loop without a step limit can loop forever.

A replanner without a replan limit can do the same at a higher layer:

```text
plan -> fail -> replan -> fail -> replan -> fail -> ...
```

Tiny-Agent Stage 02 uses two different controls:

```text
max_total_steps
max_replans
```

Why both?

### `max_total_steps`

Limits total execution work across original and replacement plans.

### `max_replans`

Limits how often strategy itself can be regenerated.

They control different failure modes.

---

## 14. Plan length itself is a budget

Tiny-Agent also uses:

```text
max_plan_steps
```

If a task that should take 4 milestones produces a 35-step plan, that is already a warning sign.

Long plans create:

- higher execution cost;
- more accumulated failure opportunities;
- stale assumptions farther into the future;
- harder human review.

A planner should return the **smallest useful plan**.

---

## 15. Planning vs task decomposition

These terms overlap but are not identical.

Task decomposition asks:

```text
What subproblems exist?
```

Planning also asks:

```text
In what order?
What depends on what?
What is the objective of each step?
What should change after failure?
```

For simple independent tasks, decomposition may be enough.

For long-horizon interaction, execution order and adaptation matter.

---

## 16. Sequential plans vs DAG plans

Tiny-Agent Stage 02 starts with a sequential plan:

```text
step 1 -> step 2 -> step 3
```

Real systems may have dependencies:

```text
             +-> search source A --+
Task -> plan |                     +-> synthesize
             +-> search source B --+
```

This forms a DAG (directed acyclic graph).

We intentionally postpone full dependency graphs and concurrent scheduling because Stage 03 introduces explicit graph/state orchestration.

The learning order is:

```text
sequential bounded plan
        ↓
understand dependencies
        ↓
state graph / DAG orchestration
```

---

## 17. Planning and human approval

Explicit plans are useful when a human wants to review strategy before high-impact execution.

Example:

```text
Task: migrate production database
        |
        v
Planner proposes migration plan
        |
        v
Human reviews / edits / approves
        |
        v
Executor begins
```

This does not mean plan approval alone makes every step safe. Side effects may still require per-action permission policies.

Human-in-the-loop is developed later, but explicit planning creates a natural approval checkpoint.

---

## 18. Planning does not grant permissions

A model might plan:

```text
1. Delete the old database.
```

That does not mean the runtime should allow deletion.

Separate:

```text
Planner capability
```

from:

```text
Executor authority
```

The Planner can propose. Policy controls authorize.

This mirrors Stage 01:

> Model proposes actions; runtime governs execution.

At the planning layer:

> Planner proposes strategy; workflow governs plan execution.

---

## 19. What should be in a plan step?

Tiny-Agent Stage 02 deliberately uses:

```python
PlanStep(
    id="health",
    description="Inspect current service health.",
)
```

rather than allowing arbitrary executable code.

Why?

Because the step is a **goal for an Executor**, not a trusted program.

Later architectures may include typed action plans, but those require stronger validation and tool-policy coupling.

For beginners, high-level step descriptions make the separation visible.

---

## 20. ReAct vs explicit plan: comparison

| Dimension | ReAct | Planner-Executor |
|---|---|---|
| Next action | decided turn by turn | guided by high-level plan |
| Adaptability | naturally high | needs explicit replan transition |
| Global strategy visibility | lower | higher |
| Human plan review | harder | natural |
| Plan staleness | not explicit | important risk |
| Long-horizon coordination | can drift | easier to structure |
| Number of model calls | depends | planning adds calls |

Neither is universally superior.

A common design is:

```text
Planner
   |
   v
one high-level step
   |
   v
ReAct Agent executes that step
```

This combines global structure with local flexibility.

---

## 21. Planning quality must eventually be evaluated

A plan can look reasonable in prose yet lead to poor execution.

Useful future metrics include:

- task success rate;
- unnecessary step count;
- repeated work;
- plan validity rate;
- replanning frequency;
- total tool calls;
- latency/cost;
- failure recovery success.

Do not evaluate Planner quality only by asking another model whether the plan "looks good."

Stage 08 will formalize evaluation.

---

## 22. Interview-ready answer

A concise answer to:

> Why use Planner-Executor instead of pure ReAct?

is:

> ReAct is strong when the next action must adapt continuously to environment observations, but it can be myopic on long-horizon tasks. Planner-Executor makes the global strategy explicit so it can be validated, budgeted, displayed, or approved, while the Executor retains local flexibility. The plan is not treated as truth; if an observation invalidates it, I use bounded replanning of the remaining work rather than regenerating the plan after every successful step.

---

## 23. Check your understanding

1. What planning already exists implicitly in ReAct?
2. Why can an explicit plan help long-horizon tasks?
3. Why is an over-detailed plan brittle?
4. Why should plan steps be structured data?
5. What validations should happen before execution?
6. What observation should trigger replanning?
7. Why should successful steps normally not trigger replanning?
8. Why are both total-step and replan budgets needed?
9. Why does a Planner proposal not imply permission to execute?
10. When might a Planner + ReAct Executor be preferable to either alone?

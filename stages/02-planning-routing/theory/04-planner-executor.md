# Planner–Executor: Separate Global Strategy from Local Execution

Planner–Executor is one of the most important orchestration patterns for multi-step Agent systems.

The idea is simple:

```text
Planner decides WHAT major work is needed.
Executor decides HOW to complete one assigned step.
Workflow decides WHEN to continue, stop, or replan.
```

This separation prevents a single model call or component from silently owning every layer of control.

---

## 1. Why split Planner and Executor?

Imagine a task:

```text
Investigate why checkout errors increased and prepare an evidence-based incident brief.
```

A pure ReAct Agent can solve it by repeatedly selecting tools. But a long-horizon task may benefit from an explicit strategy such as:

```text
1. Establish current service health.
2. Inspect recent changes near the failure window.
3. Gather evidence for likely causes.
4. Produce an incident brief.
```

Now there are two different reasoning problems.

### Global reasoning

```text
What major milestones are necessary?
What order should they follow?
What work can be omitted?
```

### Local reasoning

```text
For "inspect recent changes", which tool should I call?
Which deployment records are relevant?
Do I need another query?
```

Planner–Executor assigns these problems to different components.

---

## 2. The three-layer architecture

Tiny-Agent Stage 02 uses three roles.

```text
                 +------------------+
Task ----------> |     Planner      |
                 +--------+---------+
                          |
                          v
                        Plan
                          |
                          v
                 +------------------+
                 |     Workflow     |
                 +--------+---------+
                          |
               one step at a time
                          |
                          v
                 +------------------+
                 |     Executor     |
                 +--------+---------+
                          |
                          v
                     Observation
                          |
                          +----> Workflow
```

### Planner

Produces high-level strategy.

### Executor

Completes one step and returns a concrete result or a safe failure.

### Workflow

Owns:

- validation;
- ordering;
- completed-step history;
- total-step budget;
- replan budget;
- failure transition;
- termination.

This third role is easy to overlook. Planner + Executor without a governing workflow often turns into two models calling each other without clear authority.

---

## 3. The Planner should not execute tools

A weak architecture lets the Planner do this:

```text
Planner:
1. search_web(...)
2. query_database(...)
3. write_file(...)
```

Now the Planner is no longer merely planning. It has become an Executor and possibly an Agent.

That may be valid in some advanced systems, but it destroys the pedagogical and architectural separation we are trying to establish.

Tiny-Agent Stage 02 Planner returns:

```python
PlanStep(
    id="changes",
    description="Inspect recent changes that could explain the failure window.",
)
```

It does not return executable Python or arbitrary shell commands.

---

## 4. The Executor should not own global strategy

The opposite failure is an Executor that silently rewrites the whole task.

Suppose it is assigned:

```text
Inspect recent deployments.
```

It should not decide:

```text
Actually, let's abandon the incident investigation and build a new monitoring dashboard.
```

Its scope is one step.

This gives the Executor a useful local contract:

```text
Input:
- original task
- current PlanStep
- completed StepResults

Output:
- concrete result
or
- safe failure
```

---

## 5. The Executor can itself be a ReAct Agent

This is where Stage 01 becomes reusable.

A step such as:

```text
Gather relevant evidence from available diagnostic tools.
```

may not have a known exact action sequence.

A ReAct Agent is a good local Executor:

```text
Planner
   |
   v
PlanStep
   |
   v
AgentRuntime
   |
   +-> diagnostic tool
   +-> log search
   +-> deployment lookup
   +-> observation
   +-> another tool if needed
   |
   v
Step result
```

This produces a hierarchical architecture:

```text
global strategy      -> Planner
local adaptive work  -> Agent Executor
hard budgets         -> Workflow
```

This is more controlled than one giant Agent with every responsibility.

---

## 6. The Executor can also be deterministic code

Not every PlanStep needs another Agent.

Example:

```text
Step: Calculate summary statistics from validated records.
```

Executor implementation:

```python
def run_statistics(records):
    return deterministic_statistics(records)
```

A Planner–Executor system can mix:

```text
PlanStep A -> deterministic function
PlanStep B -> external API
PlanStep C -> ReAct Agent
PlanStep D -> human approval
```

The common interface is more important than making every node an LLM.

---

## 7. A useful Executor interface

Tiny-Agent defines conceptually:

```python
class StepRunner(Protocol):
    def run(
        self,
        *,
        task: str,
        step: PlanStep,
        completed: tuple[StepResult, ...],
    ) -> str:
        ...
```

Why pass `completed`?

Because a later step may depend on earlier evidence.

Example:

```text
Step 1 output:
"Service health shows 18% checkout errors since 09:10."

Step 2:
"Inspect changes related to the observed failure window."
```

The Executor needs enough previous context to connect the steps.

---

## 8. But do not blindly pass all history forever

Stage 02 passes all completed results because the examples are small.

In long-running production systems, this can cause:

- context growth;
- irrelevant information;
- sensitive-data propagation;
- higher token cost.

Later stages will introduce state selection, memory, summarization, and persistence.

The important principle is:

> Executor context should be intentional application state, not an accidental dump of everything that ever happened.

---

## 9. Step success needs a real contract

A dangerous pattern is:

```text
Executor returns some prose
Workflow assumes success
```

What if the prose says:

```text
"I could not access the logs."
```

but the function still returns normally?

Then the workflow may incorrectly advance.

Tiny-Agent Stage 02 starts with an explicit Python boundary:

```text
return string       -> success
raise StepFailure   -> expected safe failure
raise other error   -> unexpected failure, sanitized
```

Later, richer executors may return typed objects such as:

```python
ExecutorResult(
    status="success",
    evidence=[...],
    output="...",
)
```

The key idea is that success should be machine-readable, not inferred from the tone of a paragraph.

---

## 10. Safe execution failures

Stage 01 taught that raw exceptions should not automatically be copied into model context.

Stage 02 applies that lesson immediately.

Tiny-Agent introduces:

```python
class StepFailure(RuntimeError):
    """Expected failure whose message is safe for replanning."""
```

An Executor can intentionally report:

```python
raise StepFailure(
    "Primary log source is unavailable; a fallback evidence source is required."
)
```

This message may be useful to the Replanner.

But an unexpected exception such as:

```text
RuntimeError("secret-internal-path=/srv/private/data")
```

is reduced in workflow state to:

```text
RuntimeError
```

The full diagnostic belongs in logs/traces, not the model prompt.

---

## 11. Planner–Executor without Replanning

The simplest architecture is:

```text
plan once
   |
   v
step 1
   |
   v
step 2
   |
   v
step 3
   |
   v
finish
```

If a step fails:

```text
stop and report failure
```

This may be enough for many applications.

Do not add a Replanner until failure recovery benefits from semantic strategy changes.

---

## 12. Planner–Executor with bounded Replanning

When a failure invalidates the remaining plan:

```text
initial plan
    |
    v
step A -> success
    |
    v
step B -> failure
    |
    v
Replanner
    |
    v
remaining plan C', D'
    |
    v
continue
```

The Workflow owns the transition.

The failed Executor does not invoke the Replanner directly.

Why?

Because the Workflow should enforce:

```text
max_replans
max_total_steps
```

before authorizing another strategy generation.

---

## 13. Why the Workflow must own budgets

If the Planner controls its own budget, it can simply decide it needs more steps.

If the Executor controls its own budget, it can continue local work indefinitely.

If the Replanner controls its own retry count, it can keep regenerating plans.

Budgets are governance controls and belong outside the model-directed component.

```text
Model component proposes
Workflow enforces
```

This repeats the core Tiny-Agent philosophy at a higher level.

---

## 14. Planner output is not authorization

Suppose the Planner proposes:

```text
Step: Delete stale production records.
```

The Plan can be syntactically valid but operationally forbidden.

Future production validation should check:

- policy;
- permissions;
- side-effect level;
- human-approval requirements;
- allowed tools;
- cost limits.

The model-generated Plan is an input to governance, not a bypass around it.

---

## 15. Planner–Executor vs Router

A Router chooses one branch:

```text
request -> route -> handler
```

A Planner creates a task-specific sequence:

```text
request -> [step A, step B, step C]
```

Use Routing when the downstream paths already exist.

Use Planning when the major milestones themselves depend on the user task.

Sometimes both are useful:

```text
Request
   |
   v
Router
   |
   +-> simple FAQ workflow
   |
   +-> research branch
           |
           v
        Planner
           |
           v
        Executor
```

This prevents simple requests from paying the complexity cost of planning.

---

## 16. Planner–Executor vs one giant ReAct Agent

### Giant ReAct Agent

```text
one model loop
all tools
all decisions
```

Pros:

- simple conceptual runtime;
- maximum local flexibility.

Cons:

- large action space;
- weak global visibility;
- harder plan approval;
- harder to constrain long-horizon behavior.

### Planner + scoped Executor

```text
Planner -> bounded steps -> scoped Executor
```

Pros:

- explicit high-level strategy;
- smaller local scope;
- easier budgets and audit;
- can expose different tools per step/branch.

Cons:

- extra model calls;
- planner can create bad/stale plans;
- requires state coordination.

Choose based on task requirements and evaluation, not architectural fashion.

---

## 17. Example: research system

User asks:

```text
Compare three approaches for reducing hallucination in retrieval-augmented generation.
```

Planner might produce:

```text
1. Define the comparison dimensions.
2. Gather evidence for approach A/B/C.
3. Compare evidence against the same dimensions.
4. Produce a sourced synthesis.
```

Each step can be delegated to an Executor Agent with search/retrieval tools.

The Planner should not decide every search query in advance because future queries depend on evidence found during execution.

This is the core benefit of hierarchical planning:

```text
global structure + local adaptability
```

---

## 18. Example: support system where planning is unnecessary

User says:

```text
I was charged twice.
```

If the company already has a fixed duplicate-charge workflow:

```text
identify account -> inspect transactions -> apply policy -> response
```

there is no reason to generate a new high-level Plan.

Use Routing to send the request to that workflow.

Planner–Executor is not automatically superior to Routing.

---

## 19. Testing Planner–Executor

Separate tests by component.

### Planner tests

Check:

- valid structured shape;
- bounded number of steps;
- stable objective;
- no empty or duplicate IDs.

### Workflow tests

Use a fake Planner and fake Executor to verify:

- step order;
- completed context;
- stop behavior;
- replan triggers;
- total-step budget;
- replan budget.

### Executor tests

Test local task completion independently.

This decomposition avoids relying on one expensive end-to-end model test for every control-flow invariant.

Tiny-Agent's `tests/test_workflows.py` demonstrates this approach.

---

## 20. Interview-ready system-design answer

If asked:

> How would you build an Agent for a long multi-step task?

A strong answer is:

> I would first check whether the task can be expressed as a deterministic workflow. If the major milestones vary by request but are still bounded, I would use a Planner–Executor architecture. The Planner emits a schema-constrained high-level Plan; application code validates and budgets it; an Executor, which can itself be a ReAct Agent, handles one step at a time. I would preserve completed observations as explicit state and trigger bounded replanning only when a failure or new observation invalidates the remaining plan. Planner output is a proposal, not execution authorization.

---

## 21. Check your understanding

1. What belongs to the Planner?
2. What belongs to the Executor?
3. What belongs to the Workflow?
4. Why should the Planner not call arbitrary tools in this architecture?
5. Can the Executor be a ReAct Agent?
6. Why does the Executor receive completed results?
7. Why should completed context eventually be filtered rather than grow forever?
8. What is the purpose of `StepFailure`?
9. Why should budgets live outside model-directed components?
10. Why is a valid Plan still not authorization to perform side effects?

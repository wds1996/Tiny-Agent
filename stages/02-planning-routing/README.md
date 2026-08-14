# Stage 02 — Planning, Routing & Deterministic Workflows

Stage 01 built a dynamic ReAct loop. Stage 02 asks a more important engineering question:

> **Should the model be allowed to decide this part of the control flow at all?**

A common Agent mistake is to turn every branch, sequence, retry, and transformation into an LLM decision. Real systems are usually easier to test, cheaper, and more reliable when predictable work remains ordinary software and the model is used only where semantic judgment or dynamic decomposition is actually useful.

This stage therefore introduces the major orchestration patterns between a basic ReAct loop and the stateful graph orchestration taught in Stage 03.

## Prerequisites

Complete:

- [`../00-foundations/`](../00-foundations/)
- [`../01-react-runtime/`](../01-react-runtime/)

You should already understand:

- structured output;
- function/tool calling;
- the ReAct action-observation loop;
- model-provider adapters;
- the difference between model decisions and runtime execution.

## Learning objectives

After this stage, you should be able to:

1. distinguish a single LLM call, workflow, router, planner-executor system, and autonomous Agent;
2. explain why Agent autonomy is a cost/reliability trade-off rather than an automatic upgrade;
3. decide which control-flow decisions should remain deterministic code;
4. implement deterministic routing before reaching for an LLM router;
5. implement schema-constrained semantic routing when rules are insufficient;
6. keep routing decisions separate from deterministic dispatch;
7. explain local/implicit planning in ReAct vs explicit high-level planning;
8. represent a plan as application data rather than free-form prose;
9. separate Planner, Executor, and Workflow responsibilities;
10. validate and bound plans before execution;
11. replan only when observations invalidate the current plan;
12. distinguish replanning from repeatedly regenerating a plan after every successful step;
13. apply total-step and replan budgets;
14. explain why model-reported confidence should not be treated as calibrated probability;
15. recognize cases where a Workflow is a better engineering choice than an Agent.

## The complexity ladder

Tiny-Agent uses this mental model:

```text
Single deterministic function
          |
          v
Single LLM call
          |
          v
Prompt / processing chain
          |
          v
Deterministic workflow
          |
          v
Routing workflow
          |
          v
Planner -> Executor workflow
          |
          v
Bounded replanning
          |
          v
Open-ended autonomous Agent
```

Moving downward adds flexibility, but usually also adds:

- model calls;
- latency;
- token cost;
- nondeterminism;
- failure modes;
- testing difficulty;
- observability requirements.

Use the least dynamic architecture that solves the problem well.

## Recommended order

### Part A — Workflow vs Agent

1. [`theory/01-agent-vs-workflow.md`](theory/01-agent-vs-workflow.md)
2. [`code/deterministic_router.py`](code/deterministic_router.py)

### Part B — Routing

3. [`theory/02-routing-patterns.md`](theory/02-routing-patterns.md)
4. [`../../src/tiny_agent/decision.py`](../../src/tiny_agent/decision.py)
5. [`../../src/tiny_agent/models/openai_structured.py`](../../src/tiny_agent/models/openai_structured.py)
6. [`../../src/tiny_agent/workflows.py`](../../src/tiny_agent/workflows.py)
7. [`code/openai_router.py`](code/openai_router.py)

### Part C — Planning and execution

8. [`theory/03-planning-and-replanning.md`](theory/03-planning-and-replanning.md)
9. [`theory/04-planner-executor.md`](theory/04-planner-executor.md)
10. [`code/planner_executor_agent.py`](code/planner_executor_agent.py)
11. [`code/bounded_replanning.py`](code/bounded_replanning.py)

### Part D — Review

12. [`exercises/review-questions.md`](exercises/review-questions.md)
13. Read [`../../tests/test_workflows.py`](../../tests/test_workflows.py)
14. Read [`../../tests/test_structured_decision.py`](../../tests/test_structured_decision.py)

## Pattern 1 — Deterministic workflow

If the path is already known, write the path in code.

```text
Input
  |
  v
validate
  |
  v
transform
  |
  v
save
  |
  v
END
```

Do **not** ask an LLM whether validation should happen before saving if the application already knows the answer.

Good fits:

- document ingestion pipelines;
- fixed approval processes;
- ETL steps;
- schema validation;
- known API sequences;
- deterministic business rules.

## Pattern 2 — Routing

Routing introduces one semantic decision and keeps downstream execution explicit.

```text
                         +--> billing workflow
User request -> Router --+--> technical workflow
                         +--> general workflow
```

Important separation:

```text
Router decides destination
        !=
Router executes arbitrary downstream actions
```

After the route is chosen, normal application code should usually dispatch to the corresponding handler.

### Prefer deterministic routing when possible

```python
if is_refund_request(request):
    route = "billing"
elif contains_known_error_code(request):
    route = "technical"
else:
    route = "general"
```

This is cheap, testable, and predictable.

### Use an LLM router for semantic ambiguity

When categories depend on meaning rather than stable keywords, use a schema-constrained decision:

```json
{
  "route": "technical",
  "reason": "The user describes a product failure after login."
}
```

The model still does **not** receive permission to invent a new destination. The schema constrains `route` to an allowed enum.

## Pattern 3 — Explicit planning

A ReAct Agent often performs local planning implicitly:

```text
observe -> choose next action -> observe -> choose next action
```

Explicit planning separates high-level strategy from step execution:

```text
Task
  |
  v
Planner
  |
  v
Plan
  |
  v
Executor(step 1)
  |
  v
Executor(step 2)
  |
  v
...
```

Tiny-Agent represents the plan as data:

```python
Plan(
    objective="Prepare an incident brief",
    steps=(
        PlanStep("health", "Inspect current service health."),
        PlanStep("deploys", "Inspect recent deployments."),
        PlanStep("brief", "Draft an evidence-based incident brief."),
    ),
)
```

A plan is **not ground truth**. It is a proposed strategy that must be bounded and checked against observations.

## Pattern 4 — Bounded replanning

Do not regenerate a plan after every successful step by default.

Preferred control flow:

```text
plan
  |
  v
execute step
  |
  +-- success --> next existing step
  |
  +-- failure --> is current plan invalid?
                      |
                      +-- no --> handle locally / stop
                      |
                      +-- yes --> bounded replan
```

Replanning should be an explicit recovery transition.

Tiny-Agent Stage 02 therefore has both:

```text
max_total_steps
max_replans
```

A system with unlimited replanning has simply moved the infinite-loop problem to a different layer.

## Planner / Executor responsibility split

```text
Planner
-------
understand global objective
choose high-level milestones
order major work
avoid unnecessary steps

Executor
--------
finish one assigned step
gather observations
use tools when necessary
return concrete result/failure

Workflow
--------
validate plan
enforce budgets
pass completed context
record results
decide when replanning is allowed
stop safely
```

The Executor can be:

- deterministic Python code;
- a tool-specific service;
- a human;
- a ReAct `AgentRuntime`;
- a later LangGraph subgraph.

That composability is why separating the roles matters.

## New provider-neutral control interface

Stage 02 adds:

```text
src/tiny_agent/decision.py
```

with:

```python
class StructuredDecisionModel(Protocol):
    def decide(..., schema: dict) -> dict:
        ...
```

This is intentionally different from the Stage 01 `Model` protocol.

Stage 01 asks:

```text
What should the Agent do next?
-> ToolCall OR final answer
```

Stage 02 control components ask:

```text
Which route?
What is the bounded plan?
What remaining plan is needed after failure?
-> schema-constrained application data
```

## OpenAI structured decision adapter

The current implementation uses the Responses API with JSON-Schema Structured Outputs:

```text
src/tiny_agent/models/openai_structured.py
```

Conceptually:

```text
Routing / Planning component
        |
        v
StructuredDecisionModel
        |
        v
OpenAIStructuredDecisionModel
        |
        v
Responses API + JSON Schema
        |
        v
validated-shape JSON object
```

This reuses a Stage 00 concept — Structured Output — as a Stage 02 orchestration primitive.

## Example architecture: support routing

```text
User message
    |
    v
cheap deterministic rules
    |
    +-- certain match ----------> handler
    |
    +-- ambiguous
          |
          v
       LLM Router
          |
          v
   schema-constrained route
          |
          v
 deterministic dispatch
```

A hybrid router like this is often better than calling an LLM for every request.

## Example architecture: Planner + Agent Executor

```text
                     User task
                        |
                        v
                Structured Planner
                        |
                        v
                     Plan
              +---------+---------+
              |                   |
              v                   v
        executor step 1      executor step 2
        (AgentRuntime)       (AgentRuntime)
              |                   |
              v                   v
         observations         observations
              \                   /
               +--------+---------+
                        |
                        v
                  final step/result
```

The Planner decides *what major work is needed*. The executor Agent decides *how to accomplish one assigned step with its available tools*.

## Decision guide

Use this as a starting heuristic, not a universal law.

| Situation | Prefer |
|---|---|
| Fixed sequence known in advance | deterministic workflow |
| A small number of stable categories | rule router |
| Categories are semantic/ambiguous | LLM router + structured output |
| Task is multi-step but major milestones can be planned | planner-executor |
| Plan can become invalid after observations | bounded replanning |
| Number/order of steps cannot be predicted and environment feedback drives progress | ReAct/autonomous Agent |
| One prompt already solves the task reliably | one model call |

## Common mistakes this stage is designed to prevent

### Mistake 1 — "More Agent = more intelligent"

Extra autonomy is not free. It can reduce reliability when the path is already known.

### Mistake 2 — LLM routing without an allowlist

Do not accept arbitrary model-generated route names and dynamically import/execute them.

### Mistake 3 — Free-form planning prose

A plan should be structured enough for application code to validate and execute.

### Mistake 4 — Treating the plan as truth

Plans are hypotheses about future work. Environment observations can invalidate them.

### Mistake 5 — Replanning after every step

This adds model calls and causes strategy drift. Replan because evidence requires it, not because a loop exists.

### Mistake 6 — No plan budgets

A Planner that can emit 40 steps has already created a cost and reliability problem before execution starts.

### Mistake 7 — Letting Planner and Executor share every responsibility

If the Planner can execute arbitrary tools and the Executor can rewrite global strategy at any moment, the architecture becomes difficult to reason about.

## Stage completion checkpoint

Before moving to Stage 03, you should be able to answer:

1. Why is a Workflow not simply a "less advanced Agent"?
2. When should routing be deterministic?
3. Why should an LLM router return an enum-like structured decision?
4. Why is a route decision different from downstream dispatch?
5. What problem does explicit planning solve that ReAct does not solve as clearly?
6. Why should a plan be validated before execution?
7. What should trigger replanning?
8. Why do `max_total_steps` and `max_replans` both matter?
9. Can an Executor itself be an Agent? Why?
10. Which parts of a planner-executor system should remain ordinary Python control flow?

## References

Primary references used for this stage:

- Anthropic, *Building Effective Agents* — workflows vs agents and common workflow patterns.
- LangGraph documentation, *Workflows and agents* — routing, orchestrator-worker, evaluator-optimizer and graph representations.
- OpenAI API documentation — Responses API Structured Outputs and current GPT-5.6 model guidance.
- Huang et al., *Understanding the Planning of LLM Agents: A Survey* — planning taxonomy and challenges.

The goal is not to copy one framework's terminology exactly. Tiny-Agent uses these references to teach the underlying architectural choices first.

# 03 — Base Implementation: Build the Agent Before the Framework

The base implementation exists for one reason: by the time you look at the LangGraph version, every important control decision should already make sense without a decorator or graph API.

## Main object

```python
agent = BaseOpenScholarAgent(
    model=model,
    corpus=corpus,
    scholarly_search=search,
    memory=memory,
    exporter=exporter,
    config=config,
)
```

The class coordinates existing Tiny-Agent primitives. It does not invent a second tool runtime, second memory system, or second tracer.

## Step 1 — Read long-term personalization

```python
remembered = dict(
    self.memory.read_context(request.user_id)
)
```

If this request includes a temporary preferred style, it overlays the remembered preference for this run.

Important distinction:

```text
remembered preference
!=
research evidence
```

The memory can influence answer style. It cannot become a citation source.

## Step 2 — Structured planning

```python
plan = await asyncio.to_thread(
    self.model.plan,
    question=request.question,
    remembered_context=remembered,
)
```

The model proposes a `ResearchPlan`; application code then bounds it:

```python
subquestions = plan.subquestions[
    :config.max_subquestions
]
```

This preserves the Stage 02 principle:

> Model output proposes control data; the application validates and constrains it.

If a model returns 400 subquestions, the correct response is not “wow, such a thorough researcher.” It is “the budget has entered the chat.”

## Step 3 — Parallel but bounded retrieval

Each subquestion can create two independent retrieval tasks:

```python
local = asyncio.create_task(
    local_search(subquestion)
)

external = asyncio.create_task(
    external_search(subquestion)
)
```

The total number of subquestions has already been bounded. The Crossref client also has its own concurrency guard.

`asyncio.gather()` provides scheduling, not research judgment. It does not decide which source is trustworthy or whether the evidence is enough.

## Step 4 — Evidence normalization

Raw results are deduplicated and assigned stable public IDs:

```text
E1
E2
E3
```

The model sees the same IDs that the evaluator later checks.

## Step 5 — Evidence sufficiency before synthesis

```python
local_count = sum(
    item.kind == "local_fulltext"
    for item in evidence
)
```

If the count is below the configured threshold, the Agent returns:

```text
status = insufficient_evidence
```

and does not call the synthesis model.

This matters financially as well as scientifically: there is no reason to pay for a fluent answer that policy already knows cannot be supported.

## Step 6 — Synthesis without open-ended tools

After retrieval, the writer receives evidence and no tool surface:

```python
model.synthesize(
    question=question,
    evidence=evidence,
    remembered_context=remembered,
)
```

The research phase was Agentic; the synthesis phase is intentionally narrower.

A mature Agent does not maximize autonomy at every line of code. It uses autonomy where it creates value.

## Step 7 — Bounded critic/writer loop

The initial draft goes through the Stage 11 `TeamRuntime`:

```text
Supervisor -> Critic
            -> optional Writer
```

The critic can request revision, but the application owns `max_revisions`.

Without a bound, “reflect until perfect” is just an academically themed infinite loop.

## Step 8 — Explicit memory write

A style is stored only when the request explicitly asks for it:

```python
if request.remember_style:
    memory.write_style(...)
```

The underlying `ConservativeMemoryWritePolicy` remains responsible for the durable boundary.

## Step 9 — Export as a side effect

An `export_path` produces an `ApprovalRequest`. Without a decision, the base version returns:

```text
status = approval_required
```

If the user approves, the path still passes exporter authorization.

```text
human approval
    -> application validation
    -> path containment check
    -> file write
```

Approval is not a magic `sudo` button.

## Step 10 — Trace the run

The base path records nested spans:

```text
openscholar.run
  plan
  retrieve.local
  retrieve.crossref
  synthesize
  review.team
  memory.write
```

Raw prompts/outputs are not captured by default because Stage 10 already taught that observability must not undo Stage 09's privacy boundary.

## What the base version deliberately does not solve

The base implementation can return `approval_required`, but it does not provide durable suspended execution by itself. If the process exits, application code would need to persist the run state and reconstruct where to continue.

That is the precise point where the LangGraph version earns its place.

The lesson is not:

> Python is bad; use a graph.

The lesson is:

> Use ordinary control flow until the state-machine requirements make dedicated orchestration infrastructure valuable.
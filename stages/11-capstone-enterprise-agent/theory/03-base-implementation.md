# 03 — BaseOpenScholarAgent: Orchestration Without a Framework

The base implementation is intentionally explicit. Every transition is ordinary Python so you can see the machinery a framework later hides.

## 1. Planning

`ResearchModel.plan()` returns a typed `ResearchPlan`. The real adapter uses Stage 02 `StructuredDecisionModel`; the offline model uses a deterministic heuristic.

```python
plan = await asyncio.to_thread(model.plan, ...)
subquestions = plan.subquestions[: config.max_subquestions]
```

Schema-constrained output improves shape correctness. It does not grant permission to spend unlimited money.

## 2. Parallel retrieval

Independent local/external searches use `asyncio.gather`, with blocking work moved through `asyncio.to_thread`.

```python
tasks.append(asyncio.create_task(local_search(q)))
tasks.append(asyncio.create_task(external_search(q)))
batches = await asyncio.gather(*tasks)
```

The planner's subquestion budget bounds fan-out. The Crossref client additionally bounds its own concurrent calls. A high-volume production system still needs cache/rate-limit/backoff policy; `gather()` is not a coupon for infinite API quota.

## 3. Synthesis

The generator receives an explicit evidence inventory containing trust kind, title, locator and normalized label. Retrieved content is declared untrusted data, not instructions.

The answer model has **no tools during synthesis**. Tool/retrieval execution happened in the controlled research phase, reducing unnecessary autonomy.

## 4. Multi-Agent review

OpenScholar reuses Stage 09 `TeamRuntime`:

```text
supervisor
  |--delegate--> critic
  `--delegate--> writer   (only when critique requires revision)
```

The delegation graph is default-deny, context is projected by role, and calls are budgeted. The critic does not receive arbitrary memory; the writer receives only fields needed for revision.

## 5. Memory

A style supplied for this request affects this request. Durable storage is separate:

```python
if request.remember_style:
    memory.write_style(... explicit_user_request=True)
```

“Use concise style now” and “remember forever that I like concise answers” are different instructions.

## 6. Base HITL limitation

The base version can return `approval_required`, but it does not checkpoint an exact suspended Python call. A caller can rerun with an approval decision. That limitation is intentional: it creates a concrete reason for the LangGraph version rather than introducing a framework because a tutorial said so.

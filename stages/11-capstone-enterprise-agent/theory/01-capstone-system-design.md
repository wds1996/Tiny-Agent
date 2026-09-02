# 01 — System Design: From Agent Script to Agent Product

A complete Agent is not a large `while True` loop with more imports. It is a set of contracts around uncertain model behavior.

## 1. Start from responsibilities

OpenScholar separates five planes:

```text
Control plane   planning, routing, stop/revision decisions
Data plane      paper chunks, metadata, memories, tool outputs
Execution       retrieval, model calls, export side effects
Policy          trust, budgets, approval, authorization, retention
Operations      tracing, evaluation, API, deadlines, deployment
```

If these collapse into one prompt, the prompt becomes CEO, database administrator, security team, and intern simultaneously. That is an impressive job title and a terrible architecture.

## 2. Model output is still a proposal

The planner may propose four subquestions. Application code still caps their count. The planner may ask for external discovery. Application code still checks whether external search is allowed and configured. A critic may request revision. Application code still owns the revision budget.

```python
plan = model.plan(...)
subquestions = plan.subquestions[: config.max_subquestions]
use_external = request.allow_external_search and plan.use_external_search
```

That line is the course in miniature: **LLM flexibility inside deterministic envelopes**.

## 3. Domain services survive framework replacement

Both implementations share:

- `ResearchRequest` / `ResearchReport`;
- local corpus and evidence types;
- Crossref discovery;
- memory policy;
- export authorization;
- supervisor/critic/writer policy;
- evaluation contract.

Only orchestration changes.

```text
Base version                LangGraph version
------------                -----------------
if / for / gather           nodes / edges
Python variables            graph state
manual pending approval     checkpointer + interrupt
explicit call order         StateGraph topology
```

This is how to compare frameworks scientifically rather than aesthetically.

## 4. A full request

```text
question
  -> memory read
  -> bounded plan
  -> parallel evidence acquisition
  -> normalize + label trust
  -> evidence sufficiency gate
  -> draft
  -> critic
  -> optional writer revision
  -> optional memory write
  -> optional approved export
  -> report/eval/trace
```

There is no requirement that every request use every capability. A mature Agent is capable of *not* doing unnecessary work.

## 5. Failure boundaries

External discovery can fail without corrupting local evidence. Insufficient full text causes abstention. Critic/writer failures are reduced to stable warning types. Export is isolated behind human review and a confined directory. These are architectural decisions, not prompt personality.

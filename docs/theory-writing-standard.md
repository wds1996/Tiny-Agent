# Tiny-Agent Theory Chapter Standard

Tiny-Agent is a learning repository, not an API catalogue. A theory chapter is complete only when a beginner can move from **"I have heard this term"** to **"I can reason about the mechanism and recognize a bad implementation."**

This document is the review standard used across the 2026 curriculum.

## 1. Every chapter should answer seven questions

A strong chapter should make these answers obvious:

1. **What is it?** — precise definition and neighboring concepts.
2. **Why does it exist?** — the failure/problem that motivates the abstraction.
3. **How does it work?** — mechanism, data/control flow, state transitions, or protocol shape.
4. **Who owns the decision?** — model, runtime, application policy, infrastructure, or human.
5. **What can go wrong?** — common misconceptions, failure modes, and security/reliability boundaries.
6. **What does the code look like?** — a minimal core snippet aligned with the real repository implementation.
7. **How do I know it is useful?** — a worked example, comparison, test, or evaluation criterion.

If a chapter only answers the first question, it is a glossary entry wearing a graduation gown.

## 2. Mechanism before framework

Preferred order:

```text
problem
  -> mental model
  -> minimal mechanism
  -> Tiny-Agent implementation
  -> framework/provider mapping
  -> trade-offs and evaluation
```

Framework names change quickly. The mechanism should survive them.

For example:

```text
checkpoint semantics
    before
LangGraph checkpointer API
```

and:

```text
candidate retrieval + reranking
    before
one vendor's hybrid_search() method
```

## 3. Code blocks have three levels

### Conceptual pseudocode

Use when the point is architecture rather than a runnable API. Label it clearly.

```python
# conceptual pseudocode
proposal = model.decide(state)
validated = policy.validate(proposal)
result = executor.run(validated)
```

### Minimal runnable mechanism

Use ordinary Python when a mechanism can be shown without a framework.

### Repository-aligned snippet

When referencing Tiny-Agent classes, use their real names and semantics. Do not invent a prettier API that does not exist in `src/tiny_agent`.

A learner should not discover that the tutorial's `agent.magic_memory()` was a literary device.

## 4. Humor should clarify, not distract

Useful humor creates a memorable failure model:

> A context window is a suitcase, not a challenge to pack every sock you own.

> `BackgroundTasks` is not a durable queue; the process does not become immortal because the function runs after the response.

Avoid jokes that replace explanations. The reader should still be able to remove every joke and retain a technically rigorous chapter.

## 5. Every important abstraction needs a bad example

Good architecture becomes easier to understand when contrasted with a tempting mistake.

```text
Bad:  user-supplied tenant_id -> trusted resource lookup
Good: authenticated identity -> tenant binding -> authorization
```

```text
Bad:  all 100 tools in every model call
Good: capability catalog -> relevant subset -> model context
```

## 6. Separate facts, proposals, and authority

Tiny-Agent repeatedly uses this invariant:

```text
model / retrieved data / memory / skill
           ↓ influences
       model proposal
           ↓ validated by
 deterministic application policy
           ↓
 authorized execution
```

A chapter should not accidentally promote model text, retrieved text, Tool annotations, a Skill file, or a protocol advertisement into execution authority.

## 7. State what the example deliberately does not solve

Educational code should be honest about scope.

Examples:

- SQLite can teach durable leases without pretending to be a distributed workflow engine.
- Docker restrictions can teach a stronger execution boundary without claiming perfect hostile multi-tenant isolation.
- a deterministic hash embedding can teach vector plumbing without claiming semantic quality.

Clear limitations are part of the lesson, not an apology.

## 8. Completion test

Before considering a theory chapter finished, a learner should be able to:

- explain the concept without quoting a framework API;
- draw its data/control flow;
- identify at least one failure mode;
- read the corresponding Tiny-Agent code;
- explain why a simpler architecture might be preferable;
- name a metric/test that would tell whether the added complexity helps.

That is the bar for an A+ Tiny-Agent theory chapter.
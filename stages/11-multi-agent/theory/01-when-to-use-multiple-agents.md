# 01 — When Should You Use Multiple Agents?

Multi-Agent systems are useful, but **multiple Agents are not a maturity badge**.

A system with five Agent names can still be a badly disguised deterministic pipeline.

The first Stage 11 question is therefore not:

> How do I create more Agents?

It is:

> What engineering problem becomes easier because responsibility is split across autonomous Agent boundaries?

---

## 1. Start from the simpler architectures

Tiny-Agent now has several options:

```text
plain function
    -> deterministic workflow
    -> one Agent with Tools
    -> one Agent + RAG/MCP/memory
    -> multi-Agent
```

Move right only when the previous option stops being a good fit.

If the task is:

```text
load CSV
-> validate columns
-> aggregate revenue
-> save report
```

creating:

```text
CSV Agent
Validation Agent
Revenue Agent
Saving Agent
```

is mostly an expensive office meeting.

Use code.

---

## 2. A real reason: different expertise boundaries

A useful split may exist when subtasks require genuinely different instructions, context, tools, or evaluation criteria.

Example:

```text
Research specialist
- external evidence
- citation rules
- web/search tools

Legal reviewer
- policy corpus
- narrow legal instructions
- no external mutation tools

Writer
- style guide
- source summaries only
```

Here the boundaries carry meaning.

---

## 3. A real reason: context isolation

Suppose one giant Agent sees:

```text
customer billing data
research corpus
internal legal notes
production credentials
marketing documents
```

Even if only one subtask needs each piece, everything enters one giant authority/context surface.

A multi-Agent design can deliberately project:

```text
research Agent -> research-safe context
billing Agent  -> billing-safe context
writer         -> approved summaries only
```

The benefit is not "more intelligence."

It is **smaller context and authority domains**.

---

## 4. A real reason: independent parallel work

Some subtasks are naturally independent:

```text
quality analysis ─┐
cost analysis    ─┼─> synthesis
risk analysis    ─┘
```

Parallel specialists can reduce wall-clock latency when:

1. subtasks do not depend on one another;
2. each subtask is expensive enough to justify parallelism;
3. fan-in has a clear aggregation rule.

Do not parallelize steps that actually have a dependency chain.

```text
retrieve evidence
-> read evidence
-> write conclusion
```

Running all three simultaneously is not parallel intelligence. It is chronology denial.

---

## 5. A real reason: ownership transfer

Customer support is a classic example.

A triage Agent may handle general conversation until it recognizes a refund case.

At that point:

```text
triage
  --handoff-->
refund specialist
```

The important feature is not that another LLM ran.

The important feature is:

> **conversation ownership changed.**

This is different from asking a specialist for a bounded subtask while the manager stays responsible.

---

## 6. A real reason: independently deployed Agent systems

Sometimes the other Agent is not even part of your codebase.

It may be:

- built by another team;
- written in another language;
- deployed by another company;
- backed by private Tools and memory you cannot inspect.

That is where Agent interoperability protocols such as A2A become relevant.

A remote Agent can expose a contract without exposing its internals.

---

## 7. Weak reasons to use multi-Agent

These are warning signs:

### "It feels more agentic"

Not an engineering requirement.

### "Every step deserves its own persona"

A persona is not automatically an architectural boundary.

### "The model gets confused, so I will add three more models"

Sometimes the real fix is:

- better Tool descriptions;
- smaller context;
- deterministic routing;
- better state design;
- stronger validation;
- better retrieval.

### "A diagram with many boxes looks impressive"

PowerPoint is not a distributed-systems benchmark.

---

## 8. The same model can still support useful Agents

Separate Agents do **not** require separate foundation models.

Two Agent instances may use the same model but still have useful boundaries if they differ in:

```text
instructions
Tools
context
permissions
memory
output contract
runtime policy
```

The architectural distinction is responsibility, not necessarily model weights.

---

## 9. Conversely, multiple model calls do not imply multi-Agent

A workflow may call the same or different models many times:

```text
classify
-> extract
-> summarize
-> verify
```

If application code fixes the order and each call is just one deterministic stage, it is usually clearer to call this a workflow.

Tiny-Agent does not award an Agent title to every API request.

---

## 10. A decision checklist

Before adding another Agent, ask:

1. **Responsibility:** Does this component own a distinct decision domain?
2. **Context:** Does it need a meaningfully different context window?
3. **Tools:** Does it need a distinct capability set?
4. **Authority:** Should it have different permissions?
5. **Control:** Should it merely answer a manager, or take over the interaction?
6. **Parallelism:** Can its work run independently?
7. **Deployment:** Is it an independently deployed service?
8. **Evaluation:** Can we show measurable benefit over a simpler baseline?

If most answers are no, keep the simpler architecture.

---

## 11. Complexity is not free

A second Agent introduces more than one extra model call.

Possible new costs:

```text
routing errors
context transfer errors
constraint loss
coordination loops
latency
additional tokens
extra retries
more tracing
more permissions
more failure surfaces
```

A team can outperform one Agent while still being a worse product.

---

## 12. Stage 11 architecture principle

The default remains:

> **Use the least dynamic architecture that solves the task well.**

Multi-Agent is justified when specialization, isolation, independent work, ownership transfer, or interoperability creates enough measurable value to pay for its coordination overhead.

# Agent vs Workflow: Choose the Smallest Useful Control System

One of the most important Agent-engineering skills is knowing when **not** to build an autonomous Agent.

Beginners often learn Agent systems in this order:

```text
LLM -> tools -> ReAct -> "let the model decide everything"
```

That progression is useful for understanding autonomy, but it can create the wrong engineering instinct. In production, autonomy is not a prize awarded to a system after it becomes sophisticated. It is a design choice that trades predictability for flexibility.

This chapter builds a more useful mental model.

---

## 1. Start with the control-flow question

For every application step, ask:

> Who should decide what happens next: ordinary software or the model?

There are two broad answers.

### Predefined control flow

Application code knows the allowed path in advance:

```text
request
  |
  v
validate
  |
  v
fetch data
  |
  v
transform
  |
  v
save
```

The model may participate in one or more nodes, but code owns the graph.

This is a **workflow**.

### Model-directed control flow

The model examines the current state and decides what action or tool should happen next:

```text
request
  |
  v
model decision
  |
  +--> tool A
  |
  +--> tool B
  |
  +--> ask user
  |
  +--> finish
```

After observing the result, the model decides again.

This is the central shape of an **Agent**.

The distinction is about **control ownership**, not whether an LLM appears somewhere in the system.

---

## 2. A workflow can contain LLM calls

Consider:

```text
input
  |
  v
LLM: extract facts
  |
  v
Python: validate schema
  |
  v
LLM: write summary
  |
  v
END
```

There are two LLM calls, but the LLM does not choose whether validation happens or which stage comes next.

The path is still defined by code.

Therefore:

```text
multi-step LLM application
```

is not automatically:

```text
autonomous Agent
```

This matters because many companies use the word *Agent* broadly for marketing or product naming. As an engineer, you should still identify the actual control architecture.

---

## 3. An Agent can contain deterministic workflow segments

The reverse is also true.

An Agent might decide:

```text
"I need to ingest this document before answering."
```

but the ingestion operation itself may be a deterministic pipeline:

```text
parse -> normalize -> chunk -> embed -> index
```

The Agent chooses **whether** to invoke the capability. Ordinary software controls **how** that capability executes.

This hybrid design is common and desirable.

```text
Agent decision
      |
      v
Document-ingestion tool
      |
      v
fixed deterministic pipeline
```

Do not replace reliable internal workflows with nested LLM decisions simply because the outer system is agentic.

---

## 4. A useful complexity ladder

Think of architectures as a ladder.

### Level 0 — ordinary deterministic code

```python
result = calculate_price(items)
```

Use when the problem is fully specified by code.

### Level 1 — one LLM call

```text
user -> LLM -> answer
```

Use when a single call reliably completes the task.

Examples:

- classify sentiment;
- summarize a short document;
- extract a known set of fields;
- rewrite text.

### Level 2 — fixed LLM workflow

```text
LLM extract -> validate -> LLM synthesize
```

Use when a fixed decomposition makes each step easier or more verifiable.

### Level 3 — routing workflow

```text
input -> choose branch -> specialized handler
```

Use when several stable downstream processes exist but selecting the right one requires classification.

### Level 4 — planner-executor

```text
high-level task -> plan -> execute bounded steps
```

Use when the task is multi-step and the high-level milestones depend on the request.

### Level 5 — bounded autonomous Agent

```text
decide -> act -> observe -> decide -> ...
```

Use when the number and order of steps cannot be known reliably in advance.

### Level 6 — long-running / multi-Agent systems

These add delegation, persistence, coordination, background work, or multi-session state. They should be introduced only when the simpler structures fail measurable requirements.

---

## 5. Why simpler often wins

Every model-controlled decision introduces uncertainty.

If one decision has probability `p` of being correct, a simplistic intuition for a long sequence of independent correct decisions is:

```text
p^n
```

Real Agent steps are not independent, so this is not a literal reliability formula. But the intuition matters:

> More dynamic decisions create more opportunities for error to compound.

They also create additional:

- model latency;
- token cost;
- tool-call cost;
- prompt surface area;
- debugging difficulty;
- evaluation requirements.

For example, if the application always requires:

```text
validate payment -> create invoice -> store receipt
```

asking an LLM to decide the order each time adds no useful intelligence.

---

## 6. When a workflow is the better choice

Prefer a workflow when most of these are true:

- the sequence of steps is known;
- branches are defined by stable business rules;
- actions have significant side effects;
- correctness is more important than flexibility;
- compliance requires explicit control paths;
- intermediate states must be easy to audit;
- deterministic tests are available;
- the task repeats at high volume;
- latency/cost matters strongly.

Examples:

### Data ingestion

```text
upload
  -> antivirus check
  -> parse
  -> normalize
  -> chunk
  -> index
```

### Order processing

```text
validate cart
  -> reserve stock
  -> charge payment
  -> create shipment
```

### Model-assisted document processing

```text
extract fields with LLM
  -> validate required fields
  -> human review if low quality
  -> save
```

The LLM can help without owning the whole workflow.

---

## 7. When an Agent is justified

Agents become valuable when the correct path depends on observations that cannot be enumerated easily beforehand.

Good signals include:

- open-ended tasks;
- unknown number of steps;
- dynamic tool selection;
- exploration/search;
- repeated environment feedback;
- failure recovery requiring semantic judgment;
- user goals that can be achieved through multiple valid strategies.

Examples:

### Coding task

A request such as:

```text
Fix the failing authentication bug in this repository.
```

may require:

```text
inspect files
run tests
read error
search symbols
edit code
run tests again
inspect new error
...
```

The exact path depends on observations.

### Research task

```text
Compare the latest approaches to a niche technical problem.
```

The Agent may need to search, reject irrelevant results, refine queries, inspect evidence, and stop only when the evidence is sufficient.

---

## 8. The key test: can you draw the path before runtime?

A practical interview question is:

> Can I draw the complete control flow before I receive the user request?

If yes, that is evidence for a workflow.

If only some branches are unknown, use a hybrid architecture:

```text
fixed workflow
    |
    +--> one model router
    |
    +--> one Agent node for open-ended subtask
```

If the whole sequence must emerge from environment interaction, an Agent becomes more appropriate.

---

## 9. Deterministic when possible, agentic when useful

Tiny-Agent uses this design principle throughout the repository:

> **Deterministic when possible, agentic when useful.**

It does **not** mean "avoid LLMs."

It means separate two kinds of problems.

### Software problems

Examples:

- checking whether a value exists;
- validating JSON;
- enforcing a retry limit;
- checking permissions;
- dispatching an enum route;
- writing a record to a database.

Use software.

### Semantic decision problems

Examples:

- deciding which support category best matches an ambiguous description;
- decomposing a novel research task;
- deciding whether gathered evidence is sufficient;
- choosing the next useful search query.

An LLM may add value.

---

## 10. A bad architecture example

Suppose the requirement is:

```text
1. Read a CSV.
2. Validate required columns.
3. Calculate statistics.
4. Generate a natural-language explanation.
```

Bad design:

```text
Agent
  |
  +-> decide whether to read CSV
  +-> decide whether to validate
  +-> decide whether statistics are required
  +-> decide whether to generate answer
```

The first three steps are mandatory and predictable.

Better design:

```text
Python: read CSV
   |
Python: validate
   |
Python: calculate
   |
LLM: explain results
```

If the user may request different types of analysis, add one bounded semantic routing step:

```text
User goal
   |
Router
   +--> statistics workflow
   +--> anomaly workflow
   +--> visualization workflow
```

This is much easier to test.

---

## 11. Another bad architecture: "Agent all the way down"

Suppose an Agent decides to send an email.

The email-sending capability should not itself become:

```text
Email Agent
  -> decide whether SMTP connection is necessary
  -> decide whether address validation is necessary
  -> decide whether message should be encoded
  -> decide whether to send
```

Instead:

```text
Outer Agent decides: send_email(...)
                 |
                 v
           deterministic API client
```

This creates a clean authority boundary.

---

## 12. Workflows improve safety too

Deterministic control flow can restrict what the model is capable of deciding.

For example:

```text
LLM extracts refund reason
      |
      v
Python policy engine checks eligibility
      |
      +-- eligible --> refund workflow
      |
      +-- not eligible --> human review
```

Do not ask the LLM to reinterpret a hard business rule if code can enforce it directly.

This becomes increasingly important when Agent actions affect:

- money;
- accounts;
- files;
- production infrastructure;
- external communications.

---

## 13. Workflows and Agents form a continuum

Do not treat the terms as mutually exclusive product categories.

A realistic system may look like:

```text
                     User
                      |
                      v
                 LLM Router
               /      |      \
              /       |       \
             v        v        v
      fixed FAQ   refund    research
      workflow    workflow     Agent
                     |           |
                     v           v
                 approval    tools/search
                     |           |
                     +-----+-----+
                           |
                           v
                         answer
```

Only one branch needs high autonomy.

That is often better than building one giant Agent with every tool.

---

## 14. Enterprise design questions

Before adding an Agent loop, ask:

1. Can a single model call solve this reliably?
2. Is the path already defined by business rules?
3. Which decisions require semantic judgment?
4. Which decisions can be expressed as ordinary conditions?
5. What happens if the model chooses the wrong branch?
6. Does the model need access to all tools at all times?
7. Can a workflow constrain the action space?
8. How many model turns are acceptable for latency and cost?
9. Can we measure that autonomy improves success rate?
10. Is there a deterministic success criterion?

If you cannot explain why autonomy improves the system, do not add it merely because the architecture looks more "agentic."

---

## 15. Interview-ready answer

A concise answer to:

> What is the difference between an Agent and a Workflow?

is:

> In a workflow, application code defines the control path and the LLM is used inside predefined steps. In an Agent, the model dynamically determines parts of its own action sequence based on the current context and environment observations. I prefer deterministic workflows for predictable tasks and introduce model-directed control only where semantic or open-ended decisions provide measurable value.

That answer is much stronger than:

> An Agent can call tools and a workflow cannot.

because workflows can absolutely contain tools and LLM calls.

---

## 16. Check your understanding

Classify each system.

### A

```text
PDF -> parse -> chunk -> embed -> vector DB
```

**Deterministic workflow.**

### B

```text
Question -> LLM decides whether to search -> search -> LLM decides whether more search is required
```

**Agentic loop.**

### C

```text
Ticket -> LLM chooses billing/technical/general -> specialized fixed handler
```

**Routing workflow.**

### D

```text
Task -> LLM creates 4-step plan -> application executes those steps in order
```

**Planner-executor workflow.**

### E

```text
Agent chooses a database tool -> database tool runs deterministic SQL client code
```

**Agent containing a deterministic capability.**

If these distinctions are clear, you are ready for routing.

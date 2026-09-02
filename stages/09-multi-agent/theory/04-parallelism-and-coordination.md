# 04 — Parallelism, Coordination & Failure Modes

Multi-Agent systems introduce distributed-systems-shaped problems even when every Agent runs inside one Python process.

The moment independent workers can run, fail, disagree, or transfer control, coordination becomes a first-class design problem.

---

## 1. Fan-out / fan-in

A common pattern is:

```text
              -> Agent A -\
manager ------> Agent B ---> aggregate
              -> Agent C -/
```

Use it when subtasks are independent.

Examples:

- quality review;
- cost analysis;
- risk analysis;
- independent retrieval strategies;
- multiple domain reviews.

---

## 2. Concurrency is not free speed

Parallel work can reduce wall-clock latency, but it can also increase:

```text
model calls
API pressure
cost
rate-limit risk
memory pressure
fan-in complexity
```

If three workers each cost $0.02, parallelism may reduce latency while tripling model cost.

Stage 08 metrics should decide whether that trade is acceptable.

---

## 3. `asyncio.gather()` is not a supervisor

This code:

```python
results = await asyncio.gather(a(), b(), c())
```

only solves scheduling/collection.

It does not answer:

- Were the subtasks correct?
- Which outputs are trustworthy?
- How should conflicts be resolved?
- What if one worker fails?
- Should partial results be accepted?
- Who decides the final answer?

Fan-in is an application responsibility.

---

## 4. Prevalidate a parallel batch

Tiny-Agent validates the whole assignment batch before launching any worker.

Why?

Bad sequence:

```text
reserve Agent A budget
validate Agent A -> OK
reserve Agent B budget
validate Agent B -> DENY
launch nobody
```

Now budget was consumed for work that never started.

Better:

```text
validate all edges
validate all Agents
check parallel limit
check total budget
      |
      v
reserve batch
      |
      v
launch
```

This is a small transactional design principle.

---

## 5. Worker failure policies

Suppose three workers run:

```text
quality -> success
cost    -> failure
risk    -> success
```

Possible application policies:

### Fail fast

Reject the whole task.

Useful when every component is mandatory.

### Partial result

Continue with quality + risk and mark cost as unavailable.

Useful when partial value is acceptable.

### Retry specialist

Only if the failure and operation are retry-safe, following Stage 07 rules.

### Fallback specialist

Route to a backup with a compatible contract.

The right choice belongs to the application, not to the adjective "multi-Agent."

---

## 6. Coordination loops

Tool loops from Stage 07 become Agent loops:

```text
A -> B -> A -> B -> A ...
```

or:

```text
supervisor -> researcher
researcher returns "ask supervisor"
supervisor -> researcher
...
```

Protect with:

```text
max Agent calls
max handoffs
repeated edge limits
wall-clock budget
cost/token budget
no-progress detection
```

Tiny-Agent Stage 09 begins with call/handoff/repeated-edge limits.

---

## 7. Deadlock-like behavior

Agents can also wait on one another conceptually:

```text
Agent A: I need B's conclusion.
Agent B: I need A's conclusion.
```

Neither is technically blocked on a mutex, but the task cannot progress.

Avoid cyclic dependencies in the task graph where possible.

For known dependencies, use an explicit DAG/workflow rather than hoping conversational Agents negotiate their way out.

---

## 8. Duplicate work

Two specialists may independently perform the same expensive search.

That may be intentional for diversity.

Or it may be pure waste.

Trace:

```text
research_A -> search(query=X)
research_B -> search(query=X)
```

Stage 08 lets you detect repeated work and decide whether diversity justified the cost.

---

## 9. Conflicting results

Imagine:

```text
Agent A: release is safe
Agent B: release is unsafe
```

Do not solve this by:

```text
majority vote of two Agents
```

You need a resolution policy:

- evidence comparison;
- domain precedence;
- deterministic business rule;
- third-party review;
- human approval.

Two confident language models disagreeing does not create truth by averaging confidence.

---

## 10. Diversity vs correlated failure

Three Agents using:

```text
same model
same prompt template
same evidence
same assumptions
```

may produce three highly correlated errors.

This is not independent verification.

Useful diversity can come from:

- different evidence sources;
- different tools;
- different instructions;
- different model families;
- adversarial review roles;
- deterministic validators.

But diversity also increases complexity.

Measure it.

---

## 11. Aggregation should preserve provenance

Bad fan-in:

```text
"Experts say X."
```

Better:

```text
quality_agent -> finding A
risk_agent    -> finding B
cost_agent    -> finding C
```

Then the manager can preserve source identity in the final artifact or trace.

This makes debugging and evaluation possible.

---

## 12. Ordering semantics

`asyncio.gather()` returns results in input order even when completion order differs.

That is useful for deterministic tests.

But completion order may still matter operationally for:

- streaming;
- cancellation;
- early-stop policies;
- first-success races.

Do not confuse result ordering with execution ordering.

---

## 13. Cancellation

If the user cancels the parent task, what happens to workers?

Production systems need a cancellation policy:

```text
parent cancel
    -> cancel child work where supported
    -> stop new delegation
    -> preserve audit/trace state
    -> clean up resources
```

Stage 09 does not claim full distributed cancellation. That belongs with Stage 10 service deployment and task infrastructure.

---

## 14. Long-running remote Agents

Once a remote Agent takes minutes or hours, a simple function-call mental model breaks down.

You need concepts like:

```text
task ID
status
input-required
auth-required
completed/failed/canceled
artifact delivery
streaming or push updates
```

A2A formalizes these concepts for interoperable Agent systems.

---

## 15. Coordination observability

Useful Stage 09 metrics include:

```text
agent_calls
handoffs
unique_agents
failed_agent_calls
parallel_width
coordination_latency
coordination_cost
handoff_loop_rate
```

Then compare against a simpler baseline.

Multi-Agent optimization without these measurements is mostly architecture astrology.

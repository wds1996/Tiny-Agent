# Stage 11: Need a Second Agent? Prove It — Multi-Agent Systems

> Language: **English** | [简体中文](README.zh-CN.md)

For ten stages we have been improving one Agent: Tool boundaries, workflows, graphs, retrieval, MCP, memory, context, Skills, guardrails, traces, and evaluation.

Only now is it useful to discuss a topic that makes architecture diagrams instantly more exciting: Multi-Agent systems.

The first question is deliberately skeptical:

> **Why is one well-designed Agent not enough?**

If that question has no clear answer, five Agents usually create five debugging surfaces plus coordination overhead.

---

## 1. Multiple model calls are not automatically multiple Agents

A ReAct loop can call the model several times and still be one Agent.

Multi-Agent design introduces relatively independent task owners or roles with distinct responsibilities, context, or capabilities.

A supervisor asking a policy specialist to interpret one rule is a better starting example than merely counting model calls.

---

## 2. Reasons that can justify another Agent

A second Agent may be justified when it has meaningfully different instructions, context, Tools, permissions, data access, or service ownership. Independent subtasks that can be delegated are another reason. A remote system maintained by another team may already be an independent Agent.

“More boxes look advanced” is not a reason.

---

## 3. A small Agent boundary

The teaching interface is:

```python
class Agent(Protocol):
    name: str

    def run(
        self,
        task: str,
        context: Mapping[str, str],
    ) -> str:
        ...
```

Each specialist receives one task and a projected context.

The default question is not “how do we share everything?” It is “what does this specialist actually need?” That directly extends Stage 07.

---

## 4. Delegation keeps ownership with the caller

A supervisor can delegate:

```python
Delegation(
    target="orders",
    task="Check the order status.",
    context_keys=("order_id",),
)
```

The specialist returns a result and the supervisor continues owning the original task.

```text
Supervisor owns task
    ↓ delegates subtask
Specialist works
    ↓ returns
Supervisor continues
```

---

## 5. Handoff transfers ownership

A handoff means the target takes over the task.

The result therefore records:

```python
TeamResult(
    owner="orders",
    ...
)
```

A useful mental shortcut is:

```text
Delegation -> help me with a part
Handoff    -> this is yours now
```

The control difference matters even if a framework exposes both through similar APIs.

---

## 6. Context Projection prevents accidental oversharing

Shared data may contain order data, policy text, user identifiers, and internal secrets. An order specialist may need only the order ID.

The chapter uses an allowlist:

```python
project_context(
    context,
    allowed_keys=("order_id",),
)
```

Projection reduces both context noise and unnecessary data exposure. More Agents make Context Engineering more important, not less.

---

## 7. “Shared memory” needs a data model

If several Agents share memory, ask who owns it, who can read it, who can write it, and whether an Agent's summary is fact or interpretation.

A global mutable dictionary is convenient and quickly becomes a responsibility problem.

Prefer scoped namespaces, explicit ownership, read/write policy, and context projection.

---

## 8. Fan-out and fan-in are task structure

Order status and policy interpretation can be delegated independently:

```text
Order Agent --\
               -> Supervisor -> final
Policy Agent -/
```

The teaching `fan_out()` executes sequentially on purpose.

Fan-out describes independent task structure. Concurrency is an execution strategy. Do not mix those concepts before discussing rate limits, cancellation, and failure aggregation.

---

## 9. Team autonomy needs budgets too

Agents can delegate in cycles just as one Agent can loop.

```python
TeamBudget(
    max_delegations=4,
    max_handoffs=1,
)
```

bounds team behavior.

Handoffs have a separate budget because changing task ownership is a stronger control transition.

---

## 10. Self-delegation is the easiest loop

The teaching runtime rejects `A -> A`.

Longer cycles require global delegation traces or call-stack reasoning.

The general invariant remains: Multi-Agent autonomy must be bounded and observable.

---

## 11. Specialization should be more than personality prompts

Three Agents with different adjectives are not necessarily three meaningful architectural roles.

Strong specialization usually involves differences in task, context, Tools, permissions, data, or service-level requirements. Otherwise one model may simply be wearing three hats.

---

## 12. A Critic is not a free correctness button

Adding a reviewer or critic adds another probabilistic component, cost, latency, and failure mode.

Use Stage 10's evaluation loop to prove that the critic actually improves the target cases.

Architecture should earn its complexity.

---

## 13. Information degrades across handoffs

One Agent produces a result, another summarizes it, and a third makes a decision.

Each boundary may lose facts, provenance, uncertainty, or error type.

Important inter-agent messages benefit from structure:

```text
task
result
status
provenance
structured data
```

The same lesson appears again: important boundaries deserve explicit contracts.

---

## 14. Internal Agents do not bypass authorization

If only a billing specialist may execute refunds, a supervisor delegating to billing does not inherit that capability.

The specialist's execution boundary still applies its own authorization and approval rules.

“Another Agent in our system asked” is not permission.

---

## 15. Multi-Agent and MCP solve different boundaries

MCP connects an Agent or Host to Tools, Resources, and Prompts.

Multi-Agent coordination connects one task-owning Agent to another task-owning Agent.

A remote service exposing a database lookup is a Tool-like capability. A remote system accepting goals, managing task state, and returning artifacts behaves more like an independent Agent.

---

## 16. Independent Agent systems need an interoperability protocol

Inside one Python program we can call `runtime.delegate()` directly.

Across teams, frameworks, or services, independent Agents need a stable protocol boundary.

The current A2A standard targets exactly that class of interoperability: capability discovery, messages, task lifecycle, and artifact exchange across opaque Agent implementations.

This chapter does not turn into an A2A SDK tutorial. The important distinction is:

```text
internal Team Runtime
    -> local coordination abstraction

A2A-style boundary
    -> interoperability between independent Agent systems
```

A protocol still does not decide whether Multi-Agent architecture is justified or trusted.

---

## 17. A2A and MCP are complementary

A useful shortcut is:

```text
MCP -> Agent to Tool / Data
A2A -> Agent to another Agent
```

A remote specialist can itself use MCP internally. Different protocols solve different boundaries.

---

## 18. Run the chapter

```bash
python stages/11-multi-agent/code/demo.py
python stages/11-multi-agent/code/checks.py
```

The checks cover context allowlists, delegation ownership, handoff ownership, self-delegation, delegation/handoff budgets, unknown Agents, and per-specialist context projection.

---

## 19. Why workspace and sandboxing come next

Longer and more capable Agent work often needs files, artifacts, tests, and scripts. Stage 08 Skills may even bundle scripts.

That raises a new question:

> **If the Agent can actually manipulate files and run code, how much of the machine can it touch?**

Stage 12 gives the Agent a workspace without casually handing over the whole computer.

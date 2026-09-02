# 02 — Delegation, Handoffs & Supervisors

"Ask another Agent" hides several different control-flow semantics.

Stage 09 makes them explicit.

---

## 1. Delegation: the manager keeps control

Manager-style delegation looks like:

```text
user
 |
 v
manager
 |  delegate bounded task
 v
specialist
 |  return result
 v
manager
 |
 v
user
```

The specialist behaves like a high-level Tool.

The manager still owns:

- the user conversation;
- final synthesis;
- whether another specialist is needed;
- final answer responsibility.

This pattern is useful when the specialist should provide expertise **without becoming the new conversation owner**.

---

## 2. Handoff: control ownership changes

Handoff looks like:

```text
user
 |
 v
triage
 |
 | handoff
 v
refund specialist
 |
 v
user
```

After the transfer, the target specialist becomes the active Agent.

That is the key semantic difference.

Tiny-Agent therefore models:

```python
await team.delegate(...)
# active_agent unchanged

await team.handoff(...)
# active_agent changes only after successful target invocation
```

If a failed handoff changed active ownership anyway, the runtime would claim that control moved to an Agent that never successfully accepted the work.

---

## 3. Supervisor / worker

A supervisor architecture is a manager pattern with explicit specialist workers:

```text
             -> researcher
            /
supervisor ----> analyst
            \
             -> reviewer
                    |
                    v
              supervisor synthesis
```

The supervisor may decide:

- who should work;
- what each subtask is;
- whether outputs are sufficient;
- whether to ask another worker;
- how to combine results.

This can be LLM-driven or code-driven.

---

## 4. LLM orchestration vs code orchestration

Current OpenAI Agents SDK documentation makes this distinction explicit:

```text
LLM orchestration
    -> model chooses handoffs / agent-tools

code orchestration
    -> application decides sequence / parallelism / routing
```

Tiny-Agent keeps the same principle learned in Stage 02:

> Use deterministic code when the control rule is already known.

If every request always requires:

```text
research
-> legal review
-> final formatting
```

write the workflow.

Do not pay an LLM to rediscover the arrows in your architecture diagram on every request.

---

## 5. OpenAI Agents SDK: agents as tools

The SDK exposes a specialist through `Agent.as_tool()`.

Conceptually:

```python
specialist_tool = specialist.as_tool(
    tool_name="refund_expert",
    tool_description="Handle a bounded refund subtask",
)

manager = Agent(
    ...,
    tools=[specialist_tool],
)
```

The important runtime meaning is:

> The nested specialist returns to the original manager.

The manager keeps conversation ownership.

---

## 6. OpenAI Agents SDK: handoffs

A triage Agent can instead declare:

```python
triage = Agent(
    ...,
    handoffs=[refund_agent],
)
```

The SDK presents handoffs to the model as transfer Tools and, when selected, transfers execution to the target Agent.

This is not just a different method name.

It changes the responsibility graph.

---

## 7. Context behavior also differs

A manager calling an Agent as a Tool normally provides a generated subtask input.

A handoff often transfers conversation history so the next Agent can continue naturally.

That means handoff context deserves extra attention.

The OpenAI Agents SDK exposes input filtering for handoffs precisely because blindly forwarding all prior Tool/history data may be undesirable.

A useful rule:

```text
conversation continuity
!=
permission to copy every internal state field
```

---

## 8. Delegation task contracts

Bad delegation:

```text
"Do the important part."
```

Better:

```text
Goal:
Extract three evidence-backed risks.

Constraints:
- Use only supplied evidence.
- Do not make external mutations.
- Return exactly three bullets.

Success condition:
Every bullet must cite an evidence ID.
```

A sub-Agent is not psychic.

If the supervisor reformulates the user's task badly, the worker may return a beautifully written answer to the wrong problem.

---

## 9. Constraint loss

Multi-Agent chains introduce a new failure mode:

```text
original user request
        |
        v
supervisor summary
        |
   constraint omitted
        |
        v
worker solves wrong task
```

The output may still look coherent.

So delegation payloads should preserve critical constraints explicitly.

For high-value tasks, validate delegated task contracts just as Stage 07 validates Tool arguments.

---

## 10. Result acceptance is another decision

A supervisor should not assume:

```text
worker returned text
=> task successfully completed
```

It may need to check:

- schema;
- evidence coverage;
- required constraints;
- policy compliance;
- quality threshold.

Stage 08 evaluators can often be reused here.

---

## 11. Failed handoff behavior

Tiny-Agent uses this invariant:

```text
handoff attempt
    |
 target fails
    |
 active owner stays source
```

Why?

Because ownership should change only when the receiver actually accepts the task successfully.

This is analogous to transaction semantics:

> Do not update the control pointer before the transfer succeeds.

---

## 12. Escalation is not handoff ping-pong

A legitimate path may be:

```text
triage -> billing -> human
```

A broken path may be:

```text
triage -> billing -> triage -> billing -> triage ...
```

The latter burns:

- tokens;
- latency;
- budget;
- user patience.

Stage 09 therefore adds explicit handoff budgets and repeated-edge limits.

---

## 13. Manager vs handoff checklist

Use **manager / agents-as-tools** when:

- one Agent should own final response quality;
- specialists perform bounded subtasks;
- global context should stay centralized;
- you want deterministic fan-in.

Use **handoff** when:

- a specialist should continue the conversation directly;
- ownership really changes by domain;
- the specialist needs conversational continuity;
- decentralized responsibility is intentional.

Do not choose based on which diagram has cooler arrows.

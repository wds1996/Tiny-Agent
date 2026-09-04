# 03 — Context Ownership, Shared State & Information Boundaries

Multi-Agent systems move information between reasoning boundaries.

That creates both capability and risk.

---

## 1. Do not equate "shared context" with "copy everything"

A naive implementation does:

```python
worker_input = entire_application_state
```

That may include:

```text
conversation history
retrieved documents
other Agents' scratch state
billing data
credentials
approval records
internal routing metadata
```

Most workers do not need all of it.

---

## 2. Tiny-Agent context model

Stage 11 introduces:

```text
ContextEnvelope
├── shared
└── private_by_agent
```

Then a `ContextPolicy` projects the target view.

Example:

```text
shared
├── question
├── language
├── customer_id
└── api_key

private_by_agent
├── research
│   └── source_policy
└── billing
    └── invoice_scope
```

Policy:

```text
research -> question, language
billing  -> customer_id
```

So the views become:

```text
research
├── shared: question, language
└── private: source_policy

billing
├── shared: customer_id
└── private: invoice_scope
```

`api_key` is not forwarded at all.

---

## 3. Why private namespaces matter

If every Agent writes into one flat dictionary:

```python
state["notes"] = ...
```

then two Agents may:

- overwrite one another;
- mistake another Agent's draft for approved state;
- accidentally expose internal reasoning artifacts;
- create hidden coupling.

Namespaces make ownership visible.

---

## 4. Shared state should contain contracts, not junk drawers

Good shared fields:

```text
task_id
user_goal
approved constraints
artifact references
public intermediate results
```

Risky shared fields:

```text
all raw prompts
all credentials
all internal scratchpads
all Tool outputs forever
```

Shared state should be designed like an API contract.

If the field is there only because "someone might need it later," that is how junk drawers become architecture.

---

## 5. Passing summaries vs raw history

A specialist often needs:

```text
user goal
critical constraints
relevant evidence
```

not:

```text
137-message transcript
all prior Tool calls
all routing chatter
```

So a manager can pass a bounded delegation packet:

```text
Task
Constraints
Relevant Context
Expected Output
```

This reduces token cost and lowers context contamination.

---

## 6. But summarization can lose constraints

Compression is not free.

Suppose original user request says:

```text
Compare A and B.
Use only primary sources.
Do not include pricing.
Return JSON.
```

Manager summary:

```text
Compare A and B.
```

The worker may be logically consistent and still violate three requirements.

So distinguish:

```text
compressible narrative context
```

from:

```text
non-negotiable structured constraints
```

Keep critical constraints explicit.

---

## 7. Handoffs and full conversation history

Handoffs often need more continuity than bounded delegation.

However:

```text
full conversation history
!=
full runtime state
```

Even if the user-visible conversation is forwarded, internal credentials, hidden policy state, and unrelated Tool traces should stay outside the receiving Agent's context unless explicitly needed.

Current OpenAI Agents SDK handoffs support input filtering for this reason.

---

## 8. Shared memory is not automatically a good idea

Stage 06 taught:

```text
short-term state
long-term memory
Store
```

Multi-Agent adds a new question:

> Who owns a memory?

Possible scopes:

```text
user
team
Agent role
project
conversation
```

Do not let every Agent read/write every long-term memory namespace by default.

A worker's temporary observation should not silently become company-wide procedural memory.

---

## 9. Blackboard pattern

A classic multi-Agent pattern is a shared blackboard:

```text
Agent A -> shared board <- Agent B
                ^
                |
              Agent C
```

This can be useful when specialists contribute structured artifacts.

But it needs rules:

- schema;
- ownership;
- versioning;
- write permissions;
- conflict handling;
- provenance.

Without those rules, the blackboard becomes a group chat where everyone edits the same sentence at once.

---

## 10. Prefer artifacts for durable intermediate results

Instead of sharing huge prompts, exchange explicit artifacts:

```text
research_report.json
risk_review.json
draft.md
```

Each artifact can have:

```text
producer
schema/version
created_at
source references
approval status
```

This makes coordination easier to inspect and evaluate.

A2A also makes a useful distinction between conversational `Message` content and durable task `Artifact` outputs.

---

## 11. Context and authority are separate

Giving an Agent information does not necessarily give it permission to act.

Similarly, allowing an Agent to execute a Tool does not mean it needs every sensitive context field.

Keep these controls separate:

```text
ContextPolicy
DelegationPolicy
Tool permission policy
Approval policy
```

Stage 09 still applies inside every Agent boundary.

---

## 12. Agent identity in traces

Stage 10 tracing should identify:

```text
agent.name
source_agent
target_agent
coordination.mode
```

without automatically recording raw delegation content.

This makes it possible to debug:

```text
manager -> research -> manager -> writer
```

while preserving privacy rules.

---

## 13. A context-transfer checklist

Before forwarding data to another Agent, ask:

1. Does the receiver need this field?
2. Is it user-visible or internal runtime state?
3. Does it contain credentials or sensitive data?
4. Is a summary enough?
5. Which constraints must remain exact?
6. Who owns the resulting artifact?
7. Can the receiver write back into shared state?

The best multi-Agent systems do not merely coordinate intelligence.

They coordinate **information ownership**.

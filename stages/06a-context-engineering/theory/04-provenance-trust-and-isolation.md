# 04 — Provenance, trust, and context isolation

A context item should answer more than “what text is this?”

Useful metadata includes:

```text
where did it come from?
who owns it?
when was it produced?
is it original or summarized?
what trust class does it have?
which task/thread/user may see it?
```

## Provenance prevents category mistakes

Examples:

```text
memory:user-preference
    -> personalization
    -> not scientific evidence

retrieval:paper-fulltext
    -> evidence candidate
    -> still untrusted instructions

summary:old-thread
    -> derived state
    -> may have lost detail
```

## Trust is not one boolean in real systems

Tiny-Agent's teaching `trusted` flag is intentionally small. Production systems often need richer dimensions:

- source authenticity;
- content authority;
- confidentiality;
- freshness;
- tenancy/ownership;
- evidence quality.

A source can be authentic but still untrusted as an instruction. A signed paper PDF is still not allowed to rewrite tool permissions.

## Context isolation for sub-Agents

Do not do:

```text
parent state
-> deepcopy everything
-> specialist Agent
```

Project a minimum view:

```text
researcher -> question + evidence tools
writer     -> evidence + style requirements
reviewer   -> draft + evidence inventory
```

This reduces leakage, distraction, and privilege coupling.

## Context poisoning

Long-lived summaries/memory/skills can persist malicious or incorrect content across sessions. Therefore durable context deserves stronger governance than one-turn retrieved text:

```text
candidate
-> validate/source label
-> policy
-> durable store
-> later retrieval
```

The safest Agent does not rely on the model remembering which paragraph was malicious three context windows ago. Control-plane policy remains external and deterministic.

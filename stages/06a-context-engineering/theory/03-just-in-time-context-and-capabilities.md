# 03 — Just-in-time context and capabilities

A scalable Agent should not preload every instruction, tool, document, and skill at startup.

The recurring pattern is **progressive disclosure**:

```text
small catalog / index
      ↓ relevance decision
full instructions or data
      ↓ deeper need
specific files/resources
```

## Evidence just in time

RAG already applies this idea:

```text
large corpus
-> retrieve a few candidates
-> send selected evidence
```

## Skills just in time

Stage 06B applies the same pattern to procedural knowledge:

```text
all skill names/descriptions
-> activate one relevant SKILL.md
-> load references/scripts only when needed
```

## Tools just in time

Tool schemas also consume attention and create selection ambiguity.

Instead of exposing 300 overlapping tools on every turn, an application can:

1. route to a capability domain;
2. expose a smaller allowlisted tool subset;
3. let the model choose within that subset;
4. keep authorization outside the model.

Dynamic tool exposure is **not** dynamic permission. A tool hidden from one turn may still exist, and a visible tool may still be denied by policy.

## Workspace files just in time

Long-horizon Agents should often inspect the filesystem rather than paste entire projects into the prompt.

```text
workspace manifest / file list
      ↓
read relevant file
      ↓
patch/write artifact
```

This is one reason modern Agent harnesses increasingly combine context engineering with controlled computer environments.

## The unifying idea

RAG, tool filtering, skill activation, workspace browsing, and memory retrieval are all instances of the same design principle:

> Keep large state outside the prompt and bring in the minimum relevant slice when the current decision requires it.

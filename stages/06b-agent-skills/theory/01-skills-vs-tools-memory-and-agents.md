# 01 — Skills vs Tools, MCP, memory, and Agents

The word “skill” is often used loosely. In this stage it has a precise meaning: a portable package of **procedural knowledge** that an Agent can discover and load when a task matches.

## Tool

```text
search(query)
write_file(path, content)
run_tests()
```

A Tool exposes an action interface.

## MCP

MCP standardizes how an application discovers/calls external Tools and reads Resources/Prompts across a protocol boundary.

## Skill

A Skill might say:

```text
When reviewing a research answer:
1. enumerate factual claims;
2. map every claim to evidence;
3. distinguish metadata from full text;
4. reject unsupported conclusions;
5. produce a structured review.
```

It may reference scripts/templates, but the skill itself is primarily reusable procedure.

## Memory

Memory stores selected information across time:

```text
user prefers concise output
previous project decision
```

A procedural Skill should normally be version-controlled and governed differently from user memory.

## Agent

The Agent runtime combines:

```text
model
+ context policy
+ tools
+ skills
+ memory
+ workspace
+ execution policy
```

Skills therefore specialize a general Agent without requiring a new hard-coded Agent class for every domain.

## A useful test

Ask:

> Does this object describe an executable capability, retained fact, or reusable procedure?

That usually tells you whether it belongs as Tool/MCP, Memory, or Skill.

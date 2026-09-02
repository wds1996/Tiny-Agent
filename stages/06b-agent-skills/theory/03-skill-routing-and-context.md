# 03 — Skill routing and context composition

Skill activation is a routing problem.

```text
current task
+ skill metadata catalog
      ↓
relevance decision
      ↓
activate zero/one/few skills
      ↓
context budget
      ↓
model turn
```

## Prefer deterministic routing when possible

If the file type or command unambiguously determines a skill, ordinary code can activate it.

Examples:

```text
*.pdf -> pdf-processing
pull request -> code-review
```

Use an LLM router only when semantic judgment is genuinely needed, and constrain it to installed skill names.

## Skills compose with Tools

A skill can explain a multi-tool procedure:

```text
research-review
  -> retrieve evidence
  -> inspect citation inventory
  -> run deterministic checks
  -> request model critique
```

The skill does not bypass ToolRegistry, MCP host policy, approval, sandboxing, or identity policy.

## Skills consume context

Activating too many skills can create contradictory procedures and dilute attention. Context policy should therefore treat skill bodies as optional high-value context, not universal startup text.

## Skills and sub-Agents

A specialist Agent can receive one activated skill without receiving every skill available to the parent. This is another form of least-context/least-authority design.

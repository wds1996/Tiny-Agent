# Stage 06B — Agent Skills & Procedural Knowledge

Tools tell an Agent **what actions exist**. Skills teach an Agent **how to perform a recurring class of work well**.

This stage adopts the open Agent Skills format instead of inventing a Tiny-Agent-only skill file.

```text
skill-name/
├── SKILL.md
├── scripts/       optional
├── references/    optional
└── assets/        optional
```

## Central distinction

```text
Tool / MCP
    = executable or readable capability

Skill
    = portable procedural knowledge + instructions + optional resources

Memory
    = retained information selected by policy

Agent
    = runtime/control system that may use all three
```

A skill may explain how to use several tools. It does not grant permission to them.

## Learning objectives

After this stage you should be able to:

1. explain Skill vs prompt vs Tool vs MCP vs memory;
2. read/write the open `SKILL.md` format;
3. explain required `name` and `description` metadata;
4. use progressive disclosure: discovery -> activation -> resource loading;
5. keep many installed skills out of the active context until needed;
6. design focused scripts/references/assets;
7. understand that `allowed-tools` is experimental metadata, not authorization;
8. validate skill names/paths and reject directory traversal/symlink escape;
9. treat third-party skill instructions/code as a software supply-chain boundary;
10. evaluate whether a skill improves task success enough to justify maintenance.

## Learning order

1. `theory/01-skills-vs-tools-memory-and-agents.md`
2. `theory/02-skill-format-and-progressive-disclosure.md`
3. `code/skill_catalog_demo.py`
4. inspect `skills/research-review/`
5. `theory/03-skill-routing-and-context.md`
6. `theory/04-skill-trust-governance-and-evaluation.md`
7. `src/tiny_agent/skills.py`
8. `tests/test_skills.py`
9. `exercises/review-questions.md`

## Install

```bash
python -m pip install -e ".[dev,stage06b]"
```

The optional dependency is PyYAML because `SKILL.md` metadata is YAML frontmatter.

## References

- Agent Skills specification — https://agentskills.io/specification
- Agent Skills overview — https://agentskills.io/home
- Anthropic, *Equipping agents for the real world with Agent Skills* — https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills

## Milestone

Build a catalog with many skill metadata records in startup context, activate only the relevant skill, load its references on demand, and still run every executable action through ordinary Tiny-Agent validation/authorization.

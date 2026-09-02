# 02 — Skill format and progressive disclosure

The open Agent Skills format requires a directory containing `SKILL.md` with YAML frontmatter.

Minimal form:

```markdown
---
name: research-review
description: Review a research answer for evidence grounding and citation support. Use after drafting evidence-based research output.
---

# Instructions
...
```

The official specification constrains names and descriptions so catalogs remain predictable.

## Three levels of disclosure

```text
1. discovery
   name + description

2. activation
   full SKILL.md instructions

3. execution/detail
   scripts / references / assets as needed
```

This is context engineering applied to procedural knowledge.

If 100 skills each contain 3,000 tokens, loading all bodies would consume ~300K tokens before the user asks anything. Loading only metadata lets the Agent decide which skill deserves activation.

## Tiny-Agent `SkillCatalog`

```python
catalog = SkillCatalog("skills")
skills = catalog.discover()
print(catalog.metadata_prompt())
activated = catalog.activate("research-review")
```

Discovery parses metadata. Activation loads the instructions and enumerates safe in-root resource files.

## Keep resources focused

Large reference material belongs in `references/`, reusable executable helpers in `scripts/`, and templates/static resources in `assets/`.

The main `SKILL.md` should teach the workflow and tell the Agent when deeper material is needed rather than reproducing an entire company wiki.

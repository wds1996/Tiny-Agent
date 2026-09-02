# 02 — SKILL.md Format and Progressive Disclosure

Tiny-Agent adopts the open Agent Skills format instead of inventing a repository-only skill language.

The basic directory is deliberately boring:

```text
skill-name/
├── SKILL.md          required
├── scripts/          optional executable helpers
├── references/       optional detailed documentation
└── assets/           optional templates/data/resources
```

Boring interoperability is often excellent engineering. Nobody has ever won a production incident by proudly announcing, "Good news, our configuration format is unique."

---

## 1. SKILL.md = metadata + instructions

The file starts with YAML frontmatter followed by Markdown:

```markdown
---
name: research-review
description: Review research claims against cited evidence. Use when checking literature reviews, research reports, or citation grounding.
license: MIT
compatibility: Requires access to the relevant evidence text.
metadata:
  owner: tiny-agent
  version: "1"
---

# Research Review Procedure

1. Enumerate claims.
2. Find the evidence cited for each claim.
3. Compare wording strength with evidence strength.
4. Flag unsupported claims.
```

The metadata helps discovery. The body teaches the procedure.

---

## 2. Name and description are routing infrastructure

The official format requires a constrained `name` and a meaningful `description`.

Why care so much about description quality?

Because progressive disclosure begins with metadata. If the description is:

```text
"Helps with stuff."
```

then the router has almost no useful signal.

Better:

```text
"Reviews research claims against cited evidence. Use for literature reviews,
research reports, citation verification, or grounding checks."
```

A good description explains both **what the Skill does** and **when it should activate**.

---

## 3. Tiny-Agent validates the format

Real `SkillCatalog` discovery, simplified:

```python
catalog = SkillCatalog("skills")
skills = catalog.discover()

for skill in skills:
    print(skill.name, skill.description)
```

The parser checks important constraints:

```text
valid lowercase/hyphen name
name matches directory
non-empty bounded description
frontmatter is a mapping
metadata is a string map
allowed-tools has expected shape
paths remain inside the skill root
```

Bad skill:

```text
skills/review/SKILL.md
name: TotallyDifferentName
```

Tiny-Agent fails instead of quietly creating an ambiguous catalog.

---

## 4. Progressive disclosure has three levels

A useful Skill system does **not** load every file from every installed Skill at startup.

```text
Level 1: discovery
    name + description metadata

Level 2: activation
    full SKILL.md instructions

Level 3: resource access
    one needed script/reference/asset
```

The official Agent Skills guidance recommends this shape because many Skills can coexist without consuming the entire context window.

Think of a library:

```text
catalog card      -> metadata
borrow the book   -> activate Skill
open appendix C   -> load reference as needed
```

You do not photocopy the whole building before asking the librarian a question.

---

## 5. Tiny-Agent metadata vs activation

Startup-sized metadata:

```python
catalog = SkillCatalog("skills")
print(catalog.metadata_prompt())
```

Output shape:

```text
- code-review: Review code changes for correctness and safety.
- research-review: Review research claims against evidence.
```

Activation:

```python
skill = catalog.activate("research-review")

print(skill.instructions)
print(skill.references)
print(skill.scripts)
print(skill.assets)
```

Notice that references/scripts/assets are enumerated only after activation.

---

## 6. References should be focused

Bad:

```text
SKILL.md = 40,000 tokens of every policy, API manual, example, and historical note
```

Better:

```text
SKILL.md
  -> concise operating procedure
references/
  -> evidence-policy.md
  -> output-format.md
  -> edge-cases.md
```

Then the Agent can load only the needed reference.

This is the same context-engineering principle from Stage 06A applied to procedural knowledge.

---

## 7. Scripts are executable software

A Skill may contain:

```text
scripts/check_citations.py
```

That file is not "just prompt context." It is code.

Before executing third-party scripts, consider:

- source/trust;
- dependency provenance;
- sandbox policy;
- filesystem/network access;
- credentials exposure;
- review/signing/version policy.

Stage 09A provides the controlled compute boundary.

A markdown directory becoming executable does not make the supply chain disappear; it merely gives it nicer headings.

---

## 8. `allowed-tools` is not Tiny-Agent authorization

The Agent Skills format defines an experimental `allowed-tools` field. Implementations may use it differently.

Tiny-Agent exposes it on `SkillDescriptor`:

```python
print(skill.descriptor.allowed_tools)
```

but deliberately does **not** convert it into runtime permissions.

```text
Skill metadata says Bash(git:*)
          ↓
model may understand intended capability
          ↓
Tiny-Agent policy independently decides what is actually allowed
```

Portable metadata and local authorization are different layers.

---

## 9. Safe file discovery

Third-party Skill resources create a path-boundary problem.

Tiny-Agent resolves every discovered file and verifies it remains under the Skill root. This catches traversal/symlink escapes such as a resource that resolves to:

```text
../../.ssh/id_rsa
```

The lesson generalizes:

> A relative-looking path is not trusted until its resolved target is checked against the permitted root.

Stage 09A uses the same principle for Agent workspaces.

---

## 10. Worked design

For a `data-analysis` Skill:

```text
data-analysis/
├── SKILL.md
├── references/
│   ├── statistical-checks.md
│   └── chart-guidelines.md
├── scripts/
│   └── validate_csv.py
└── assets/
    └── report-template.md
```

Runtime flow:

```text
user asks to analyze CSV
-> metadata router selects data-analysis
-> load SKILL.md
-> read statistical-checks only if needed
-> sandbox validate_csv.py if execution is authorized
-> use report-template at final artifact step
```

That is progressive disclosure across both context and compute.

---

## Completion check

You should be able to:

1. write valid SKILL.md metadata;
2. explain why description quality affects routing;
3. distinguish discovery, activation, and resource loading;
4. explain why scripts create a supply-chain/execution boundary;
5. explain why `allowed-tools` is not automatically authorization;
6. validate paths and keep resource access inside the Skill root.

# Stage 08: Stop Welding Every Procedure into the System Prompt — Agent Skills

> Language: **English** | [简体中文](README.zh-CN.md)

Stage 07 turned model context into a deliberate selection problem.

That immediately exposes another source of context bloat: reusable procedures.

A team may have repeatable guidance for release checks, code reviews, migrations, incident response, or data analysis. Putting every procedure permanently into one system prompt makes every task pay the context cost of every other task.

The natural alternative is:

> **Advertise that a procedure exists, then load its full instructions only when the task needs it.**

That is the central idea behind Agent Skills and progressive disclosure.

---

## 1. A Skill describes how to work

Keep the earlier abstractions separate.

A Tool answers:

> What action can the system execute?

MCP answers:

> How are external capabilities and context exposed across a protocol boundary?

Memory answers:

> What information should survive over time?

Context Engineering answers:

> What should this model turn see?

A Skill answers:

> What reusable procedure should guide this kind of task?

A release-check Skill may say to identify the target version, run deterministic tests, inspect generated files, read a checklist, and report failures.

It does not itself mean `deploy_production()`.

```text
Skill = procedural guidance
Tool  = executable capability
```

---

## 2. Why not make every Skill a Workflow?

If control flow is completely deterministic, Stage 02 already gave us the answer: write a workflow.

Skills fit procedures that are reusable and structured but still require task-specific judgment.

```text
deterministic control flow
    -> Workflow

model-guided reusable procedure
    -> Skill
```

A Skill can also instruct the Agent to enter an application-owned workflow when a high-impact action is reached.

---

## 3. The smallest Skill

The open Agent Skills format centers on a directory containing `SKILL.md`:

```text
release-check/
└── SKILL.md
```

The file begins with YAML frontmatter:

```markdown
---
name: release-check
description: Use when preparing a software release and you need a repeatable pre-release verification procedure.
---
```

`name` is a stable identity.

`description` is also a routing surface: it should explain both what the Skill does and when it is useful.

A description such as “A useful skill” gives the Agent almost nothing to match against a task.

---

## 4. Directory identity and metadata identity should agree

The teaching catalog requires:

```text
release-check/
    SKILL.md -> name: release-check
```

A mismatch between directory name and metadata makes caches, logs, resource paths, and versioning harder to reason about.

Portable formats benefit from boring, stable identity.

---

## 5. Progressive disclosure: show the menu before the kitchen

Imagine one hundred Skills with two thousand tokens of instructions each.

Loading every body at startup would spend two hundred thousand tokens before the user asks a question.

Progressive disclosure separates the lifecycle:

```text
all skills
    ↓ metadata only

matching skill
    ↓ full instructions

needed resource
    ↓ load on demand
```

Discovery exposes small metadata such as `name` and `description`.

Activation loads the `SKILL.md` body.

Resources such as references are read only when the procedure reaches the point where they matter.

This is Context Engineering applied to procedural knowledge.

---

## 6. Discovery should not secretly load the full body

The chapter's `SkillMetadata` contains only:

```python
name
description
path
```

Full instructions appear only in `ActivatedSkill`.

That makes:

```python
catalog.discover()
```

and:

```python
catalog.activate("release-check")
```

genuinely different operations.

Progressive disclosure should exist in code, not only in a diagram.

---

## 7. Skill bodies should contain procedures, not slogans

“Be careful and do high quality work” is not a procedure.

Useful Skills provide ordered actions, decision points, examples, and relevant edge cases.

The teaching release Skill tells the Agent to establish release identity, run tests, inspect temporary files, consult a checklist, and report failure before suggesting an action.

It still does not grant deployment authority.

---

## 8. Put conditional detail in resources

A Skill may have:

```text
release-check/
├── SKILL.md
└── references/
    └── checklist.md
```

The main instructions explain when the checklist matters. The catalog reads it only on demand:

```python
catalog.read_resource(
    "release-check",
    "references/checklist.md",
)
```

This preserves a small activation footprint.

---

## 9. Resource paths need boundaries

A resource loader must reject:

```text
../../secret.txt
```

The teaching implementation resolves paths and verifies that the target remains inside the Skill directory.

This is not a complete sandbox. It is a concrete reminder that every external-loading mechanism needs a boundary.

---

## 10. A bundled script is not automatic execution authority

The Skill format can include scripts.

That does not mean a Host should execute arbitrary scripts simply because a Skill contains them.

```text
skill contains script
!=
script is trusted to execute
```

Execution environment, filesystem access, network access, and credentials remain Host policy.

Stage 12 will address workspace and sandbox boundaries. Stage 08 deliberately does not jump ahead and run arbitrary Skill scripts.

---

## 11. Declared Tool usage is not authorization

Some Skill clients support metadata describing expected or allowed Tools.

Treat that as a declaration or policy input, not magical permission.

A Skill mentioning a money-transfer Tool does not grant the Agent the right to transfer money.

The Host remains the authority boundary.

---

## 12. Skills are not memory

Memory may retain “the user prefers Chinese.”

A Skill may contain “how to perform a release review.”

The first is retained information. The second is reusable procedure.

Their provenance and governance should differ as well. Ordinary conversation should not silently rewrite the system's procedural Skills.

---

## 13. Skills and MCP compose

A release Skill may instruct the Agent to use a GitHub Tool.

That Tool may arrive through MCP.

```text
Skill
    ↓ procedural guidance
Agent / Runtime
    ↓ selects allowed capability
MCP Tool
    ↓ external action
```

One packages procedure; the other standardizes a capability boundary.

---

## 14. A minimal Skill catalog

The chapter implements:

```python
catalog = SkillCatalog(root)
```

Discovery:

```python
catalog.discover()
```

Activation:

```python
catalog.activate("release-check")
```

On-demand resource loading:

```python
catalog.read_resource(
    "release-check",
    "references/checklist.md",
)
```

No model or framework is required to understand the lifecycle.

---

## 15. Description quality matters

Skill quality has at least two layers:

```text
discovery quality
    -> can the Agent identify the right Skill?

procedure quality
    -> do activated instructions guide the task well?
```

A detailed body is not useful if metadata never makes the Skill discoverable.

Later evaluation work should test both.

---

## 16. Format boundary used in this chapter

The open Agent Skills format uses a `SKILL.md` file with YAML frontmatter and Markdown instructions. `name` and `description` form the basic metadata, and Skill directories may include resources such as `references/`, `scripts/`, and `assets/`.

The teaching parser intentionally supports only the simple scalar fields needed for this chapter. A production client should use mature YAML parsing and specification validation rather than extending this tiny parser into a home-grown YAML implementation.

---

## 17. Run the chapter

```bash
python stages/08-agent-skills/code/demo.py
python stages/08-agent-skills/code/checks.py
```

The checks verify metadata-only discovery, body loading on activation, directory/name identity, name validation, and resource path containment.

---

## 18. Why reliability and safety must come next

Our Agent can now retrieve data, remember information, load procedures, call remote systems, and pause for human review.

Its failures can therefore cause more than bad prose.

Remote calls can time out. Retries can duplicate side effects. Models can repeat actions. External content can conflict with instructions. Skills can request capabilities they should not have. Budgets can run away.

At this point, postponing safety would be like adding a larger engine and scheduling the brake lesson for next month.

Stage 09 adds reliability, validation, budgets, permissions, and execution guardrails.

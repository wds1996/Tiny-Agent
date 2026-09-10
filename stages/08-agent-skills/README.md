# Stage 08: Load Procedures When They Matter — Agent Skills

> Language: **English** | [简体中文](README.zh-CN.md)

[Stage 07](../07-context-engineering/README.md) established a rule: a model
turn should receive the information it needs now, rather than every piece of
information the system owns.

Reusable procedures create the same problem. A release check, a code review,
a migration, and incident response may each have useful instructions. Putting
all of them permanently in a system prompt makes every task pay for every
other procedure.

This chapter uses a simple alternative:

> **First advertise which procedures exist. Load one procedure only when the task calls for it.**

We will use one `release-check` Skill throughout the chapter.

---

## 1. What a Skill adds to the Agent

A Skill is reusable **procedural guidance**. It tells an Agent how to approach
a category of task; it does not perform the task by itself.

For a release check, the guidance may be:

```text
identify the target version and branch
run deterministic tests
inspect generated files
read the release checklist when needed
report failures before suggesting a release
```

That fills a different role from the components introduced earlier:

| Component | Main question it answers |
| --- | --- |
| Workflow | What fixed control flow should the program run? |
| Tool | What action can the system execute? |
| MCP | How are remote capabilities and resources exposed? |
| Memory | What selected information survives over time? |
| Context Engineering | What should this model turn receive? |
| Skill | What reusable procedure should guide this task? |

Use a Workflow when steps and branches are fully deterministic. Use a Skill
when the procedure is stable but applying it needs task-specific judgment. A
Skill may tell the Agent to enter an application-owned Workflow at a high-impact
point; it does not replace that Workflow.

---

## 2. A Skill is a small, versionable package

This chapter uses a directory whose entry point is `SKILL.md`:

```text
release-check/
├── SKILL.md
└── references/
    └── checklist.md
```

`SKILL.md` is the required entry point. A practical Skill package can also
contain optional material alongside it:

```text
release-check/
├── SKILL.md                 required: identity and main procedure
├── references/              optional: detailed documents read on demand
├── scripts/                 optional: deterministic helpers
└── assets/                  optional: templates, examples, or other files
```

Before using those names, fix their meaning:

- **Frontmatter** is the small YAML-like header between the first two `---`
  lines in `SKILL.md`.
- **Discovery** scans Skill directories and reads that header, producing a
  small list of metadata that a router can inspect.
- **Activation** loads the Markdown body of one selected Skill.
- A **resource** is an additional file inside that Skill package.
- The **Host** is the application that owns the Agent. It decides which Tools,
  scripts, files, credentials, and approvals are actually available.

These parts have different jobs and loading times:

| Part | What it contains | When it should be read or used |
| --- | --- | --- |
| Frontmatter in `SKILL.md` | Name and description | Discovery |
| Markdown body in `SKILL.md` | Goal, ordered procedure, and decision points | Activation |
| `references/` | Long checklists, policies, and edge cases | Only when a procedure step needs them |
| `scripts/` | Repeatable deterministic work | Only after Host policy permits execution |
| `assets/` | Templates, sample files, or media | Only when the task needs that artifact |

The teaching Skill has only a reference because that is enough to demonstrate
the lifecycle. The absence of `scripts/` and `assets/` does not make a Skill
incomplete; they are optional ways to keep the main procedure focused.

Here is the complete teaching Skill:

```markdown
---
name: release-check
description: Use when preparing a software release and you need a repeatable pre-release verification procedure.
---

# Release Check

Before proposing a release:

1. Identify the target version and branch.
2. Run the project's deterministic tests.
3. Check that generated or temporary files are not included.
4. Review the release-specific checklist in `references/checklist.md`.
5. Report failures before suggesting a release action.

Do not publish or deploy anything merely because this skill was activated. The host application still owns execution and approval.
```

The procedure refers to a separate resource rather than putting every release
detail into its main body. This is the actual
[`references/checklist.md`](code/skills/release-check/references/checklist.md):

```markdown
# Release Checklist

- Version number is intentional.
- Tests relevant to the changed area pass.
- Documentation links resolve.
- No credentials, caches, or temporary artifacts are included.
- High-impact deployment actions require the application's normal approval path.
```

This checklist is useful only after the Agent has reached step 4. Keeping it
separate means a task that merely discovers `release-check` does not need to
load it.

The frontmatter answers discovery questions before the full instructions are
loaded:

- `name` is the stable identifier used by code, logs, and resource paths.
- `description` says both what the Skill does and when it should be selected.

The directory and `name` should agree. In this example, the directory is
`release-check` and the metadata name is also `release-check`. Stable identity
avoids ambiguous resource paths and confusing records later.

---

## 3. Progressive disclosure is the reason Skills help Context

Suppose a repository has one hundred Skills, each with long instructions.
Loading every body at startup recreates the context-bloat problem from Stage 07.

Instead, loading has three levels:

```text
all Skill directories
        ↓ discover
name + description
        ↓ activate the matching Skill
full SKILL.md instructions
        ↓ read only when a step needs it
specific reference, script, or asset
```

Discovery is a menu. Activation opens one recipe. A resource supplies a detail
only when that recipe reaches the relevant step.

The distinction must exist in code. In [`skills.py`](code/skills.py),
`discover()` calls `read_frontmatter()`, which reads line by line and stops at
the closing `---`; it never calls `read_text()` for the complete file.
`SkillMetadata` contains only `name`, `description`, and `path`. Activation is
the separate operation that calls `parse_skill_file()` and returns an
`ActivatedSkill` containing the body.

---

## 4. See the lifecycle in one small catalog

The catalog deliberately has no model, vector database, or framework. That
keeps the lifecycle visible before later stages combine it with routing and
runtime policy.

This complete program is also [`code/demo.py`](code/demo.py):

```python
from pathlib import Path

from skills import SkillCatalog


def main() -> None:
    root = Path(__file__).with_name("skills")
    catalog = SkillCatalog(root)

    for skill in catalog.discover():
        print("discovered:", skill.name, "->", skill.description)

    active = catalog.activate("release-check")
    print("\nactivated instructions:\n", active.instructions)

    reference = catalog.read_resource(
        "release-check",
        "references/checklist.md",
    )
    print("\non-demand reference:\n", reference)


if __name__ == "__main__":
    main()
```

Read it in order:

1. `discover()` reads only metadata, so a caller can decide which Skill is
   relevant without adding every procedure body to Context.
2. `activate("release-check")` reads the selected `SKILL.md` body.
3. `read_resource(...)` reads the checklist only after the activated procedure
   reaches that step.

The catalog does not do semantic routing. In a real Agent, a router or model
can select a Skill from discovered metadata. The catalog makes that later choice
cheap and explicit. The runnable DeepSeek example expresses selection as a
Tool Call: the model requests `activate_skill(name)`, while the Host validates
the name and returns the selected `SKILL.md` as a Tool Result.

The real implementation is [`deepseek_skills.py`](code/deepseek_skills.py).
These are its actual functions and responsibilities:

| Runtime step | Actual code |
| --- | --- |
| Publish `name` and `description` through a Tool schema | `build_skill_tool(candidates)` |
| Send the initial model request | `request_completion(..., tools=skill_tools, tool_choice="auto")` in `main()` |
| Validate the model's requested name and load `SKILL.md` | `activate_requested_skill(...)` |
| Put the selected Instructions into the conversation | `activation_result_message(...)` |
| Offer and validate on-demand reference loading | `build_reference_tool(...)` and `read_requested_reference(...)` |
| Continue the conversation after Tool Results | the second and, when needed, third `request_completion(...)` calls in `main()` |

The runtime trace is therefore:

```text
user task
  → model may call activate_skill(name)
  → Host validates name and returns SKILL.md
  → model may call read_skill_reference(path)
  → Host validates path and returns that reference
  → model writes its final response
```

The important boundary is the order: the model sees short metadata through the
Tool definition; it receives one selected procedure only through the Tool
Result; the Host independently approves every external action.

[`code/deepseek_skills.py`](code/deepseek_skills.py) turns this connection into
a runnable DeepSeek example. It follows the normal Tool Calling conversation:

1. The first model response may call `activate_skill(name)`. The Tool schema
   exposes only the discovered names and descriptions.
2. The Host validates the arguments, activates the named Skill, and returns
   its Instructions in a Tool Result.
3. If those Instructions name a reference, the model may call
   `read_skill_reference(path)`; the Host validates and returns only that file.
4. The model then produces a release-review proposal. This program has no Tool
   that can run tests, publish, or deploy.

The message sequence follows the official [DeepSeek Tool Calls guide](https://api-docs.deepseek.com/guides/tool_calls/): append the assistant's Tool Call, append the matching `tool` message with its `tool_call_id`, then ask the model to continue.

The default task is a release request. Pass `--task "..."` to try another
message. For an unrelated task, the model should answer without calling the
Skill activation Tool.

---

## 5. Keep detailed material in resources

The main Skill body should help the Agent make its next decision. Put
conditional detail in a resource instead of making every activation carry it.

For example, `references/checklist.md` is useful during a release check but
irrelevant to a database migration. Keeping it separate preserves the
three-level loading sequence.

Resource loading still needs a boundary. The teaching catalog resolves the
requested path and rejects a target outside the Skill directory, such as:

```text
../../secret.txt
```

The following is the actual method inside `SkillCatalog`; its indentation shows
that it is a class method rather than a standalone function.

```python
    def read_resource(self, skill_name: str, relative_path: str) -> str:
        skill_root = (self.root / skill_name).resolve()
        target = (skill_root / relative_path).resolve()
        if target != skill_root and skill_root not in target.parents:
            raise ValueError("resource path escapes skill directory")
        if not target.is_file():
            raise FileNotFoundError(relative_path)
        return target.read_text(encoding="utf-8")
```

This prevents the catalog from becoming an unrestricted file reader. It is not
a complete sandbox; filesystem permissions, secrets, and process isolation
remain Host responsibilities.

---

## 6. A Skill guides work; the Host controls execution

Activating the release Skill does not publish a release. A Skill may mention a
script or a Tool, but that is a request for a capability, not permission to use
it.

```text
Skill procedure
    ↓ proposes a next step
Host / Runtime policy
    ↓ permits or rejects the capability
Tool or script
    ↓ performs an action only when permitted
```

This is why the teaching catalog reads resources but never runs arbitrary
scripts from a Skill directory. The Host owns execution environment, file and
network access, credentials, approval, and authorization.

The same distinction explains how Skills work with MCP. A Skill can describe
when a GitHub Tool would be useful; MCP can expose that Tool across a protocol
boundary; the Host still decides whether this Agent may call it.

Skills are also different from Memory. Memory might retain “this user prefers
Chinese”; a Skill contains a maintained procedure such as “how to review a
release.” Ordinary conversation must not silently rewrite procedural guidance.

---

## 7. Write Skills for discovery and execution

A good Skill is not merely a block of text. It has a small internal structure:

```text
frontmatter  → lets the system discover and identify the Skill
body         → tells the Agent how to proceed after activation
resources    → hold detail that is useful only in some situations
scripts      → optionally package deterministic helpers
assets       → optionally package reusable task artifacts
```

The first two parts are the minimum. Resources, scripts, and assets are added
only when they make the procedure clearer or more reusable.

### Frontmatter: help the right task find the Skill

`name` gives the package a stable identity. `description` is the short text
available during discovery, before the Agent has loaded the body. It must name
both the task and the trigger. Compare:

```text
Weak:   Helps with software.
Useful: Use when preparing a software release and you need a repeatable pre-release verification procedure.
```

The weak description does not identify a task or a selection condition. The
useful description tells a router or model that this is for *pre-release
verification*, not general software work.

### Body: make the next step clear

The Markdown body is read only after activation. It should state the goal,
ordered actions, meaningful decision points, and the point at which an extra
resource is needed. For the teaching Skill, this means identifying the version,
running tests, inspecting artifacts, reading the checklist, and reporting a
failure before proposing a release.

“Be careful” is a quality wish. “If tests fail, report the failure before
suggesting a release” is an action with a decision boundary.

### Optional material: keep it useful without making it automatic

Put a long release matrix in `references/`; the body can point to it only when
the check reaches that stage. A future `scripts/verify_release.py` could
package deterministic checks, but the Skill should still state its expected
input, output, and failure meaning. An `assets/` directory could hold a release
notes template. None of these files gains automatic execution or authority by
being placed beside `SKILL.md`.

The parser in this chapter intentionally reads only simple scalar frontmatter
fields. A production client should use a mature YAML parser and validate the
format rather than extending this teaching parser into a custom YAML
implementation.

---

## 8. Run the chapter

The offline example needs only the Python standard library:

```bash
python stages/08-agent-skills/code/demo.py
python stages/08-agent-skills/code/checks.py
```

Observe the order in the demo: metadata first, then full instructions, then the
on-demand checklist. The checks verify metadata-only discovery, activation-time
body loading, directory/name identity, valid names, and resource path
containment.

To run the real model example, install the optional dependency and set the
same DeepSeek variables used in earlier stages. The variables must be set in
the same terminal that runs Python.

Windows Command Prompt:

```bat
python -m pip install -r stages/08-agent-skills/code/requirements.txt
set "DEEPSEEK_API_KEY=your_key_here"
set "DEEPSEEK_MODEL=your_available_deepseek_model"
python stages/08-agent-skills/code/deepseek_skills.py
```

PowerShell:

```powershell
python -m pip install -r stages/08-agent-skills/code/requirements.txt
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="your_available_deepseek_model"
python stages/08-agent-skills/code/deepseek_skills.py
```

The normal output prints discovered metadata, the user task, the model's Skill
Tool Call, the Host's activation result, and the procedure-guided reply. Add
`--show-model-conversation` to inspect the loaded Tool Result as well; use only
non-sensitive demo data.

---

## 9. Why reliability and safety come next

Skills give an Agent reusable ways of working. Along with Tools, MCP, Memory,
retrieval, and human approval, that creates more ways for a runtime to fail:
retries can duplicate effects, remote calls can time out, and a procedure can
request a capability it should not receive.

[Stage 09: Reliability, Safety, and Guardrails](../09-reliability-safety/README.md)
turns those risks into runtime rules that can be checked and enforced.

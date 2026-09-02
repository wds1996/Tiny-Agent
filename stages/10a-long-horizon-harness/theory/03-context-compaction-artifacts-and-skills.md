# 03 — Context Compaction, Artifacts, and Skills Across Sessions

Long-horizon Agents must preserve continuity while accepting that no single model context should contain the entire project history.

The trick is to externalize different kinds of continuity into the right places:

```text
facts/progress -> ledger/checkpoint
large outputs   -> artifacts/workspace
procedures      -> Skills
working view    -> compact model context
```

---

## 1. Do not use transcript replay as persistence

Bad:

```text
new session
-> replay 300 previous turns
-> add all Tool observations
-> add every generated file
```

This is expensive, slow, and eventually impossible.

Better:

```text
stable objective
+ ledger status
+ compact recent handoff
+ relevant artifacts
+ current Skill
+ current Tool subset
```

---

## 2. Compaction is a context operation

Stage 06A introduced:

```python
record = compact_items(
    old_context_items,
    key="handoff-summary",
    summarizer=summarize,
    provenance="derived:compaction",
)
```

In long-horizon work, compaction is especially useful at **session boundaries**:

```text
session work
-> save exact artifacts/ledger
-> create short handoff summary
-> next session starts small
```

Exact identifiers/ownership/approval facts remain structured state.

---

## 3. Artifacts carry large durable results

Suppose one task generates:

```text
12 MB CSV
20 figures
100 KB report draft
```

Do not paste them into `state.notes`.

Record references:

```text
artifacts/data-summary.csv
artifacts/figures/plot-1.png
reports/draft.md
```

Then context engineering selects previews/sections when needed.

An artifact is external working state, not an unusually ambitious prompt message.

---

## 4. Artifact provenance matters

Useful metadata/questions:

```text
which task produced it?
which input/source version?
which code/model?
validated by what test/evaluator?
which tenant/run owns it?
is it scratch or promoted output?
```

A future worker should not treat an unknown file as trustworthy merely because it exists in the workspace.

---

## 5. Skills preserve procedure across model sessions

A long-running coding/research job may use standardized procedure:

```text
research-review Skill
code-review Skill
data-analysis Skill
```

Instead of copying procedure into every handoff summary, keep it versioned as a Skill and activate it when the phase needs it.

```text
ledger says next task = review evidence
-> SkillCatalog activates research-review
-> ContextBuilder adds Skill instructions
```

This keeps handoffs focused on **project-specific state**, not repeated organizational procedure.

---

## 6. Skill version should be part of reproducibility

If a 3-day task spans a Skill update:

```text
day 1 Skill v1
release v2
new worker uses v2
```

Behavior may change mid-run.

For high-reproducibility tasks, pin/record the Skill version/source used by the run or explicitly migrate it.

The same applies to model/provider versions and code/environment artifacts.

---

## 7. Build context from durable sources

Conceptual long-horizon worker:

```python
items = [
    ContextItem("objective", "task", state.objective, required=True, trusted=True),
    ContextItem("handoff", "note", handoff, priority=90),
    ContextItem("skill", "skill", activated_skill.instructions, priority=85),
    ContextItem("artifact-preview", "workspace", preview, priority=80),
]

snapshot = ContextBuilder(budget).build(items)
```

The exact API uses `ContextItem` keyword arguments as defined in Stage 06A; this snippet shows how the subsystems compose conceptually.

---

## 8. Worked research run

After session 3:

```text
Ledger:
  search papers        completed
  extract evidence     completed
  compare methods      pending

Workspace:
  evidence/method-a.md
  evidence/method-b.md

Handoff:
  "Two methods extracted; compare assumptions/performance next."
```

Session 4 loads:

```text
objective
pending compare task
research-review Skill
method-a/method-b relevant sections
```

It does **not** need every search query and failed URL from sessions 1–3.

---

## 9. Garbage collection/retention

Long projects accumulate scratch data.

Define:

```text
what is temporary?
what must survive run completion?
what is user-facing output?
what must be retained for audit?
when can artifacts be deleted?
```

Retention is both cost and privacy policy.

Keeping every intermediate Tool output forever is not automatically "better observability."

---

## Completion principle

> **Use ledgers for exact progress, artifacts for large durable outputs, Skills for reusable procedure, and compact context for the current model decision.**

That separation lets new sessions continue without pretending the model has an infinite autobiographical memory.
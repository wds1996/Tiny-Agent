# 03 — Skill Routing, Activation, and Context Integration

Installing a Skill is easy. Deciding **when to activate it** without loading every Skill into every request is the interesting engineering problem.

```text
installed Skills
   ↓ metadata catalog
candidate Skills
   ↓ task matching/policy
activated Skill(s)
   ↓
ContextBuilder
   ↓
model decision
```

Routing is context selection, not permission assignment.

---

## 1. Start with metadata, not full manuals

`SkillCatalog.metadata_prompt()` provides a compact discovery view:

```python
catalog = SkillCatalog("skills")
metadata = catalog.metadata_prompt()
```

Suppose there are 50 Skills. Startup context might contain only:

```text
- code-review: Review code changes...
- data-analysis: Analyze tabular datasets...
- research-review: Check claims against evidence...
...
```

Loading 50 full procedural manuals would defeat the entire purpose of progressive disclosure.

---

## 2. Routing can be deterministic or semantic

### Deterministic

Useful when the trigger is explicit:

```python
def choose_skill(file_name: str) -> str | None:
    if file_name.endswith(".pdf"):
        return "pdf-processing"
    if file_name.endswith(".csv"):
        return "data-analysis"
    return None
```

### Semantic

Useful when intent is fuzzy:

```text
Task: "Check whether these claims exaggerate the papers"
Candidates:
- research-review
- copy-editing
- citation-formatting
```

A model/router can choose an enum from the application-provided candidate set.

The result is still validated:

```python
selected = decision["skill"]
if selected not in approved_candidate_names:
    raise ValueError("unknown skill selection")
```

---

## 3. Do not ask the model to route across an infinite filesystem

Bad architecture:

```text
"Here are 4,000 SKILL.md files. Read them and choose."
```

Better hierarchy:

```text
catalog metadata
-> category/filter
-> small candidate list
-> semantic choice if needed
-> activate one/few Skills
```

For very large catalogs, metadata itself may need indexing/search.

The principle is recursive: even your progressive-disclosure catalog may eventually require progressive disclosure.

---

## 4. Activate only after selection

```python
skill = catalog.activate("research-review")
```

Now you have:

```text
skill.instructions
skill.references
skill.scripts
skill.assets
```

An activated Skill can become a `ContextItem`:

```python
from tiny_agent import ContextItem

skill_item = ContextItem(
    key="skill:research-review",
    kind="skill",
    content=skill.instructions,
    priority=90,
    provenance="skill:research-review",
    trusted=False,
)
```

Why `trusted=False` by default?

Because a Skill can guide model procedure, but it should not be promoted to immutable control authority—especially when third-party.

---

## 5. Skills compete for context budget too

A Skill body can be large. If three Skills are activated, do not blindly concatenate them.

Possible policies:

```text
one primary Skill + one helper Skill
per-phase Skill activation
Skill instruction compaction
load references only on demand
```

Example research flow:

```text
PLAN
  -> research-planning Skill

EVIDENCE REVIEW
  -> research-review Skill

FINAL FORMAT
  -> report-formatting Skill
```

The writer does not need the planning manual after the plan is fixed.

---

## 6. Skill routing vs Tool routing

These decisions are related but different:

```text
Skill routing
    -> which procedural guidance should the model see?

Tool exposure
    -> which action schemas should the model see?

Tool authorization
    -> which actions may actually execute?
```

A Skill may recommend a Tool set, but the Host still decides what is exposed/authorized.

---

## 7. Skill routing vs sub-Agent delegation

Use a Skill when:

- same runtime/identity should continue;
- you need domain procedure;
- no independent lifecycle/state is required.

Use a sub-Agent when:

- work should have isolated context;
- it has a distinct role/Tool surface;
- independent state/lifecycle is useful;
- parallel/delegated execution is justified.

Bad design:

```text
Need a different checklist
-> spawn another autonomous Agent
```

Sometimes you needed a Skill, not a committee meeting.

---

## 8. Worked example: academic answer review

Input:

```text
"Review this answer and tell me whether every major claim is supported."
```

Pipeline:

```text
1. application exposes metadata for review-related Skills
2. router chooses research-review
3. SkillCatalog.activate("research-review")
4. ContextBuilder includes:
   - task
   - answer under review
   - evidence
   - Skill instructions
5. model produces structured review
6. deterministic evaluator checks citation IDs/known sources
```

The Skill supplies procedure. Evidence supplies facts. Evaluator code supplies deterministic checks.

That separation is the entire point.

---

## 9. Failure case: accidental Skill stacking

Suppose both Skills activate:

```text
legal-contract-review: "Prefer conservative wording"
marketing-copy: "Use bold persuasive claims"
```

If the task is legal review, the second Skill is irrelevant and conflicting.

More Skills do not create more expertise automatically. They can create instruction collision.

Evaluate activation precision:

```text
activation precision = relevant activated Skills / activated Skills
activation recall    = needed Skills activated / needed Skills
```

---

## 10. Observability

Record enough metadata to debug routing:

```text
available Skill metadata/version
candidate Skills
selected Skill(s)
loaded references
context token contribution
routing reason/model version
```

Do not log sensitive Skill/resource contents by default if they contain proprietary procedure or data.

---

## Completion principle

> **Discover cheaply, select narrowly, activate deliberately, load resources lazily, and keep authorization outside Skill routing.**

That makes Skills a scalable context mechanism rather than another giant prompt directory.
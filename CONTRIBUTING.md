# Contributing

> Language: **English** | [简体中文](CONTRIBUTING.zh-CN.md)

Tiny-Agent is a sequential Agent-engineering course, not a collection of independent technical notes. A technically correct contribution can still be a poor course contribution if it appears in the wrong Stage, reads like an API catalog, depends on concepts that have not been taught yet, or duplicates the same implementation in several places.

---

## 1. Write like a teacher, not a glossary

A lesson should usually move through cause and effect: what the previous Stage can already do, what new problem appears, where the obvious solution starts to fail, why a new concept becomes necessary, how a local code snippet exposes the mechanism, how the complete example behaves, and what remaining limitation motivates the next Stage.

Lists and tables are useful for comparison and review. They should not carry the main explanation. Avoid long runs of one-sentence paragraphs and repeated “definition + five bullets” sections.

Humor and analogy are welcome when they improve the mental model. They should never replace the technical explanation.

---

## 2. Stages use continuous integers

The curriculum is numbered:

```text
00
01
02
...
15
```

Do not add `06A`, `09B`, or similar side chapters. If a new topic truly needs a Stage, reconsider the full dependency order and adjust the integer sequence deliberately.

Stage numbers represent learning order.

---

## 3. Teach only what the current Stage has earned

Do not backfill future answers into earlier chapters.

A Stage may end by motivating the next problem, but it should not teach the next Stage in advance. Before rewriting a chapter, re-read the preceding Stages and confirm what the learner already knows, why the new problem follows naturally, and which terms have already been defined.

The course should feel like one long class rather than fifteen unrelated “today we discuss X” posts.

---

## 4. The Stage README is the lesson

The standard structure is:

```text
stages/XX-topic/
├── README.md
├── README.zh-CN.md
└── code/
```

Do not recreate fragmented `theory/`, `exercises/`, or link-index directories.

If one chapter genuinely needs multiple Markdown files, they should read as consecutive parts of one lesson with a direct continuation from one file to the next.

---

## 5. Keep repository-maintenance commentary out of tutorial prose

Tutorials should not contain statements such as:

> “The full code is placed here to avoid README drift.”

> “This refactor removed theory files.”

> “Based on feedback, the chapter was reorganized.”

Those are repository-maintenance concerns. They belong in contribution documentation or commit history, not in the lesson itself.

---

## 6. Complete teaching programs belong in the Stage's `code/`

Do not maintain a second global implementation tree that students must reconcile with chapter examples.

README snippets should show only the mechanism being taught. Show the reducer when discussing state merging, the approval record when discussing HITL, and the budget check when discussing bounded execution. Keep the complete file under `code/`.

---

## 7. Chinese and English should both read naturally

The two language versions must preserve the same technical boundaries but do not need sentence-by-sentence translation.

Established terms such as Tool Call, Runtime, State, Reducer, Context, Memory, MCP, Skill, Trace, and Lease may remain in English where useful. Avoid unnecessary mixed-language noun chains.

---

## 8. Mechanism first, framework second

The preferred sequence is:

```text
concrete problem
    ↓
minimal inspectable mechanism
    ↓
deterministic checks
    ↓
framework / protocol mapping
```

A framework quickstart is not a substitute for explaining the abstraction it implements. Framework APIs change quickly; mechanisms usually live longer.

---

## 9. Do not overclaim teaching implementations

A teaching hash embedding is not a neural semantic embedding. A bounded subprocess wrapper is not a security sandbox. Local idempotency is not distributed exactly-once execution. A cooperative deadline does not forcibly terminate arbitrary code.

Words such as Production, Secure, Durable, Idempotent, and Sandboxed are claims. Use them only for the boundary the code actually establishes and checks.

---

## 10. Keep proposal separate from authority

This invariant appears throughout the curriculum:

```text
Tool Call != execution authority
Route != dispatcher
Plan != executor
Memory Candidate != durable write permission
Retrieved Result != sufficient evidence
Skill declaration != Tool permission
Delegation != authorization
Approval != authorization
```

Model output may propose. Application-owned validation, policy, authorization, and execution still decide.

---

## 11. Prefer deterministic teaching and checks

When the mechanism itself does not require a live model or service, prefer deterministic model doubles, fake provider clients, local data, temporary SQLite databases, temporary directories, and in-process protocol transports.

Use live systems to evaluate integration or model quality, not to prove deterministic runtime invariants.

---

## 12. Every Stage needs executable boundary checks

`code/checks.py` is the preferred name, although earlier well-named check files such as `runtime_checks.py` may remain.

Checks should test invariants, not merely imports. Examples include rejecting invalid arguments before handlers, stopping loops, ensuring rejection causes no side effect, abstaining on missing evidence, preserving required context, blocking path traversal, or reclaiming only expired leases.

The happy path is only the minimum.

---

## 13. Self-review before committing

Teaching continuity: Does the chapter follow naturally from the previous one? Does every new abstraction solve a concrete problem? Are future concepts avoided? Does the ending motivate the next Stage?

Voice: Are there too many one-sentence paragraphs? Is the explanation driven by lists instead of reasoning? Did repository-maintenance commentary leak into the lesson? Are analogies useful rather than decorative?

Technical correctness: Are concept boundaries precise? Does the chapter overclaim security, reliability, or production guarantees? Did model output accidentally gain application authority? Are scopes for retries, memory, context, identity, and durability explicit?

Code: Do snippets match the runnable implementation? Does the Stage code run? Are failure paths checked? Are network or credential requirements explicit?

Repository: Are both language versions updated? Are Markdown fences balanced? Do relative links resolve? Are caches, databases, logs, and build outputs absent?

---

## 14. Running checks

For standard-library Stages:

```bash
python stages/XX-topic/code/demo.py
python stages/XX-topic/code/checks.py
```

For a Stage with dependencies:

```bash
python -m pip install -r stages/XX-topic/code/requirements.txt
python stages/XX-topic/code/demo.py
python stages/XX-topic/code/checks.py
```

A full syntax pass is also useful:

```bash
python -m compileall -q stages
```

Remove generated `__pycache__` and `.pyc` files afterward.

Dependencies belong to the Stage that needs them under `code/requirements.txt`; do not rebuild one global “all Agent libraries” dependency layer at the repository root.

---

## 15. Fast-changing protocols and APIs

MCP, A2A, model-provider SDKs, and similar surfaces change quickly. Verify version-specific claims against current official documentation rather than old tutorials.

Version-sensitive examples should have executable coverage. Do not claim support for an integration that has not actually been verified.

---

## 16. Keep generated files and credentials out of commits

Check for:

```text
__pycache__/
*.pyc
*.db
*.sqlite
*.log
.env
.venv/
build/
dist/
*.egg-info/
```

Never commit real credentials.

---

## 17. Three final reviewer questions

Before accepting a teaching contribution, ask:

> **Why would a first-time learner naturally need this concept here?**

> **After the lesson, can the learner explain both what the mechanism solves and what it does not solve?**

> **If every framework name were hidden, would a clear engineering mechanism still remain?**

If all three answers are clear, the contribution is usually aligned with Tiny-Agent's course standard.

# Contributing to Tiny-Agent

**English** | [简体中文](CONTRIBUTING.zh-CN.md)

Tiny-Agent is both a learning project and an evolving Agent runtime. Contributions should preserve both goals.

## 1. Repository model

Tiny-Agent has two complementary layers:

```text
stages/          stable educational snapshots
src/tiny_agent/  latest evolving integrated runtime
```

A completed learning stage should remain readable even after the main runtime becomes more sophisticated.

The repository also keeps:

```text
tests/           executable specifications for Agent mechanisms
README*.md       public learning entry points
docs/            cross-stage learning maps
```

Repository-maintenance metadata should stay minimal. Do not add unrelated CI, templates, badges, generated files, or tooling that does not directly support the learning project unless the change is explicitly needed.

## 2. Stage directory convention

Use capability-based names, not dates or personal study schedules.

Preferred:

```text
stages/04-agentic-rag/
```

Avoid:

```text
day11/
week2/
my-rag-notes/
```

Whenever applicable, a stage should contain:

```text
stage-name/
├── README.md
├── README.zh-CN.md
├── theory/
├── code/
└── exercises/
```

### `README.md` / `README.zh-CN.md`

Must explain:

- why the stage exists;
- prerequisites;
- learning objectives;
- recommended reading/coding order;
- expected milestone;
- links to all important files in the stage.

### `theory/`

Detailed Markdown explanations should live here.

Prefer several focused chapters over one extremely long catch-all file.

A theory chapter should normally include:

- motivation;
- mental model;
- architecture/flow when relevant;
- common misconceptions;
- engineering implications;
- key takeaways;
- review questions;
- references when external material is used.

### `code/`

Contains stage-specific implementation snapshots.

Educational code should favor clarity over maximum abstraction. If the latest `src/tiny_agent/` implementation has evolved beyond what a beginner needs for the current stage, keep a simpler standalone snapshot under the stage.

Every runnable example should state how to run it.

### `exercises/`

Use this directory for:

- coding exercises;
- debugging tasks;
- design questions;
- interview-style questions;
- extension challenges.

## 3. Theory-only stages

A stage does not need executable code to deserve a directory.

If a capability is primarily conceptual, keep:

```text
stage-name/
├── README.md
├── README.zh-CN.md
└── theory/
```

Do not force meaningless code into a conceptual chapter just to satisfy a template.

## 4. Updating the latest runtime

If a stage introduces a capability that belongs in the reusable Tiny-Agent runtime, update `src/tiny_agent/` as well.

Examples:

```text
Stage snapshot                  Latest runtime
--------------                  --------------
minimal ToolRegistry      ->    src/tiny_agent/tool.py
minimal Agent loop        ->    src/tiny_agent/runtime.py
provider adapter          ->    src/tiny_agent/models/
RAG mechanism             ->    src/tiny_agent/retrieval.py + rag.py
memory/HITL policy        ->    src/tiny_agent/memory_policy.py + approval.py
safety/governance         ->    src/tiny_agent/reliability.py + governance.py
multi-Agent mechanism     ->    src/tiny_agent/multi_agent.py
long-horizon harness      ->    src/tiny_agent/harness.py
```

The stage snapshot should teach the concept. The latest runtime should integrate it cleanly with everything implemented so far.

## 5. Do not hide mechanisms too early

Tiny-Agent intentionally teaches first principles before high-level frameworks.

When introducing a framework such as LangGraph, show:

1. the underlying problem;
2. the handwritten version or earlier Tiny-Agent implementation;
3. what abstraction the framework adds;
4. what complexity or tradeoff the framework introduces.

Avoid educational examples whose entire logic is effectively:

```python
agent = create_agent(...)
agent.run(...)
```

without explaining what happens underneath.

## 6. Keep model and runtime responsibilities separate

A core project principle is:

> LLMs propose actions; runtimes execute and govern actions.

Do not give a model unrestricted authority over local functions, files, shells, databases, credentials, or external side effects.

Execution policy belongs in deterministic runtime code.

## 7. Testing expectations

Treat tests as executable learning material, not only as regression machinery.

Before changing a mechanism, read [tests/README.md](tests/README.md) to understand which tests correspond to which stages.

Prefer deterministic unit tests for runtime behavior.

Use fake/scripted models when testing:

- loop transitions;
- tool execution;
- stopping conditions;
- error handling;
- state updates;
- permission logic.

Use real models only in separate integration/evaluation tests where model quality is actually being measured.

Do not make every unit test depend on network access, API keys, or stochastic model behavior.

If you add a new meaningful `test_*.py` file, update both:

- `tests/README.md`;
- `tests/README.zh-CN.md`.

Explain what the test protects, which Stage it belongs to, and what a failure usually means.

## 8. Bilingual documentation requirements

Tiny-Agent maintains an English and Simplified Chinese learning track.

For learner-facing Markdown:

```text
README.md                 <-> README.zh-CN.md
chapter.md                <-> chapter.zh-CN.md
review-questions.md       <-> review-questions.zh-CN.md
```

When adding or materially changing learner-facing documentation:

1. update both language versions in the same contribution;
2. preserve the same technical meaning, architecture boundaries, warnings, examples, and exercises;
3. do not translate code identifiers, API names, commands, or file paths unless the path itself has a Chinese Markdown counterpart;
4. in Chinese documentation, internal course links should point to `.zh-CN.md` whenever that counterpart exists;
5. keep the explicit language switch pointing to the other language;
6. do not reduce the Chinese version into a summary of a more complete English source.

Translation should be natural rather than literal, but technical correctness has priority over stylistic localization.

## 9. Documentation links

When adding a new important file:

- link it from that stage's `README.md` and `README.zh-CN.md` where applicable;
- update the root README pair if it changes the public learning path;
- keep English pages inside the English learning path and Chinese pages inside the Chinese learning path;
- avoid dead placeholder links.

## 10. Pull requests

Keep pull requests focused on one capability or one coherent maintenance goal.

Good examples:

```text
feat: add provider-neutral OpenAI adapter
feat: introduce planner-executor stage
feat: add tool-call trajectory evaluator
docs: explain MCP trust boundaries
test: cover Agent step-limit behavior
```

A PR should explain:

- what learners gain;
- what runtime behavior changes;
- what files are educational snapshots vs integrated implementation;
- how the change is tested;
- whether both language tracks were updated when documentation changed.

## 11. Writing style

Aim for explanations that are:

- technically precise;
- beginner-readable;
- engineering-oriented;
- explicit about tradeoffs;
- free of unnecessary framework marketing.

Prefer concrete diagrams, small examples, and clear responsibility boundaries.

Humor is welcome when it improves memory or clarity, but it must not distort the technical point.

## 12. Long-term goal

A successful contribution should make it easier for another learner to answer three questions:

1. **How does this Agent capability work?**
2. **Why would a real engineering team design it this way?**
3. **How can I verify that the implementation still preserves those semantics?**

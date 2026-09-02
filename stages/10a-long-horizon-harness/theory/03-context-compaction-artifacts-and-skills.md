# 03 — Context compaction, artifacts, and Skills

Long-horizon harness design combines several earlier Tiny-Agent ideas.

## Context Engineering

Old transcript becomes compact notes/summaries while exact state remains in structured stores/files.

## Workspace

Large code/data/artifacts remain on disk. The Agent reads the relevant file when needed rather than carrying every byte in prompt context.

## Skills

A recurring procedure can be loaded on demand each session:

```text
test-and-fix
research-review
release-checklist
```

This is more reliable than hoping a compressed history preserved a 40-step procedure from three hours ago.

## Artifacts are communication

An artifact is not only final output. Intermediate artifacts can bridge sessions:

```text
analysis.json
plan.md
failing-tests.txt
retrieval-results.json
```

Use structured, inspectable artifacts where later workers need exact facts.

## Do not compact control truth into prose

Keep exact:

```text
run_id
task status
approval grant
idempotency key
resource owner
checkpoint version
```

in structured state. Human-readable summaries are useful context, not a substitute for transaction/state semantics.

# 04 — Skill trust, governance, and evaluation

A Skill is executable-adjacent content. Third-party skills can contain instructions, scripts, links, and templates, so installation is a software supply-chain decision.

## Do not confuse metadata with authorization

The Agent Skills spec currently includes an experimental `allowed-tools` field.

Tiny-Agent exposes it as descriptive metadata only.

```text
SKILL.md says Bash(git:*)
        !=
application grants shell permission
```

Real permission still belongs to Stage 07 governance and Stage 09A sandbox policy.

## Review before installation

For third-party skills inspect:

- provenance/license/version;
- scripts and dependencies;
- network assumptions;
- filesystem writes;
- credential requirements;
- referenced URLs/resources;
- instructions that attempt to expand authority.

## Version skills

A skill is part of Agent behavior. Prompt/procedure changes can cause regressions just like code changes.

Record skill version/hash in traces where practical, and evaluate changes against a task dataset.

## Evaluate a Skill against a baseline

```text
no skill
vs
skill v1
vs
skill v2
```

Measure:

- task success;
- trajectory/tool correctness;
- tokens and latency;
- unsafe-action rate;
- human correction rate.

A 2,000-token skill that does not improve outcomes is not automatically valuable because the Markdown is beautiful.

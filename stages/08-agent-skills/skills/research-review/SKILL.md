---
name: research-review
description: Review an evidence-grounded research draft for unsupported claims, citation misuse, and metadata/full-text confusion. Use after a research answer has been drafted from an evidence inventory.
license: MIT
compatibility: Works with an Agent that can read the draft and evidence inventory.
metadata:
  version: "1.0"
  author: tiny-agent
allowed-tools: Read
---

# Research review procedure

1. List the draft's substantive factual claims.
2. Identify the citation label attached to each claim.
3. Check that every cited label exists in the evidence inventory.
4. Treat bibliographic metadata as support for bibliographic facts only.
5. For scientific/technical findings, require substantive source text.
6. Flag claims whose cited evidence does not actually support the wording.
7. Prefer revision or abstention over inventing missing support.

For a more detailed rubric, read `references/RUBRIC.md` only when a full review is required.

The `allowed-tools` declaration above is descriptive Skill metadata. Application authorization still decides whether any tool can execute.

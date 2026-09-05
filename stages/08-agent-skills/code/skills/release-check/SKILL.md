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

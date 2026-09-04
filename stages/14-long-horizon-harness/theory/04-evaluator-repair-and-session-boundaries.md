# 04 — Evaluators, Repair, Replanning, and Session Boundaries

A long-horizon Agent needs an answer to a simple question:

> How does the system know that progress is real?

"The model says it looks good" is weak evidence.

Use external evaluators/tests wherever possible.

---

## 1. Evaluator feedback closes the loop

```text
worker produces result
        ↓
evaluator/test
        ↓
pass -> complete task
fail -> repair / replan / human
```

Examples:

```text
coding      -> tests/lint/type checks
research    -> citation/evidence checks
ETL         -> schema/row invariants
report      -> required sections/format
security    -> policy checks
```

The evaluator can be deterministic, model-based, human, or layered.

---

## 2. Deterministic checks first

If code can verify it exactly, prefer code.

```python
assert output_file.exists()
assert tests_passed
assert citation_ids <= known_evidence_ids
```

Use semantic judges for questions ordinary code cannot answer reliably:

```text
Does this evidence actually support the claim?
Is the report materially complete?
```

Model judges are evaluators, not execution authority.

---

## 3. Retry vs repair vs replan

These are different responses.

### Retry

Same operation, same basic approach:

```text
HTTP 503 -> bounded retry with backoff
```

### Repair

Output is close but incorrect:

```text
unit test fails -> inspect failure -> patch code
```

### Replan

The approach itself is wrong:

```text
source unavailable / assumption invalid
-> change research strategy/task list
```

Blind retry of a conceptual failure only gives you the same wrong answer with impressive persistence.

---

## 4. Failed tasks need evidence

Record enough failure state:

```text
error category
brief note
artifact/log path
attempt count
relevant evaluator output
```

Do not dump an unbounded stack trace into every future prompt.

The exact log can remain an artifact; the handoff includes the actionable summary.

---

## 5. Session boundary is an architecture tool

Ending a model session is not necessarily failure.

A deliberate session boundary can:

- reset accumulated context noise;
- switch model/Skill role;
- release expensive resources;
- create a clean human-review point;
- checkpoint durable progress.

Long-running work should be designed to survive a new model instance.

If your Agent only works when one chat never ends, your "memory architecture" may be a browser tab.

---

## 6. Handoff should include next-action affordances

Useful summary:

```text
Objective: fix authentication regression
Completed: reproduced bug, identified failing module
Current failure: refresh-token test still fails
Relevant artifacts: logs/test-2.txt, src/auth.py
Next task: inspect token expiry conversion
```

This gives the next worker a bounded starting point.

Avoid narrative like:

```text
We tried many things. Continue investigating.
```

---

## 7. Evaluators can create loops too

Bad:

```text
writer -> critic -> writer -> critic -> ... until perfection
```

Need budgets:

```text
max repair attempts
max model calls
max wall time
max cost
human escalation threshold
```

Stage 09's bounded-loop principles still apply at multi-session scale.

---

## 8. Worked coding repair

```text
task: implement parser
worker writes parser.py
pytest -> 2 failures
```

Harness does not mark completed.

Instead:

```text
record failure artifact
-> create/continue repair task
-> next worker loads failing test + parser + brief handoff
-> patch
-> pytest passes
-> task completed
```

Notice that the full previous coding conversation is irrelevant once exact files/tests exist.

---

## 9. Human review as session boundary

Risky operation:

```text
generated migration ready
```

Harness can persist:

```text
status = waiting_for_human
artifact = migration.sql
```

The worker exits.

Hours later an authenticated reviewer approves/rejects, and a new worker resumes.

This is far more durable than keeping one model call suspended in RAM for an afternoon.

---

## 10. Completion principle

> **Use evaluators to turn progress into evidence, distinguish transient retry from semantic repair/replanning, and treat session boundaries as normal resumable checkpoints rather than catastrophic memory loss.**

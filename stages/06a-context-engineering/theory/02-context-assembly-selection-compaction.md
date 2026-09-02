# 02 — Context assembly, selection, and compaction

A useful context builder works like a compiler pipeline rather than a giant string concatenation.

```text
sources
  -> candidates
  -> classify
  -> prioritize/filter
  -> compact where appropriate
  -> order
  -> render
```

## Required vs optional context

Some information should fail closed if it cannot fit:

- core safety/control instructions;
- the current user task;
- schemas required to interpret the expected response.

Other information can be selected:

- old history;
- low-relevance memories;
- extra evidence candidates;
- optional tools/skills.

`ContextBuilder` admits required items first. If required items exceed the budget, it raises `ContextBudgetError` instead of silently dropping an invariant.

## Priority is not ordering

Selection asks:

> What fits?

Ordering asks:

> In what sequence should the model see it?

Tiny-Agent ranks optional items by priority for admission but restores selected items to original application order before rendering. This prevents a retrieval score from accidentally moving a low-trust evidence block ahead of system/task instructions.

## Compaction is lossy derived state

When history becomes large:

```text
old turns
   -> summary
recent turns remain verbatim
```

But the summary is not the original record.

Tiny-Agent's `compact_items()` returns a `CompactionRecord` containing:

- the source item keys;
- the derived summary item;
- original estimated size;
- estimated savings;
- provenance `derived:compaction`.

This matters because summaries can omit exceptions, caveats, attribution, or uncertainty.

## What should not be compacted casually

Avoid replacing these with vague summaries when exactness matters:

- approval decisions;
- authorization facts;
- structured tool results required for later computation;
- legal/audit records;
- exact source quotations/locators;
- idempotency keys and run/task identifiers.

Context compression is not permission to destroy application truth.

## Evaluate context policies

Compare policies on a fixed dataset:

```text
answer quality
trajectory success
input tokens
latency
cost
retrieval/tool precision
prompt-injection success rate
```

If a 40% smaller context preserves quality and reduces attack surface, that is an engineering win. If aggressive summarization loses critical constraints, it is not.

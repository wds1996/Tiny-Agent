# Stage 14 — Long-Horizon Agent Harnesses

A short Agent loop assumes the task fits inside one process lifetime and a manageable context. Long-horizon work breaks those assumptions.

Hours- or days-long tasks need a harness that can make incremental progress across:

- model context windows;
- process restarts;
- sandbox expiration;
- human pauses;
- transient failures;
- multiple worker sessions.

The central lesson is:

> Long-horizon reliability comes from externalized progress, artifacts, task state, evaluation, and resumable execution — not from asking the model to “remember everything.”

## Learning objectives

After this stage you should be able to:

1. explain why one giant prompt/session is a poor long-horizon architecture;
2. maintain a durable task ledger outside model context;
3. split initializer/planner work from incremental worker sessions;
4. record progress notes and artifacts for the next session;
5. build compact handoff summaries instead of replaying full transcripts;
6. resume with a new runtime object/process;
7. use evaluators/tests as feedback rather than “looks done” model confidence;
8. distinguish retry from repair/replanning;
9. separate durable harness state from disposable sandbox compute;
10. reason about leases, cancellation, side effects, and job ownership.

## Learning order

1. `theory/01-why-long-horizon-agents-fail.md`
2. `theory/02-task-ledgers-and-shift-handoffs.md`
3. `code/long_horizon_demo.py`
4. `code/resume_demo.py`
5. `theory/03-context-compaction-artifacts-and-skills.md`
6. `theory/04-evaluator-repair-and-session-boundaries.md`
7. `theory/05-durable-harness-vs-disposable-compute.md`
8. `src/tiny_agent/harness.py`
9. `src/tiny_agent/jobs.py`
10. `tests/test_harness.py`, `tests/test_jobs.py`
11. `exercises/review-questions.md`

## Current references

- Anthropic, *Effective harnesses for long-running agents* — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic, *Harness design for long-running application development* — https://www.anthropic.com/engineering/harness-design-long-running-apps
- OpenAI, *The next evolution of the Agents SDK* — https://openai.com/index/the-next-evolution-of-the-agents-sdk/
- MCP 2026-07-28 Tasks extension overview — https://blog.modelcontextprotocol.io/posts/2026-07-28/

## Tiny-Agent implementation

`TaskLedger` stores objective, task status, attempts, notes, and artifact paths as a human-readable JSON file under the governed workspace. Writes are atomic file replacements.

`LongHorizonHarness` executes one pending task at a time, persists the transition before and after worker execution, and generates a compact handoff summary for the next worker/session.

`SQLiteRunQueue` from Stage 13 provides a separate service-level durable job/lease example.

## Milestone

Start a multi-task run, complete only one step, destroy the runtime object, construct a new runtime from the same workspace, and continue without replaying hidden model history.

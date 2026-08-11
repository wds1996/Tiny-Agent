# Stage 07 — Reliability, Safety & Tool Governance

## Why this stage exists

Agent demos usually assume tools succeed and the model behaves sensibly. Real systems must survive invalid arguments, network failures, loops, unsafe requests, and permission boundaries.

This stage turns execution control into an explicit runtime policy.

## Planned topics

- typed tool errors;
- retryable vs fatal failures;
- timeout and cancellation;
- retry/backoff;
- fallback tools and models;
- max steps / max tool calls;
- token and cost budgets;
- loop detection;
- tool permissions and allowlists;
- approval policies;
- prompt injection and indirect prompt injection;
- sandboxing concepts;
- audit trails.

## Planned code artifacts

```text
code/
├── error_model.py
├── retry_policy.py
├── execution_budget.py
├── permission_policy.py
├── loop_detection.py
└── guarded_tool_runtime.py
```

## Planned theory

```text
theory/
├── 01-agent-failure-modes.md
├── 02-retry-timeout-fallback.md
├── 03-execution-budgets.md
├── 04-tool-permissions.md
└── 05-prompt-injection-and-sandboxing.md
```

## Milestone

Build a guarded runtime with explicit budgets, typed failures, retry policies, and permission checks so that Agent execution fails predictably rather than silently or catastrophically.

## Key question

> What authority should an LLM have, and what authority must always remain with deterministic runtime policy?

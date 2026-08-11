# Stage 08 — Evaluation & Observability

## Why this stage exists

An Agent that appears to work in a demo is not automatically reliable. Production teams need to understand what happened during execution and measure whether changes make the system better or worse.

This stage introduces traces, metrics, regression datasets, and Agent-specific evaluation.

## Planned topics

- traces and spans;
- model and tool events;
- execution trajectories;
- task-success evaluation;
- tool-selection accuracy;
- argument accuracy;
- retrieval metrics;
- trajectory evaluation;
- latency, token, and cost metrics;
- offline vs online evaluation;
- deterministic graders;
- LLM-as-judge;
- regression evaluation sets;
- debugging from traces.

## Planned code artifacts

```text
code/
├── trace_model.py
├── local_tracer.py
├── eval_dataset.py
├── tool_call_evaluator.py
├── trajectory_evaluator.py
└── end_to_end_eval.py
```

## Planned theory

```text
theory/
├── 01-why-agent-evaluation-is-hard.md
├── 02-tracing-and-observability.md
├── 03-tool-and-trajectory-evals.md
├── 04-offline-online-evaluation.md
└── 05-cost-latency-quality.md
```

## Milestone

Create a reproducible evaluation suite and inspectable trace for Tiny-Agent so that changes can be tested against task success, tool behavior, trajectory quality, latency, and cost.

## Key question

> If an Agent gives the correct final answer through a wasteful or unsafe trajectory, should we consider the execution successful?

# Stage 06 — Memory, Persistence & Human-in-the-Loop

## Why this stage exists

A useful Agent must often carry state across steps, survive interruptions, remember selected information across sessions, and pause before risky operations. These are runtime capabilities, not properties we should assume the LLM magically provides.

## Planned topics

- context vs state vs memory;
- short-term/session memory;
- long-term memory;
- checkpointing;
- persistence;
- resume and replay;
- memory retrieval and write policies;
- human approval gates;
- approve / edit / reject flows;
- high-risk tool execution.

## Planned code artifacts

```text
code/
├── session_state.py
├── checkpoint_store.py
├── long_term_memory.py
├── human_approval.py
└── resumable_agent.py
```

## Planned theory

```text
theory/
├── 01-context-state-memory.md
├── 02-short-vs-long-term-memory.md
├── 03-checkpoint-and-resume.md
└── 04-human-in-the-loop.md
```

## Milestone

Build an Agent that can persist execution state, resume after interruption, retrieve selected long-term memory, and stop for human approval before a risky tool call.

## Key question

> What information should be stored, for how long, and who should be allowed to authorize side effects?

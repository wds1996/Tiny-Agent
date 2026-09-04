# 04 — LangGraph Implementation: Same Domain, Different Orchestration

The framework version should answer a precise question:

> What does LangGraph buy us once the application semantics are already correct?

It should **not** quietly redefine evidence, memory, permissions, or evaluation.

## Shared domain layer

Both implementations reuse:

```text
ResearchRequest / ResearchReport
LocalResearchCorpus
CrossrefScholarlySearch
ResearchReviewTeam
ResearchMemoryStore
MarkdownReportExporter
evaluate_research_report
```

The graph version adds orchestration primitives:

```text
StateGraph
TypedDict state
nodes
conditional edges
checkpointer
interrupt
Command(resume=...)
```

## Graph structure

```text
START
  |
load_memory
  |
plan
  |
retrieve
  |
  +-----------------------+
  |                       |
insufficient             draft
  |                       |
  |                     review
  |                       |
  +----------+------------+
             |
          remember
             |
       export requested?
        /            \
      no             yes
      |                |
  finalize      approval_export
                      |
                  finalize
                      |
                     END
```

The graph makes branch structure explicit. This becomes useful once workflows contain resumable human boundaries and more than a few nontrivial transitions.

## State is serializable application data

The graph state stores values such as:

```python
class OpenScholarGraphState(TypedDict, total=False):
    run_id: str
    question: str
    user_id: str
    thread_id: str
    plan: dict[str, Any]
    evidence: list[dict[str, Any]]
    answer: str
    warnings: list[str]
    metrics: dict[str, int]
    status: str
```

Notice what is **not** placed into graph state:

- database connections;
- model clients;
- file handles;
- authorization objects;
- Python coroutine objects.

Those are runtime dependencies owned by the application instance, not durable state.

## Why evidence is converted to dictionaries

`Evidence` is a domain dataclass. Checkpointed graph state should remain simple and portable, so graph nodes convert evidence to plain dictionaries and reconstruct domain objects only when needed.

This creates a clean serialization boundary:

```text
Domain object
  -> graph-safe representation
  -> checkpoint
  -> domain object
```

## Checkpointer vs long-term memory

These remain different even when both are persisted in a database:

```text
Checkpointer
  -> where this graph execution paused
  -> thread-scoped

ResearchMemoryStore
  -> explicit cross-run user preference
  -> user-scoped
```

A framework checkpoint should not automatically become a user's permanent semantic memory.

## The HITL node

The export node is intentionally ordered like this:

```python
approval = ApprovalRequest(...)

decision_payload = interrupt(
    approval.to_interrupt_payload()
)

decision = ApprovalDecision.from_payload(
    decision_payload
)

# side effect only after resume
exporter.export(...)
```

Why?

A LangGraph node containing `interrupt()` can be re-executed from its beginning when resumed. If the file write happened before the interrupt, resume could repeat the side effect.

Bad:

```python
exporter.export(report, path)
decision = interrupt(...)
```

That is not human approval. That is “please approve the thing I already did, potentially twice.”

## Resume

The caller uses the same `thread_id`:

```python
report = await agent.resume(
    thread_id="research-42",
    decision=ApprovalDecision(
        outcome="approve"
    ),
)
```

Internally:

```python
Command(resume=payload)
```

continues from the checkpointed interrupt boundary.

## Why the graph does not own permissions

A node named `approval_export` is not an authorization mechanism.

The actual exporter still enforces:

- relative path only;
- `.md` suffix;
- resolved target stays inside the configured export root;
- exclusive creation to avoid accidental overwrite.

Framework routing says **when** code executes. Application policy says **whether** the side effect is valid.

## Base vs graph version

The graph version is not automatically superior.

Use the base version when:

- branching is simple;
- process-local execution is enough;
- you want minimal dependencies;
- ordinary code remains readable.

The graph becomes attractive when:

- human pauses must survive process restarts;
- state transitions need inspection;
- workflows branch and rejoin frequently;
- checkpoint/resume is a core requirement;
- graph streaming/debugging adds real value.

A useful rule:

> If you cannot explain the state machine without LangGraph, adding LangGraph will not make the state machine correct. It will only make the confusion serializable.
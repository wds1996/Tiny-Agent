# Advanced — Tool / Agent-Computer Interface Design

Function Calling quality depends heavily on the interface the model sees.

A runtime can be perfectly implemented and still fail because its tools are ambiguous, overlapping, too broad, or return unusable observations.

## Design dimensions

### Names

Prefer stable, specific verbs/nouns:

```text
search_papers
read_document_chunk
create_report_draft
```

Avoid opaque names such as `do_task_2`.

### Descriptions

Explain:

- what the tool does;
- when it should be used;
- important limits;
- what it does **not** do.

Tool selection is partly a language-understanding problem.

### Schemas

Use constrained enums/ranges/required fields where the application already knows the valid domain. Do not ask the model to encode policy through free-form strings.

### Granularity

Too narrow:

```text
one Tool per tiny implementation detail
```

creates long Tool chains.

Too broad:

```text
shell(command)
http(method, url, headers, body)
```

greatly expands authority and ambiguity.

Prefer task-relevant capabilities with minimum required privilege.

### Outputs

Tool output becomes future model context. Return structured, bounded, provenance-rich observations rather than 5 MB of logs.

## Dynamic exposure

Large systems may own hundreds of tools. Context engineering can expose only the subset relevant to the current task/domain.

Remember:

```text
visible to model != authorized to execute
```

The runtime must still validate permission after a ToolCall is proposed.

## Evaluate the interface

Build a dataset of tasks and measure:

- correct Tool selection;
- argument accuracy;
- unnecessary calls;
- recovery after errors;
- output token/context cost.

Tool design is an Agent-computer interface problem, not only a Python function-wrapping problem.

Reference: https://www.anthropic.com/engineering/writing-tools-for-agents

# Stage 07: Do Not Move the Warehouse onto the Desk — Context Engineering

> Language: **English** | [简体中文](README.zh-CN.md)

Stage 06 taught the Agent to retain things. Checkpoints can preserve execution, long-term memory can retain selected preferences, RAG can supply evidence, and MCP can return remote context and Tool results.

Now we have a new problem: there is too much useful information.

```text
instructions
conversation history
checkpoint state
long-term memory
RAG evidence
Tool observations
MCP resources
current user input
...
```

The tempting solution is to send all of it to the model every time.

That confuses storage with attention.

Stage 07 asks one question:

> **What should the model see on this turn?**

Context Engineering is the discipline of selecting, organizing, compacting, and labeling the information used for a model call.

---

## 1. Context and memory are different

Memory asks what should be retained.

Context asks what should be visible now.

A stored preference such as “answer in Chinese” may be useful on one turn and irrelevant on another. A checkpoint may contain retry counters and internal phase data that the runtime needs but the model does not.

Keep the layers separate:

```text
State
    -> what execution needs

Memory / Persistence
    -> what survives over time

Context
    -> what this model call sees
```

---

## 2. A context window is a desk, not a warehouse

More input is not automatically better.

It costs tokens and latency, but more importantly it creates more competition and more opportunities for stale or conflicting information to influence the model.

A refund question may need:

```text
current question
order facts
current refund policy
```

It probably does not need last year's hotel preference, eighty old conversation turns, or an obsolete policy version.

The objective is not “fill the window.” It is “spend the attention budget on information that matters to this decision.”

---

## 3. Make the budget explicit

The teaching code models:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContextBudget:
    max_input_tokens: int
    reserved_output_tokens: int = 0

    @property
    def usable_input_tokens(self) -> int:
        usable = self.max_input_tokens - self.reserved_output_tokens
        if usable <= 0:
            raise ValueError("reserved_output_tokens leaves no input budget")
        return usable
```

Reserving output space prevents the input from consuming the whole allowance.
For example, `max_input_tokens=105` with `reserved_output_tokens=30` leaves
the selector only 75 estimated input tokens.

The local examples use a deliberately rough estimate:

```python
max(1, (len(content) + 3) // 4)
```

It is useful for deterministic teaching, not for exact provider billing. Real hard limits should use the relevant tokenizer or provider usage data.

---

## 4. Context items need metadata

Anonymous strings make selection nearly impossible to reason about.

The chapter uses:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContextItem:
    key: str
    content: str
    kind: str
    priority: int
    required: bool = False
    provenance: str = "application"

    @property
    def estimated_tokens(self) -> int:
        return max(1, (len(self.content) + 3) // 4)
```

Now the system can distinguish instructions from evidence, memory from history, required context from optional context, and one source from another.

`key` identifies one candidate and must be unique. `kind` describes its role,
while `provenance` records where it came from. Larger `priority` wins only among
optional items; it does not grant trust or authority. `required=True` means the
call must fail rather than silently omit that item.

Context assembly becomes a data-selection problem instead of a string-concatenation trick.

---

## 5. Required context should fail closed

Some information is foundational to a call: system constraints and the current user request are common examples.

They are marked:

```python
ContextItem(
    key="instructions",
    content="Answer only from supplied evidence.",
    kind="instructions",
    priority=100,
    required=True,
)
```

The builder first checks whether required items fit. If not, it raises `ContextOverflowError`.

Silently deleting something declared required would make the declaration meaningless.

---

## 6. Optional context competes by priority

After required items are placed, optional items use the remaining budget.

The teaching rule is intentionally simple:

```python
sorted(optional, key=lambda item: (-item.priority, item.key))
```

A production selector may combine relevance, recency, task phase, trust class, source type, and cost. The important lesson is that optional context needs an explicit selection policy.

Here is the complete teaching selector from `context.py`. It first reserves all
required items, then spends the remaining budget on optional candidates in a
deterministic order, and finally records what did not fit:

```python
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ContextSelection:
    items: tuple[ContextItem, ...]
    used_tokens: int
    omitted_keys: tuple[str, ...]


class ContextOverflowError(RuntimeError):
    pass


class ContextBuilder:
    def build(
        self,
        items: Iterable[ContextItem],
        budget: ContextBudget,
    ) -> ContextSelection:
        candidates = list(items)
        if len({item.key for item in candidates}) != len(candidates):
            raise ValueError("context item keys must be unique")

        limit = budget.usable_input_tokens
        required = [item for item in candidates if item.required]
        optional = [item for item in candidates if not item.required]
        required_cost = sum(item.estimated_tokens for item in required)
        if required_cost > limit:
            raise ContextOverflowError(
                f"required context needs {required_cost} tokens, budget is {limit}"
            )

        selected = list(required)
        used = required_cost
        for item in sorted(optional, key=lambda item: (-item.priority, item.key)):
            if used + item.estimated_tokens <= limit:
                selected.append(item)
                used += item.estimated_tokens

        selected_keys = {item.key for item in selected}
        omitted = tuple(item.key for item in candidates if item.key not in selected_keys)
        return ContextSelection(tuple(selected), used, omitted)
```

`ContextSelection` is the return record: `items` is what will be rendered,
`used_tokens` is the estimate spent, and `omitted_keys` identifies candidates
that lost the budget decision. `ContextOverflowError` is the explicit failure
used when the required set cannot fit.

---

## 7. Relevance is not authority

High priority means useful for the current task. It does not mean trusted.

Retrieved evidence, Tool results, user text, and remote MCP content can all be highly relevant while still being external data.

The `provenance` field preserves where an item came from, and rendered context keeps source and kind labels instead of flattening everything into one anonymous block.

The renderer keeps those labels in the text handed to the model:

```python
def render_context(selection: ContextSelection) -> str:
    blocks = []
    for item in selection.items:
        blocks.append(
            f"<context kind={item.kind!r} source={item.provenance!r} key={item.key!r}>\n"
            f"{item.content}\n"
            "</context>"
        )
    return "\n\n".join(blocks)
```

This is not a complete prompt-injection defense. It is the prerequisite for having a trust boundary at all.

---

## 8. Conversation history eventually needs compaction

The naive chat pattern is:

```python
messages.append(new_message)
send_everything(messages)
```

It works until history becomes long, repetitive, stale, and contradictory.

A common strategy keeps recent turns and compacts older ones.

The chapter's teaching compactor records both a summary and the message IDs that produced it. The complete function makes the loss explicit: it keeps only a
short normalized prefix of each older message, while recent messages stay
outside the summary.

```python
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    role: str
    text: str


@dataclass(frozen=True, slots=True)
class CompactedHistory:
    summary: str
    source_message_ids: tuple[str, ...]


def split_history(
    messages: Sequence[Message], *, keep_last: int = 2
) -> tuple[list[Message], list[Message]]:
    if keep_last < 0:
        raise ValueError("keep_last must be >= 0")
    if keep_last == 0:
        return list(messages), []
    if len(messages) <= keep_last:
        return [], list(messages)
    return list(messages[:-keep_last]), list(messages[-keep_last:])


def render_messages(messages: Sequence[Message]) -> str:
    return "\n".join(f"{message.role}: {message.text}" for message in messages)


def compact_history(
    messages: Sequence[Message], *, keep_last: int = 2
) -> CompactedHistory:
    older, _recent = split_history(messages, keep_last=keep_last)
    if not older:
        return CompactedHistory("", ())

    facts = []
    for message in older:
        normalized = " ".join(message.text.split())
        if normalized:
            facts.append(f"{message.role}: {normalized[:120]}")
    return CompactedHistory(
        summary=" | ".join(facts),
        source_message_ids=tuple(message.id for message in older),
    )
```

The IDs matter because a summary is lossy.

---

## 9. A summary is not a checkpoint or source of truth

Compaction transforms:

```text
raw history
    ↓
summary
```

That is useful for attention management, but a summary may omit nuance or make mistakes.

Therefore:

```text
compacted context != checkpoint
compacted context != original evidence
```

Provenance makes it possible to trace a summary back to its source material.

---

## 10. Compaction does not make content mandatory

A compact summary still has to compete for context.

The flow is:

```text
retained history
    ↓
optional compaction
    ↓
candidate ContextItem
    ↓
selection
    ↓
model context
```

Compression solves size. Selection solves relevance.

---

## 11. RAG, memory, and Tool results are context sources

Stage 04 produced evidence candidates. Stage 06 produced retained memories. Tool and MCP calls produce observations.

Stage 07 brings them to one selection boundary:

```text
RAG evidence ----\
memory -----------+--> Context Builder --> Model
Tool results -----/
```

Not every stored memory belongs in every prompt. Not every retrieved document belongs in every model turn.

---

## 12. Prefer just-in-time context when possible

Many facts are needed only after the task reaches a certain phase.

Load order details when an order is actually referenced. Retrieve policy when policy is needed. Fetch a remote resource when the decision requires it.

Just-in-time loading saves tokens and reduces unnecessary exposure of data.

It connects naturally to the routing and Agentic Retrieval ideas from earlier stages.

---

## 13. Tool schemas also consume context

A model offered one hundred Tools has to read one hundred names, descriptions, and parameter schemas.

Capability count is not free.

Large Tool catalogs increase context cost and selection ambiguity. Routing, namespacing, and capability scoping therefore belong to Context Engineering too.

Anything the model must read competes for attention.

---

## 14. A complete assembly pass

The demo keeps the two most recent messages verbatim and creates the following
Context items:

```text
instructions
current question
recent history
retrieved policy
user memory
history summary
```

It builds those candidates explicitly, so the metadata and selection decision
can be inspected together:

```python
history = [
    Message("m1", "user", "I am planning a refund for order ORDER-42."),
    Message("m2", "assistant", "I will check the policy before proposing an action."),
    Message("m3", "tool", "Policy: refunds within 30 days use the original payment method."),
    Message("m4", "user", "The order is 12 days old."),
]
_older_history, recent_history = split_history(history, keep_last=2)
compacted = compact_history(history, keep_last=2)

items = [
    ContextItem(
        key="instructions",
        content="Answer from supplied evidence. Do not invent missing policy.",
        kind="instructions",
        priority=100,
        required=True,
    ),
    ContextItem(
        key="current-question",
        content="Can ORDER-42 be refunded to the original payment method?",
        kind="user",
        priority=100,
        required=True,
    ),
    ContextItem(
        key="recent-history",
        content=render_messages(recent_history),
        kind="recent-history",
        priority=100,
        required=True,
        provenance="conversation:m3,m4",
    ),
    ContextItem(
        key="retrieved-policy",
        content="Refunds within 30 days use the original payment method.",
        kind="evidence",
        priority=90,
        provenance="policy-handbook",
    ),
    ContextItem(
        key="memory",
        content="User prefers concise Chinese answers.",
        kind="memory",
        priority=30,
        provenance="user-memory",
    ),
    ContextItem(
        key="old-summary",
        content=compacted.summary,
        kind="history-summary",
        priority=40,
        provenance="compactor",
    ),
]

selection = ContextBuilder().build(
    items,
    ContextBudget(
        max_input_tokens=105,
        reserved_output_tokens=30,
    ),
)
```

A short piece of code turns “what should the model see?” into an observable policy decision.

Run this assembly immediately after reading it:

```bash
python stages/07-context-engineering/code/demo.py
```

The output prints the token estimate, omitted keys, and the fully labeled
context. The example is offline, so the context-selection policy can be tested
without a model key.

With this budget, the required instruction, question, and recent raw history
fit first. The policy evidence then fits, while `memory` and the older-history
summary are reported as omitted. The old summary remains a candidate rather
than disappearing; a larger budget or a different task can select it later.

### 14.1 Use DeepSeek for semantic compaction and relevance suggestions

The offline example makes the selection rule predictable. In a real task, a
model is better suited to two semantic jobs: compressing older conversation
turns into a task-focused summary, and judging which optional sources are most
useful for the current question.

[`code/deepseek_context.py`](code/deepseek_context.py) sends the older history,
the current question, and the known optional candidates to DeepSeek. It asks
for one JSON proposal shaped like this:

```json
{
  "history_summary": "The user is preparing a refund for ORDER-42.",
  "priority_suggestions": [
    {
      "key": "retrieved-policy",
      "priority": 90,
      "reason": "It directly answers the refund-method question."
    },
    {
      "key": "memory",
      "priority": 20,
      "reason": "It affects response style, not refund eligibility."
    },
    {
      "key": "old-summary",
      "priority": 40,
      "reason": "It carries earlier task context."
    }
  ]
}
```

The model is not allowed to decide what is required, invent a candidate, alter
its provenance, or exceed the budget. The application itself attaches the source
message IDs because it already knows which messages it supplied for compaction.
It checks that every optional key is known and every priority is an integer from
0 through 100, replaces only the optional priorities, and then calls the same
`ContextBuilder` as the offline demo:

```text
older history + optional candidates
              ↓
       DeepSeek JSON proposal
              ↓ validate keys and scores; attach source IDs
application-owned required items + validated optional items
              ↓
    ContextBuilder applies the budget
              ↓
      rendered context for a later model turn
```

This keeps semantic judgement with the model while preserving the boundary
rules established in Stages 00, 04, and 06: a model proposal becomes data that
the application validates and applies deliberately.

The two most recent history messages do not enter that compaction request.
They are rendered verbatim as a Required `recent-history` item, so the current
tool observation and latest user detail are not lost while older turns are
being summarized.

This is a real API integration, but it intentionally sends only a small,
already-prepared candidate set. In a production system, first use deterministic
filters or retrieval to reduce a large history and document store; then ask a
model to summarize or rank that bounded set. Persist the resulting summary with
its application-owned source IDs, measure real provider token usage, and do not
log full prompts or model responses containing sensitive data. The example sets
a request timeout, retries transient failures twice, limits JSON output to 1024
tokens, and rejects any response whose finish reason is not `stop`.

A model's relevance score is still not a trust decision. Apply model ranking
only after application policy has separated candidate sources into the trust
classes that may compete with one another; untrusted retrieved text must never
promote itself into an instruction or privileged source through a high score.

---

## 15. Record omissions

The result exposes these concrete values:

```python
print([item.key for item in selection.items])
print(selection.used_tokens)
print(selection.omitted_keys)
```

Omission data matters during debugging and evaluation.

If the model misses a policy fact, it is valuable to know whether retrieval failed, selection dropped the evidence, or the model ignored evidence that was present.

Stage 10 will turn these decisions into trace and evaluation signals.

---

## 16. Smaller is not automatically better

Context Engineering is not a token-minimization contest.

Removing necessary evidence can make the answer worse. The goal is context that is sufficient, relevant, bounded, and clearly sourced.

---

## 17. Context Engineering is broader than Prompt Engineering

Prompt Engineering often focuses on how instructions are phrased.

Context Engineering also asks:

```text
what enters the model
when it enters
where it came from
what is omitted
what is compacted
```

Conversation, memory, evidence, Tool schemas, Tool results, and task data all belong to that larger problem.

---

## 18. Run the chapter

```bash
python stages/07-context-engineering/code/demo.py
python stages/07-context-engineering/code/checks.py
```

The checks cover required-context survival, fail-closed overflow, deterministic priority, output reservation, duplicate keys, compaction provenance, retention of recent raw history, and the lossy nature of summaries.

The two commands above are offline and need no extra dependency. To run the
real DeepSeek compaction-and-priority example, install the Stage 07 dependency
and set the same two environment variables used in earlier DeepSeek stages.

Windows Command Prompt:

```bash
python -m pip install -r stages/07-context-engineering/code/requirements.txt
set "DEEPSEEK_API_KEY=your_key_here"
set "DEEPSEEK_MODEL=your_available_model_id"
python stages/07-context-engineering/code/deepseek_context.py --show-model-conversation --show-rendered-context
```

PowerShell:

```powershell
python -m pip install -r stages/07-context-engineering/code/requirements.txt
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="your_available_model_id"
python stages/07-context-engineering/code/deepseek_context.py --show-model-conversation --show-rendered-context
```

The two `--show-*` options print the reconstructed model conversation and final
Context, so use them only with the non-sensitive teaching data. Without those
options, the program prints only the validated priority suggestions, source IDs,
selected keys, and omitted keys. Model wording and priority values can vary; the
application's budget and Required Item rules do not.

---

## 19. Why Skills come next

After this chapter, the Agent can choose what context to load.

But reusable procedures create another problem. Code review, release checks, migrations, and incident response may each require substantial instructions. Keeping every procedure permanently in the system prompt recreates context bloat.

The next question is:

> **Can the Agent first discover that a procedure exists, then load its detailed instructions only when needed?**

That is progressive disclosure, and it leads directly to
[Stage 08: Agent Skills](../08-agent-skills/README.md).

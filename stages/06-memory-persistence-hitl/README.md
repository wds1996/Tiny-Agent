# Stage 06: Save Before You Leave — Memory, Checkpoints, and Human-in-the-Loop

> Language: **English** | [简体中文](README.zh-CN.md)

By the end of Stage 05, our Agent can do quite a lot. It can run a Tool loop, follow workflows and graphs, retrieve evidence, and connect to external capabilities through MCP.

The next problem is less glamorous and much more operational:

> **What happens when the process disappears?**

Imagine an Agent preparing a refund. It has checked the order, calculated the amount, and paused because moving money requires human review. The reviewer returns twenty minutes later and clicks Approve. Unfortunately, the original Python process disappeared during a deployment.

If the system responds with “that approval belonged to the previous process,” we do not yet have a durable Agent system.

Stage 06 separates five ideas that are often thrown into one bucket: **State, Checkpoint, short-term memory, long-term memory, and Human-in-the-Loop**. The goal is not to memorize database products. The goal is to understand what must survive so execution can continue, what is worth retaining across conversations, and where a program must deliberately give control back to a person.

---

## 1. State is not durable just because it is explicit

Stage 03 taught us to make execution State visible:

```python
state = {
    "order_id": "ORDER-42",
    "amount": "18.50",
    "phase": "waiting_approval",
}
```

That is already a major improvement over hidden local variables. But explicit memory is still memory. A process restart can erase it.

A checkpoint is a persisted execution snapshot:

```text
runtime state
    ↓ persist
checkpoint
```

Its primary question is not “what does the user prefer?” It is “what must a future runtime know to continue this run?”

That gives us a useful first separation:

| Concept | Main question |
|---|---|
| State | What does the current execution need now? |
| Checkpoint | How does that execution snapshot survive process loss? |
| Short-term memory | What should survive inside one thread? |
| Long-term memory | What selected information should survive across threads? |
| RAG knowledge | What external evidence can be retrieved from a corpus? |

The same database may store several of these. Storage technology does not make their semantics identical.

---

## 2. Scope your IDs before choosing your database

A single user may have multiple threads, and one thread may contain multiple runs:

```text
User
├── Thread A
│   ├── Run 1
│   └── Run 2
└── Thread B
    └── Run 3
```

`user_id` owns durable user information. `thread_id` identifies a continuing conversation or task context. `run_id` identifies one concrete execution.

Confusing these scopes creates subtle bugs. Treating a thread as a user loses cross-thread memory. Treating a user as a thread allows unrelated execution state to bleed together.

Durability starts with a data model, not with a vendor logo.

The teaching workflow deliberately persists only `run_id`. That keeps the
example focused on checkpoint and recovery mechanics. In a product, the
checkpoint record would also relate its `run_id` to the relevant `thread_id`
and authenticated `user_id`; do not treat this small schema as a complete
multi-user data model.

---

## 3. A checkpoint stores what is necessary to continue

### Why this example uses SQLite

SQLite is an embedded relational database. Its data lives in a local file such
as `agent.db`; unlike a client-server database, it does not require us to run a
separate database service for this teaching example. Python ships the
[`sqlite3`](https://docs.python.org/3/library/sqlite3.html) module in its
standard library, so this Stage has no package to install.

You only need four SQLite ideas here:

| Term | Meaning in this chapter |
|---|---|
| database file | The durable file such as `agent.db`. A new Python process can open the same file. |
| table | A named collection of records, such as `checkpoints`. |
| row | One saved record, identified here by `run_id`. |
| transaction | The `with conn:` block commits a successful write or rolls it back if an exception escapes. |

SQLite is a small, local starting point, not the only production choice. See the
[SQLite documentation](https://www.sqlite.org/docs.html) for SQLite itself and
the [Python `sqlite3` documentation](https://docs.python.org/3/library/sqlite3.html)
for the API used below.

The checkpoint state says exactly what a later runtime must recover:

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkflowState:
    run_id: str
    phase: str
    action: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
```

The store opens the file and creates the table once. `run_id TEXT PRIMARY KEY`
means that one run has at most one current checkpoint row:

```python
from contextlib import contextmanager
from pathlib import Path
import sqlite3


class SQLiteCheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._init_db()

    @contextmanager
    def _session(self):
        conn = sqlite3.connect(self.path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._session() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    run_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL
                )
                """
            )
```

Saving and loading then use that same session:

```python
from dataclasses import asdict
import json


def save(self, state: WorkflowState) -> None:
    payload = json.dumps(asdict(state), ensure_ascii=False, sort_keys=True)
    with self._session() as conn:
        conn.execute(
            """
            INSERT INTO checkpoints(run_id, state_json)
            VALUES (?, ?)
            ON CONFLICT(run_id) DO UPDATE SET state_json=excluded.state_json
            """,
            (state.run_id, payload),
        )


def load(self, run_id: str) -> WorkflowState:
    with self._session() as conn:
        row = conn.execute(
            "SELECT state_json FROM checkpoints WHERE run_id=?",
            (run_id,),
        ).fetchone()
    if row is None:
        raise KeyError(f"unknown run_id: {run_id}")
    return WorkflowState(**json.loads(row[0]))
```

The `?` placeholders pass values separately from SQL text, rather than building
SQL with string interpolation. `ON CONFLICT ... DO UPDATE` means that a later
save for the same `run_id` replaces its old snapshot.

Continuation no longer depends on the original Python object. A new runtime can
open the same store, load the same `run_id`, and recover the phase and
arguments. That is the first layer of durable execution.

---

## 4. Durable recovery is not exactly-once side effects

This distinction matters.

Consider:

```text
1. payment service accepts refund
2. local process crashes
3. completed checkpoint was never saved
4. runtime recovers old checkpoint
5. refund is attempted again
```

The checkpoint tells us where local execution believed it was. It cannot automatically roll back or deduplicate an external financial system.

The teaching code uses an idempotency key:

```python
idempotency_key = f"{run_id}:issue_refund"
```

and a local unique table to demonstrate one defense. The complete teaching
operation first returns an already recorded result and otherwise records the
new one:

```python
def record_effect_once(
    self,
    idempotency_key: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
    with self._session() as conn:
        existing = conn.execute(
            "SELECT result_json FROM effects WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if existing is not None:
            return json.loads(existing[0])
        conn.execute(
            "INSERT INTO effects(idempotency_key, result_json) VALUES (?, ?)",
            (idempotency_key, encoded),
        )
    return result
```

This demo records a simulated refund result; it does not call a payment service.
It demonstrates the shape of an idempotency boundary, not a distributed
transaction. Two independent workers can also race between the `SELECT` and
`INSERT`, so production code needs an atomic claim, a handled uniqueness race,
or—preferably—an external API with its own idempotency contract, unique business
key, or compensation design.

Solving recovery does not solve distributed consistency by accident.

---

## 5. Long-term memory answers a different question

A checkpoint preserves progress. Long-term memory preserves selected information across conversations.

Examples include:

> “Use Chinese by default.”
>
> “Keep explanations concise.”
>
> “Remember my preferred city.”

These are not steps of one workflow.

So the architecture splits:

```text
execution continuity
    -> checkpoint

cross-thread retained information
    -> long-term memory
```

The hard part is not writing JSON. It is deciding what deserves durable retention, who owns it, and whether storing it is allowed.

---

## 6. A model proposes a Memory Candidate; policy authorizes the write

The chapter defines the allowed categories and the candidate proposed by the
model:

```python
from dataclasses import dataclass
from typing import Any, Literal


MemoryKind = Literal["semantic", "episodic", "procedural"]


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    owner_id: str
    key: str
    value: dict[str, Any]
    kind: MemoryKind
    explicit_user_request: bool
    sensitive: bool = False
```

The word *Candidate* is intentional.

A model may extract a useful preference, but the application still evaluates it:

```python
decision = policy.evaluate(candidate)

if decision.store:
    store.put(candidate)
```

The teaching policy rejects sensitive data, incidental facts without an explicit memory request, and procedural self-rewrites that would change how the Agent behaves.

Its decision is ordinary application code, not a model judgment:

```python
@dataclass(frozen=True, slots=True)
class MemoryDecision:
    store: bool
    reason: str


class ConservativeMemoryWritePolicy:
    def evaluate(self, candidate: MemoryCandidate) -> MemoryDecision:
        if candidate.sensitive:
            return MemoryDecision(False, "sensitive data is not stored")
        if candidate.kind == "procedural":
            return MemoryDecision(False, "procedural memory needs stronger governance")
        if not candidate.explicit_user_request:
            return MemoryDecision(False, "an incidental fact is not durable memory")
        if not candidate.owner_id.strip() or not candidate.key.strip():
            return MemoryDecision(False, "owner_id and key are required")
        return MemoryDecision(True, "explicit non-sensitive memory is allowed")
```

Different products will use different policies. The invariant is more important:

```text
model proposal != durable write authority
```

This is the same boundary we have used for Tool Calls since Stage 00.

---

## 7. Semantic, episodic, and procedural memory carry different risk

Semantic memory stores relatively stable facts or preferences.

Episodic memory stores events or prior experiences.

Procedural memory can alter how a system behaves.

A wrong preference is inconvenient. A wrong remembered rule such as “refunds no longer require review” changes authority. That is why procedural memory deserves stronger governance than an ordinary user preference.

Do not reduce the memory problem to “which vector database should I use?” First ask what kind of information is being retained and what it can change.

---

## 8. Long-term memory needs an owner boundary

The teaching store keys memory by both owner and key. The complete table shape
makes the ownership boundary visible:

```python
CREATE TABLE IF NOT EXISTS memories (
    owner_id TEXT NOT NULL,
    key TEXT NOT NULL,
    kind TEXT NOT NULL,
    value_json TEXT NOT NULL,
    PRIMARY KEY (owner_id, key)
)
```

Reading it also requires an owner:

```python
store.get("alice", "answer-style")
```

In a real service, `owner_id` must come from the authenticated request context,
not from a model proposal or an untrusted client field. Including an owner column
does not by itself establish access control.

This small design choice matters. A real multi-tenant system will add namespaces, tenants, versions, retention metadata, provenance, and deletion state, but ownership should be explicit from the beginning.

---

## 9. Human-in-the-Loop means the program intentionally stops

A valid Tool call is not automatically an authorized side effect.

The refund workflow persists:

```text
phase = waiting_approval
```

and produces a structured request. Its type makes clear that review receives
the proposed action, its arguments, and a reason—not an unlabeled Boolean:

```python
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    run_id: str
    action: str
    arguments: Mapping[str, Any]
    reason: str


ApprovalRequest(
    run_id="run-001",
    action="issue_refund",
    arguments={"order_id": "ORDER-42", "amount": "18.50"},
    reason="Refund changes external financial state.",
)
```

The reviewer can see the exact action and arguments under review.

That is more meaningful than an unlabeled “Are you sure? yes/no” dialog.

---

## 10. Review may approve, edit, or reject

Real reviewers often want to say, “Approve, but change the amount.”

So the chapter models:

```text
approve
edit
reject
```

Edited arguments are validated again. Human input does not bypass schema or
business validation simply because it came from a person. The essential branch
from `approval.py` is complete enough to show where that happens:

```python
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Literal


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    outcome: Literal["approve", "edit", "reject"]
    edited_arguments: Mapping[str, Any] | None = None


def resolve_refund_arguments(
    original: Mapping[str, Any],
    decision: ApprovalDecision,
) -> dict[str, Any] | None:
    if decision.outcome == "reject":
        return None
    if decision.outcome == "approve":
        candidate = dict(original)
    elif decision.outcome == "edit" and decision.edited_arguments is not None:
        candidate = dict(decision.edited_arguments)
    else:
        raise ValueError("edit requires edited_arguments")

    order_id = candidate.get("order_id")
    if not isinstance(order_id, str) or not order_id.strip():
        raise ValueError("order_id must be a non-empty string")
    try:
        amount = Decimal(str(candidate.get("amount")))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("amount must be numeric") from exc
    if amount <= 0:
        raise ValueError("amount must be positive")
    return {"order_id": order_id.strip(), "amount": str(amount)}
```

The safe flow is:

```text
model proposal
    ↓
human review
    ↓
approve / edit / reject
    ↓
validate final arguments
    ↓
authorization
    ↓
execute
```

---

## 11. Approval is not authorization

A person clicking Approve does not prove that person has permission to approve the action.

Approval records a review decision. Authorization decides whether the identity is allowed to make that decision or execute that capability.

This chapter focuses on durable review. A later reliability and safety chapter will strengthen the permission model.

---

## 12. Durable HITL survives the original process

The milestone is simple to describe and important to achieve:

```text
runtime A
  ↓
prepare action
  ↓
save waiting_approval checkpoint
  ↓
runtime A disappears

runtime B
  ↓
open same store
  ↓
load same run_id
  ↓
receive human decision
  ↓
resume execution
```

The following complete recovery core uses one database path for both runtime
objects:

```python
from pathlib import Path

from approval import ApprovalDecision
from durable_workflow import RefundWorkflow, SQLiteCheckpointStore


db_path = Path("agent.db")
runtime_a = RefundWorkflow(SQLiteCheckpointStore(db_path))
request = runtime_a.start(
    run_id="run-001",
    order_id="ORDER-42",
    amount="18.50",
)

# The original process could disappear after this persisted pause.
runtime_b = RefundWorkflow(SQLiteCheckpointStore(db_path))
final = runtime_b.resume("run-001", ApprovalDecision(outcome="approve"))
```

`runtime_b` shares no Python objects with `runtime_a`; the common database file
and `run_id` are the recovery boundary. The supplied `demo.py` uses a temporary
directory so it leaves no database file in the repository. That makes it safe
to run repeatedly, but it only demonstrates object recreation in one process.
Use a deliberate durable path such as `agent.db` when testing a real process
restart, and do not commit that database file.

That is meaningfully different from keeping a Python process blocked on `input()`.

---

### 12.1 Optional: let DeepSeek make proposals, not decisions

The offline example is sufficient for learning persistence and HITL. A live
model is useful here for a narrower reason: it lets us observe the exact point
where a model turns a user message into a **refund proposal** and a **Memory
Candidate**. It still does not receive permission to write memory or execute a
refund.

[`code/deepseek_hitl.py`](code/deepseek_hitl.py) asks DeepSeek for one JSON
object with `reply`, `refund`, and `memory`. Before anything happens, the
application validates that shape, confirms that a proposed order ID appeared in
the user message, assigns `owner_id` from trusted application state, applies
the memory policy, and saves an approval checkpoint. Human input is still
required before the refund result is recorded.

[`code/langgraph_deepseek_hitl.py`](code/langgraph_deepseek_hitl.py) expresses
the same preparation as this graph:

```text
DeepSeek proposal
    -> validate and apply Memory Policy
    -> validate refund proposal and save waiting_approval checkpoint
    -> human review outside the graph
```

The LangGraph version makes the preparation steps observable. SQLite remains
the durable checkpoint store, and `RefundWorkflow.resume()` remains responsible
for processing the reviewed result. A graph run by itself does not make the
review durable.

Install the optional dependencies and use the same environment variables as the
earlier live-model stages:

```bash
python -m pip install -r stages/06-memory-persistence-hitl/code/requirements.txt
```

Windows CMD:

```bash
set "DEEPSEEK_API_KEY=your_key_here"
set "DEEPSEEK_MODEL=deepseek-v4-flash"
python stages/06-memory-persistence-hitl/code/deepseek_hitl.py
python stages/06-memory-persistence-hitl/code/langgraph_deepseek_hitl.py
```

PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"
python stages/06-memory-persistence-hitl/code/deepseek_hitl.py
python stages/06-memory-persistence-hitl/code/langgraph_deepseek_hitl.py
```

Both programs use the same sample request. Change `user_message` in either
file to compare a refund request, a memory-only request, and a request with no
proposal. The application should continue to own every write and side effect.

---

## 13. Persisted information and model context are different problems

After this chapter we can persist checkpoints, conversation history, selected memory, Tool observations, RAG results, and MCP data.

It is tempting to send all of it to the model on every turn.

That would confuse storage with attention.

**What may be retained** is a durability question. **What the model should see now** is a context-selection question.

A warehouse can hold a hundred boxes. A desk should not contain all hundred at once.

Stage 07 is about deciding what belongs on the desk.

---

## 14. Run the chapter

The offline demo uses only the Python standard library, so there is no
dependency to install. The end-to-end demo is:

```bash
python stages/06-memory-persistence-hitl/code/demo.py
```

When the new runtime reaches the approval boundary, enter one of these values:

```text
approve  # execute the teaching refund result
edit     # enter a replacement order ID and amount; both are validated again
reject   # finish without recording the refund result
```

For example, choose `edit` and enter `-1` as the amount to see validation
reject the review input. The demo keeps the checkpoint in `waiting_approval`
and asks again, so you can then choose a valid outcome.

Boundary checks:

```bash
python stages/06-memory-persistence-hitl/code/checks.py
```

They verify durable recovery across object recreation, rejection without side effects, revalidation after edit, local idempotency, conservative memory writes, sensitive-memory rejection, and owner-scoped storage.

The demo database is temporary and is deleted after the program exits. Its
purpose is to show that a second runtime can use the same SQLite file before
that cleanup; it is not a production retention setting.

---

## 15. What should be clear before moving on

State is the execution snapshot; a checkpoint is a durable form of that snapshot.

Checkpoints preserve progress. Long-term memory preserves selected information across threads.

Memory extraction is a proposal, not permission to store forever.

Human review may approve, edit, or reject, but edited values still require validation and approval still does not replace authorization.

Durable recovery makes restart possible; it does not automatically provide exactly-once semantics for external systems.

Once these boundaries are clear, the next question becomes unavoidable:

> **Now that the system can retain so much information, what should each model turn actually receive?**

That is [Stage 07: Context Engineering](../07-context-engineering/README.md).

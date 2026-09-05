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

---

## 3. A checkpoint stores what is necessary to continue

The teaching code defines a small state record:

```python
@dataclass(frozen=True, slots=True)
class WorkflowState:
    run_id: str
    phase: str
    action: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
```

A tiny SQLite checkpoint store persists it:

```python
def save(self, state: WorkflowState) -> None:
    payload = json.dumps(asdict(state))
    conn.execute(
        """
        INSERT INTO checkpoints(run_id, state_json)
        VALUES (?, ?)
        ON CONFLICT(run_id)
        DO UPDATE SET state_json=excluded.state_json
        """,
        (state.run_id, payload),
    )
```

The important change is architectural. Continuation no longer depends on the original Python object. A new runtime can open the same store, load the same `run_id`, and recover the phase and arguments.

That is the first layer of durable execution.

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

and a local unique table to demonstrate one defense. This proves idempotency only inside the teaching store. Real external APIs need their own idempotency contract, unique business keys, or compensation design.

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

The chapter defines:

```python
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

The teaching store keys memory by both owner and key:

```python
PRIMARY KEY (owner_id, key)
```

Reading it also requires an owner:

```python
store.get("alice", "answer-style")
```

This small design choice matters. A real multi-tenant system will add namespaces, tenants, versions, retention metadata, provenance, and deletion state, but ownership should be explicit from the beginning.

---

## 9. Human-in-the-Loop means the program intentionally stops

A valid Tool call is not automatically an authorized side effect.

The refund workflow persists:

```text
phase = waiting_approval
```

and produces a structured request:

```python
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

Edited arguments are validated again. Human input does not bypass schema or business validation simply because it came from a person.

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

The complete example creates one `RefundWorkflow`, pauses it, discards that object, constructs another workflow, and resumes from the same SQLite file.

That is meaningfully different from keeping a Python process blocked on `input()`.

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

The end-to-end demo is:

```bash
python stages/06-memory-persistence-hitl/code/demo.py
```

Boundary checks:

```bash
python stages/06-memory-persistence-hitl/code/checks.py
```

They verify durable recovery across object recreation, rejection without side effects, revalidation after edit, local idempotency, conservative memory writes, sensitive-memory rejection, and owner-scoped storage.

---

## 15. What should be clear before moving on

State is the execution snapshot; a checkpoint is a durable form of that snapshot.

Checkpoints preserve progress. Long-term memory preserves selected information across threads.

Memory extraction is a proposal, not permission to store forever.

Human review may approve, edit, or reject, but edited values still require validation and approval still does not replace authorization.

Durable recovery makes restart possible; it does not automatically provide exactly-once semantics for external systems.

Once these boundaries are clear, the next question becomes unavoidable:

> **Now that the system can retain so much information, what should each model turn actually receive?**

That is Stage 07: Context Engineering.

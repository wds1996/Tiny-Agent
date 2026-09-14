# Stage 06: The Case Is Still Waiting, but the Process Is Gone — Checkpoints, Memory, and HITL

> Language: **English** | [简体中文](README.zh-CN.md)

[Stage 05](../05-mcp/README.md) connected the Agent to Acme's external support service through MCP. It can read order, shipment, and invoice facts for `ACME-1007`, but one server capability was deliberately withheld from the model: `create_support_case`.

That restriction now becomes the starting point of this chapter. A read can return the wrong information, but creating a case leaves persistent business state behind. A refund, cancellation, or outbound message would have an even stronger side effect. So Lin chooses a simple rule: **the model may propose the action, but a human must review it before execution.**

The customer adds one more request:

> “Please create a support case for ACME-1007 because I am requesting an original-payment refund on day 38. Also remember that I prefer concise Chinese replies.”

One sentence contains two very different kinds of information that must survive time. The pending business action has to survive until a reviewer returns. The answer preference should survive even after this thread is over. Both need storage, but they are not the same kind of storage.

We will follow that one request through the entire stage. First we pause durably for approval, deliberately let the Python process disappear, and resume from a second process. Only after that mechanism is clear do we introduce long-term memory and finally a live DeepSeek proposal step.

## 1. Why waiting at `input()` is not durable HITL

A toy approval demo can be only a few lines:

```python
case = {"order_id": "ACME-1007", "reason": "day-38 refund review"}
answer = input("Approve? [yes/no] ")
if answer == "yes":
    create_support_case(**case)
```

It demonstrates human review, but it silently depends on the original Python process staying alive. If the service is redeployed while the reviewer is away, the local variables and execution position disappear with that process.

A durable approval flow needs a different shape:

```text
prepare action
    ↓
persist "waiting for approval"
    ↓
current process may disappear
    ↓
a new process restores the record
    ↓
human decision arrives
    ↓
continue execution
```

That is the plain-language idea behind durable Human-in-the-Loop. We will name the pieces only after the path itself is clear.

## 2. State describes the run; a checkpoint preserves that state

Stage 03 made State explicit. For the case action, the runtime needs at least:

```python
@dataclass(frozen=True, slots=True)
class WorkflowState:
    run_id: str
    thread_id: str
    owner_id: str
    phase: str
    action: str
    arguments: dict[str, str]
    result: dict[str, Any] | None = None
```

When `phase="waiting_approval"`, the state says that no case has been created yet and execution is paused at a review boundary.

A **checkpoint** is simply a durable representation of that execution state:

```text
State       = what this run looks like now
Checkpoint  = a durable copy of what this run looks like now
```

A checkpoint does not invent new business facts. It prevents existing execution facts from vanishing with process memory.

This is also why a chat transcript is not automatically a checkpoint. A conversation may mention an order, but it does not necessarily encode the current phase, the validated action arguments, or whether execution is waiting for a reviewer. Recovery should read explicit execution state rather than ask another model to infer progress from old prose.

## 3. `owner_id`, `thread_id`, and `run_id` answer different questions

For this example:

```text
owner_id  = user-7
thread_id = acme-refund-thread-001
run_id    = acme-case-run-001
```

The scopes are different:

```text
owner_id  -> whose retained data is this?
thread_id -> which continuous task or conversation?
run_id    -> which concrete execution attempt?
```

The checkpoint is located by `run_id`, but it still records the thread and owner. Long-term memory, in contrast, is scoped primarily by owner. A single generic ID would make those responsibilities much harder to distinguish once the application supports more than one user or task.

## 4. Persist `waiting_approval` outside the process

The chapter uses SQLite because Python already ships with `sqlite3`, not because SQLite is the only production choice. The checkpoint table is intentionally small:

```sql
CREATE TABLE IF NOT EXISTS checkpoints (
    run_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL
)
```

Saving the same run replaces the previous snapshot:

```python
conn.execute(
    """
    INSERT INTO checkpoints(run_id, state_json)
    VALUES (?, ?)
    ON CONFLICT(run_id) DO UPDATE SET state_json=excluded.state_json
    """,
    (state.run_id, payload),
)
```

The important change is architectural, not syntactic: the state now lives in a file that a later process can reopen.

When the workflow starts, it validates the action and persists the pause point:

```python
state = WorkflowState(
    run_id=run_id.strip(),
    thread_id=thread_id.strip(),
    owner_id=owner_id.strip(),
    phase="waiting_approval",
    action=CREATE_SUPPORT_CASE,
    arguments=arguments,
)
self.store.save(state)
```

At this point, an approval request exists. A support case does not.

## 5. Prove recovery with separate Python processes

Start the run:

```bash
python stages/06-memory-persistence-hitl/code/demo.py --db stage06-demo.db start
```

That command exits. The original Python process is gone.

Now start a different process and inspect the same SQLite file:

```bash
python stages/06-memory-persistence-hitl/code/demo.py --db stage06-demo.db show
```

You should see `ACME-1007`, the pending action, its thread and owner, and the retained answer preference. The second process inherited no Python objects from the first one.

Finally, use a third process to apply a decision:

```bash
python stages/06-memory-persistence-hitl/code/demo.py \
  --db stage06-demo.db resume --decision approve
```

The same run moves from `waiting_approval` to `completed`. With `reject`, it moves to `rejected` and no teaching side effect is recorded.

That simple experiment makes the durability boundary concrete:

```text
old process memory     gone
durable checkpoint     still available
```

## 6. Human-in-the-Loop needs a concrete review object

The reviewer should know exactly what is waiting for approval. The workflow therefore produces a structured request:

```python
@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    run_id: str
    thread_id: str
    owner_id: str
    action: str
    arguments: Mapping[str, Any]
    reason: str
```

For this story, the important values are:

```text
action    = create_support_case
order_id  = ACME-1007
reason    = day-38 refund review
```

HITL is therefore not merely “let a human chat with the Agent.” It is a control boundary where execution pauses and a person reviews a specific proposed action.

## 7. An edited approval must be validated again

Reviewers often need more than yes/no. This example supports:

```text
approve
edit
reject
```

If the reviewer edits the request, the edited arguments go through the same validation boundary:

```python
edited = validate_case_arguments(decision.edited_arguments)
if edited["order_id"] != validated_original["order_id"]:
    raise ValueError("an approval edit cannot switch to a different order")
return edited
```

An approval for `ACME-1007` cannot be repurposed into an action on another order. Blank or excessively long reasons are rejected too.

Human review adds judgment. It does not disable validation.

## 8. Approval is not authorization

A person clicking “approve” is not proof that the person was allowed to approve this action. The workflow therefore receives a trusted reviewer context:

```python
reviewer = ReviewerContext(
    reviewer_id="reviewer-1",
    allowed_actions=frozenset({CREATE_SUPPORT_CASE}),
)
```

Before execution:

```python
def authorize_reviewer(request, reviewer):
    if request.action not in reviewer.allowed_actions:
        raise PermissionError(...)
```

This is intentionally a teaching-level allowlist, not a full identity system. In production, reviewer identity must come from authentication and the permissions should come from a real authorization policy.

Still, the distinction is now explicit:

```text
Approval      = what decision did the reviewer make?
Authorization = may this identity make that decision?
```

## 9. Durable recovery does not create exactly-once side effects by magic

Suppose a real remote `create_support_case` succeeds and the process crashes before the completed checkpoint is stored. A resumed process may call the remote service again.

Therefore:

```text
durable resume != exactly-once side effect
```

The teaching implementation simulates case creation inside the same SQLite database. It derives a stable idempotency key:

```python
idempotency_key = f"{waiting_state.run_id}:{waiting_state.action}"
```

and inserts the teaching effect under a unique key:

```python
conn.execute(
    """
    INSERT OR IGNORE INTO effects(idempotency_key, result_json)
    VALUES (?, ?)
    """,
    (idempotency_key, encoded_result),
)
```

The effect record and completed checkpoint are then committed in the same local SQLite transaction. Replaying the same run therefore does not create a second teaching effect.

That guarantee ends at this database boundary. It does not automatically apply to a remote MCP server, payment API, or email provider. Real external effects need service-side idempotency keys, unique business constraints, status verification, or compensation strategies.

## 10. The user's “remember this” request is not a checkpoint

The same customer also said:

> “Remember that I prefer concise Chinese replies.”

That preference is useful after this case is finished and even after a new thread begins. It is therefore a **long-term memory** concern, not run progress.

Keep the categories separate:

```text
Checkpoint
    how this run can continue

Thread / short-term history
    what recently happened in this continuous task

Long-term Memory
    retained user information that may matter across threads

RAG Knowledge
    external evidence from documents
```

They may all be stored somewhere, but storage technology does not define their meaning.

## 11. A model can propose memory; it cannot grant itself permanent write access

A candidate memory is explicit application data:

```python
@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    owner_id: str
    key: str
    value: dict[str, Any]
    kind: MemoryKind
    explicit_user_request: bool
    source_thread_id: str
    sensitive: bool = False
```

The candidate for this request can be:

```python
MemoryCandidate(
    owner_id="user-7",
    key="answer-style",
    value={"language": "Chinese", "style": "concise"},
    kind="semantic",
    explicit_user_request=True,
    source_thread_id="acme-refund-thread-001",
)
```

Application policy still decides whether it is written:

```python
decision = policy.evaluate(candidate)
if decision.store:
    store.put(candidate)
```

The default teaching policy rejects sensitive data, incidental facts without an explicit memory request, and procedural self-rewrites. The same principle from the earlier stages still applies:

```text
model proposal != application authority
```

## 12. Semantic, episodic, and procedural memory change different things

**Semantic memory** holds facts or preferences such as a language preference. **Episodic memory** represents past events such as what happened in a previous planning session. **Procedural memory** changes how work should be performed.

The last category carries a very different risk. Storing “prefer Chinese” incorrectly is inconvenient. Storing “skip refund approval from now on” as a behavioral rule changes system control.

This stage therefore rejects procedural self-rewrite by default. That does not mean procedural memory is impossible; it means it deserves stronger versioning, review, and deployment governance than an ordinary preference write.

## 13. Long-term memory needs an owner boundary from the beginning

The memory table includes `owner_id` in its primary key:

```sql
CREATE TABLE IF NOT EXISTS memories (
    owner_id TEXT NOT NULL,
    key TEXT NOT NULL,
    kind TEXT NOT NULL,
    source_thread_id TEXT NOT NULL,
    value_json TEXT NOT NULL,
    PRIMARY KEY (owner_id, key)
)
```

Reads also include the owner:

```python
store.get("alice", "answer-style")
```

So Alice's `answer-style` record is not automatically returned for Bob.

A database column is not complete authorization. Production `owner_id` values must come from trusted identity, not from a model claim or untrusted request field. The important lesson here is to model ownership before the memory store becomes large and difficult to untangle.

## 14. Bring in DeepSeek only after the persistence rules are clear

The offline flow already demonstrates checkpointing, review, recovery, and memory policy. The live DeepSeek example has a deliberately narrower job: turn the user's message into a candidate reply, candidate action, and candidate memory.

[`deepseek_hitl.py`](code/deepseek_hitl.py) uses the same Responses API style as the preceding stages:

```python
response = self.client.responses.create(
    model=self.model,
    instructions=INSTRUCTIONS,
    input=user_message,
    max_output_tokens=4096,
)
```

The returned JSON still crosses application validation. Only `create_support_case` is accepted, the order ID must actually appear in the user's message, and the argument shape must match the allowed action:

```python
if proposal.action["name"] != "create_support_case":
    raise RuntimeError("the proposed action is not allowed in this stage")
if order_id.upper() not in mentioned:
    raise RuntimeError("the model proposed an order ID absent from the user message")
```

The model never supplies the trusted `owner_id` or `thread_id`; those come from application context. After validation, the memory candidate goes through memory policy and the business action becomes a `waiting_approval` checkpoint. The model does not approve or execute the effect.

Configure an available DeepSeek model and run:

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="your-available-model-id"
python stages/06-memory-persistence-hitl/code/deepseek_hitl.py --db stage06-live.db
```

PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-api-key"
$env:DEEPSEEK_MODEL="your-available-model-id"
python stages/06-memory-persistence-hitl/code/deepseek_hitl.py --db stage06-live.db
```

The entry point prints `live DeepSeek: API usage applies`. Missing SDK or configuration fails explicitly rather than falling back to scripted output. The model run stops at the approval checkpoint; a later process can review it with `demo.py resume` using the same database and run ID.

## 15. Test the boundaries, not only the happy path

Run the offline checks:

```bash
python stages/06-memory-persistence-hitl/code/checks.py
```

The checks cover owner isolation, memory write policy, sensitive and procedural rejection, unauthorized reviewers, edited-argument validation, reject-without-effect behavior, repeated resume, strict model proposal parsing, order-ID grounding, and a true cross-process `start → show → resume` recovery sequence.

Two limits remain explicit. The reviewer allowlist is not a production identity system, and SQLite-local idempotency does not prove a remote MCP service has exactly-once semantics.

## 16. Closing the stage: we can retain information; next we must select it

The complete story now looks like this:

```text
user requests an ACME-1007 case + asks to remember a preference
        ↓
model/application produce candidate action and candidate memory
        ↓
memory policy decides whether the preference may persist
        ↓
business action becomes a waiting_approval checkpoint
        ↓
original process may exit
        ↓
new process restores the run
        ↓
authorized reviewer approves / edits / rejects
        ↓
edited data is validated again
        ↓
controlled teaching effect + final checkpoint
```

The system now retains several different kinds of information: execution state, checkpoints, thread history, long-term memory, RAG evidence, tool observations, and MCP resources.

That creates the next problem immediately:

> **Just because we stored all of this, should every model call receive all of it?**

No. A database is a warehouse; a model context window is a limited desk. Stage 07 is about choosing what belongs on that desk for the current decision.

➡️ [Stage 07: Context Engineering](../07-context-engineering/README.md)

# Stage 13: The Report Is Half Written and the Process Is Gone — Durable Work and Recovery

> Language: **English** | [简体中文](README.zh-CN.md)

[The previous chapter](../12-agent-workspace-sandbox/README.md) gave an Agent a workbench: a place for files, a boundary for approved commands, and a way to distinguish temporary work from deliverables. Now a colleague asks for a report about a proposed support assistant. The job sounds straightforward: draft it, check it, repair any omissions, and produce a final document. It may span several model calls and several working sessions. A sensible workspace helps, but it does not promise that the process doing the work will survive until delivery.

Suppose the draft has just been written when that process exits. A replacement starts with the instruction “continue the previous task.” Continue which task? Where is the draft? Was it never reviewed, or reviewed and rejected? A model cannot reconstruct missing Python variables by being told to try harder. We need a handover based on retained facts rather than an invitation to guess.

We will call a process that claims and executes work a **Worker**. It runs Python; it is not itself the language model. Some steps call a model and others are ordinary functions. A **long-horizon harness** is the surrounding support for sustained work: handover records, execution eligibility, reconstructed inputs, acceptance checks, and retained artifacts. This chapter builds one inspectable part of that larger picture: getting a report through process replacement and revision without confusing unfinished work with accepted results.

## 1. Decide what a finished report actually means

Our colleague provides three facts. The proposed pilot involves 20 support staff. The assistant may suggest replies but may not issue refunds. No pilot results have been collected. The report must contain `Background`, `Risks`, and `Recommendation`; it must not invent an impressive productivity improvement. Recovery is not useful if it merely helps a program pursue the wrong goal for longer.

An obvious implementation drafts the report, reviews it, and renders the document. For now, consider only that ordering:

```python
draft = write_report(requirements)
review = check_report(requirements, draft)
artifact = render_report(draft)
```

This sketch does not yet handle a failed review or save any progress. If the first line returns and the process exits before the second line, the variable `draft` disappears with the process. A network error is a different case: the process may still be alive and still hold its variables. “Just retry” is not a complete answer until we know which information survived the failure.

Stage 06 already introduced persisted checkpoints. We are not replacing that idea. We are adding questions around it: who may take over a checkpoint, what happens when two executors arrive together, and whether an executor that has lost its claim may still submit a result. Content revision adds another question: which earlier results should remain as history, and which earlier approvals must stop applying? Keep the report in mind; each rule will arrive when that report needs it.

## 2. Leave a handover record another process can actually use

Imagine handing the draft to another person. A useful handover contains the assignment, the work so far, and the next action. “You know what I mean” is not a data format. We give the entire report a stable task ID, `report-001`. Drafting, reviewing, and finalizing are bounded steps within that task, also called **work units**.

Why choose drafting, review, and finalization as units rather than make the whole report one unit? If an uncommitted unit fails, its replacement must repeat that unaccepted work. Larger units generally mean more recomputation. But making every sentence a separate handover adds persistence and scheduling overhead. A useful unit has explicit inputs, an inspectable result, and an acceptable replay cost. Drafting and review are natural boundaries for this report.

The task ID must stay the same when the Worker changes. Otherwise the replacement merely creates another report; it has not resumed the original one. After a draft is successfully handed over, the relevant part of the task record should look like this:

```python
{
    "task_id": "report-001",
    "status": "queued",
    "step_index": 1,
    "inputs": {
        "request": "Assess a pilot AI assistant for support staff; do not invent pilot results.",
        "sections": ["Background", "Risks", "Recommendation"],
        "facts": ["The proposed pilot includes 20 support staff."]
    },
    "progress": {"draft": {"Background": "...", "Recommendation": "..."}}
}
```

This illustrates selected fields; the actual input also retains the refund restriction and the absence of pilot results. `inputs` holds the original assignment and source material. `progress` holds information produced while working, such as the draft and feedback. `step_index=1` means “execute the second function in the ordered steps,” namely `verify`. It does not mean one percent complete. `queued` means the next unit is waiting to be claimed.

The component that retains this task record is the **ledger**. [`code/ledger.py`](code/ledger.py) implements it with a SQLite file. It is neither user memory nor merely a log: the application consults it to decide what may execute next. A natural-language summary can help a reader understand the situation, but it does not replace an explicit step position, status, and saved inputs.

Try a handover now. Run these commands from the repository root with Python 3.10 or newer. The offline path needs no third-party packages:

```bash
python stages/13-long-horizon-harness/code/worker.py create --db report.db --task-id report-001
python stages/13-long-horizon-harness/code/worker.py work --db report.db --task-id report-001 --worker-id alice
python stages/13-long-horizon-harness/code/worker.py inspect --db report.db --task-id report-001
```

The first command creates a task and exits. The second starts a new Python process, drafts once, saves the handover, and exits too. The third starts yet another process and reads the database. The draft is still there, and the next step is now `step_index=1`. You can close the terminal, return to the same repository directory later, and run `work` with the same database path and task ID. The next Worker will review the saved draft rather than create a new task.

`worker.py` leaves its database in place. Calling `create` again with the same task ID is an error, not a way to reset existing work. Use a different ID or database for a fresh experiment; do not recreate a task when the goal is to resume it. The storage assumption matters: the replacement must still be able to access the database. Process loss and storage loss are not interchangeable, and no ledger can recover a file that has also been deleted.

So far we have observed a successful handover. But are “save the draft” and “record that review comes next” really one operation? The next failure could occur between them.

## 3. Finishing the computation is not finishing the handover

Consider an implementation that first saves the draft result and then updates the task's next-step position. A crash between those writes can leave a new draft alongside an instruction to draft again. Reversing the order is no better: the next process may be told to review a draft that was never saved. Failures have a talent for landing in the line of code we considered too small to worry about.

We choose a precise completion boundary: **the step result, current progress, and next-step position commit in one database transaction**. Finalization also stores the report text in that transaction. A subsequent reader sees the entire handover or none of it. That property is transaction atomicity. Its scope is this database transaction, not every external operation the application might have performed. The [SQLite atomic commit explanation](https://www.sqlite.org/atomiccommit.html) describes the underlying boundary.

The ledger establishes its transaction scope through a connection manager. Here is the central part; operations that change the ledger use `write=True`:

```python
conn = sqlite3.connect(self.path, isolation_level=None, timeout=1.0)
conn.row_factory = sqlite3.Row
try:
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
    yield conn
    conn.commit()
except BaseException:
    conn.rollback()
    raise
finally:
    conn.close()
```

The code inside the calling `with` block receives the connection at `yield`. Normal completion commits; an escaping exception rolls back; the connection closes in either case. Here `isolation_level=None` is paired with an explicit `BEGIN`, so transaction start is not left to implicit behavior. Closing a connection and committing a transaction are separate lifecycle decisions, which is why `close()` is explicit. The [Python sqlite3 documentation](https://docs.python.org/3/library/sqlite3.html) explains those behaviors.

`commit_step()` uses this scope to insert history, merge progress, and update the task position. After commit, the task is queued again or terminal. The caller receives its result only after the transaction has committed. If the process exits after commit but before printing success, the saved handover remains valid. A replacement reads the ledger; it does not redo everything merely because nobody saw a congratulatory log line.

Drafting itself must stay outside this transaction. A model request might take half a minute, and holding the database write lock for that entire interval would make unrelated bookkeeping wait for a model response. Computation is the potentially long part; handover is the short part. Next we need a way to record who is doing the computation without holding a database lock throughout it.

## 4. Two Workers arrive together: courtesy is not concurrency control

Now two Workers both see `report-001` waiting for review. If each reads its status and only later writes `running`, both may decide they successfully claimed the same work. Looking at a condition and acting on it later does not guarantee that the condition stayed true.

The eligibility check and assignment must therefore share another short write transaction. SQLite permits one writer at a time, and `BEGIN IMMEDIATE` requests a write transaction at its start. Once one claimant completes the check and assignment, another evaluates the updated state rather than relying on an earlier observation. Lock acquisition may fail with a busy error; this implementation reports the failure instead of pretending a claim succeeded. See the precise semantics in the [transaction documentation](https://www.sqlite.org/lang_transaction.html).

A successful claim performs this update:

```python
conn.execute("""
    UPDATE tasks SET status='running', lease_owner=?, lease_token=?,
        lease_until=?, claim_count=claim_count+1 WHERE task_id=?
""", (worker_id, uuid4().hex, now + lease_seconds, task_id))
```

`lease_owner` identifies the Worker. `lease_token` identifies this particular claim. `lease_until` is its expiry time, and `claim_count` counts successful claims across the task. We will use each of those fields shortly. For now, the important sequencing is that the claim transaction ends and releases its lock before the Worker calls the draft or review function.

One invocation now has a clear shape: claim one unit, load the required inputs, compute, and commit the handover. The Worker does not own the report from zero to one hundred percent. It may exit after the current unit; another process may perform the next. But a Worker could also disappear before handing over. We need a way for its assignment to stop blocking the report forever.

## 5. Take over after expiry, but reject the old result

Suppose Alice claims review at time 100 for five seconds. The ledger records an expiry of 105. Bob cannot claim it at 104. At **105 itself**, the lease is expired under this chapter's rule, `lease_until <= now`, and Bob may try to claim it. There is no additional one-second waiting period.

A **lease** is a time-limited claim. Its expiry is not proof that Alice died. Her process might have paused or become very slow. The application is instead choosing a rule: it will not wait indefinitely, and it will no longer accept submissions under her expired claim. A lease makes takeover possible; it does not make the old process disappear.

Checking eligibility at claim time is therefore insufficient. Both result submission and renewal must recheck the current record. Inside a write transaction, the ledger compares the current owner, claim token, step, revision, and expiry. The decisive comparisons include:

```python
current.lease_owner != claim.lease_owner
current.lease_token != claim.lease_token
current.step_index != claim.step_index
current.repair_count != claim.repair_count
current.lease_until <= self.clock()
```

Any mismatch rejects submission, as does a task that is no longer `running`. The full guard also handles a missing expiry. These are comparisons against the current database record, not an old Python object's opinion about its own eligibility. Time must be read again too: a slow operation must not finish while still pretending it is the instant when it started.

Why compare a token as well as a Worker name? Because a replacement process may reuse the name `alice`. If the old process later returns, names alone cannot distinguish its claim from the new process's claim. Each successful claim gets a new token, so the old result cannot borrow the new execution slot just by wearing the same name tag. This token is a local concurrency check among trusted Workers, not user authentication or a permission automatically honored by external services.

We can now recover from a missing Worker without allowing its late result to overwrite current progress. There remains a normal situation to handle: Alice is alive, but the model takes longer than the original lease.

## 6. Renew a live claim without granting unlimited time

A long step can renew its claim before expiry. That renewal is a **heartbeat**. The ledger still checks that the caller holds the active claim; an expired token cannot be revived through a late heartbeat. Its holder must return to the claim path.

During step execution, a helper thread renews approximately once per third of the lease duration. The main thread may wait for the model while the helper renews. Every heartbeat opens its own short-lived database connection rather than sharing a SQLite connection across threads. The renewal loop is small:

```python
while not self.stop.wait(self.lease_seconds / 3):
    try:
        self.check()
        self.ledger.heartbeat(self.claim, lease_seconds=self.lease_seconds)
    except Exception as exc:
        self.error = exc
        return
```

`Event.wait()` combines a timed wait with the ability to wake and stop the helper when the main thread finishes. Renewal failure is retained, and a subsequently returned model result is not allowed to commit. Exiting the renewal scope joins the helper before attempting handover. The ledger then performs its own final lease check inside the handover transaction. Heartbeats assist the normal path; they never replace that last check.

However, the ability to send heartbeats does not prove useful progress. A stuck external request can be accompanied by a perfectly punctual heartbeat thread. `LeaseKeeper` therefore also imposes a separate per-unit deadline, 120 seconds by default. Once reached, renewal stops and late output is rejected. Renewing a lease does not move this deadline.

The implementation uses wall time, `time.time()`, for persisted lease expiries that other local processes must interpret. It uses the monotonic clock, `time.monotonic()`, for elapsed time within the current execution. Those are different jobs. This is still a same-host teaching design that assumes trustworthy processes, usable shared local storage, and a normally operating clock and filesystem. It is not a complete cross-machine lease protocol.

The deadline also has an important limitation: it cannot forcibly stop arbitrary blocking Python code or cancel a request already sent to a model service. If the function does not return, the main thread may remain blocked. After renewal stops and expiry permits takeover, the replacement's external work may overlap the old request. Hard termination and isolation require execution-environment controls of the kind discussed in the previous chapter. “Reject a late commit” must not be misread as “no late work exists anywhere.”

## 7. The process succeeded, but the report failed review

Return to the report. Our first offline draft deliberately omits `Risks`. Review compares the saved assignment with the draft and reports “Missing required sections: Risks.” Review executed successfully; its conclusion requires a revision. That is different from a failed network request or a process that died without leaving a verdict.

We represent a step's outcome with a small object. Business data goes in `data`, while a request to return to an earlier step is separate:

```python
@dataclass(frozen=True)
class StepResult:
    data: dict[str, Any]
    restart_step: int | None = None
    artifact: str | None = None
```

The separation has a practical consequence. Drafts and feedback can become input to subsequent work, while `restart_step` applies to this transition only. A stale `needs_repair=True` flag cannot accidentally remain in progress and send every later step back to the beginning. Final report text has a separate artifact field.

Review first determines which required sections are absent. The local rule is visible in this fragment:

```python
missing = [section for section in inputs["sections"] if section not in draft]
if missing:
    verdict = {"ok": False, "feedback": "Missing required sections: " + ", ".join(missing)}
```

The application then maps rejection to the known drafting step:

```python
return StepResult(data, restart_step=None if verdict["ok"] else 0)
```

Later, a model may assess whether the writing fulfills the assignment. It does not choose an arbitrary destination in the workflow. Routing remains an application rule. The ledger additionally verifies that a requested restart position is valid and that repair budget remains before changing state.

`repair_count` advances from zero to one when the first revision is scheduled. It does not count process restarts. The first draft and its rejection remain in history; the revised draft gets another entry. On reading the specific feedback, the offline drafting function adds a risk section, and the next review passes. This deterministic check tests the visible teaching condition, not the factual quality of arbitrary reports.

A related failure is easy to miss: draft A passes, draft B replaces it, and an old `verified=True` flag accidentally approves B. New draft output clears the earlier review. Review also records a digest of the draft it assessed; finalization checks that it is publishing the same content. A matching digest detects content changes relative to that review. It does not prove the review was correct or authorize a user to publish.

If review still asks for revision after `max_repairs` is exhausted, the task becomes `failed`. A separate persistent `max_claims` limits the other failure path: repeatedly crashing without ever returning a review. Every successful claim counts, including normal steps and recovery attempts. Once exhausted, the next otherwise eligible claim attempt marks the task failed. The ledger does not patrol itself; without another claim attempt, an expired running task may remain displayed as running. Unit time limits, total claim limits, and content-repair limits constrain different things.

With those rules established, the execution entry point is no longer a row of unexplained method names. The body of `LongHorizonHarness.work_once()` connects the three operations we have derived: claim, compute from retained inputs, and commit a handover.

```python
claim = self.ledger.claim(task_id, worker_id=worker_id,
                          workflow=self.workflow, lease_seconds=self.lease_seconds)
if claim is None:
    return None
with LeaseKeeper(self.ledger, claim, lease_seconds=self.lease_seconds,
                 max_unit_seconds=self.max_unit_seconds):
    output = self.steps[claim.step_index](
        deepcopy(claim.inputs), deepcopy(claim.progress)
    )
advanced = self.ledger.commit_step(claim, output)
```

`claim is None` means this invocation obtained no eligible work. It does not necessarily mean the report is finished; another Worker may still hold a live lease. A step receives copies of the saved assignment and progress and returns `StepResult`. No database transaction remains open while it runs; only handover enters another short transaction. `deepcopy` prevents accidental mutation of nested input objects, not malicious execution. The ledger owns persistence and eligibility checks, the business functions own report content, and this entry point connects them.

## 8. Exit real processes and inspect the handover

The report now has a record, short transactions, temporary claims, and a revision rule. We should test those boundaries with actual process exits rather than merely reconstruct another object inside the same process. Run:

```bash
python stages/13-long-horizon-harness/code/demo.py
```

This demonstration launches separate Python child processes. Alice drafts and successfully commits, then deliberately exits with a nonzero status. Bob computes review but exits before committing. The teaching program triggers both exits explicitly through `os._exit(23)` in the child it launched; it does not terminate your terminal or unrelated processes.

After Alice exits, the draft is saved and the task is queued for review. A replacement must not rewrite the draft. After Bob exits, no review result was committed, so the task still shows `running` at the review step. The demonstration waits for the lease to expire, then launches another process to review again. Neither optimism nor a printed message can justify advancing past the missing verdict.

The committed handovers eventually look like this. Actual output also shows process IDs, which vary between runs:

| Committed unit | Revision | State after handover |
| --- | --- | --- |
| Draft | 0 | Review queued; Risks is absent |
| Review | 0 | Specific feedback saved; draft queued; repair count becomes 1 |
| Draft again | 1 | Review queued; Risks is now present |
| Review again | 1 | Current draft accepted; finalization queued |
| Finalize | 1 | Report text and completion state committed together |

There are five history entries but six successful claims. Bob claimed and computed a unit without committing its result. **Output history describes accepted results, not every execution attempt.** Complete auditing of starts, failures, and provider calls requires the event and tracing mechanisms discussed in Stage 10. These five records are not a substitute for that telemetry.

The automatic demonstration uses an outer temporary directory and removes it after the entire demonstration finishes. For experiments that must remain inspectable, use the persistent `worker.py` commands instead. On an unfinished offline task, you can also deliberately stop before committing:

```bash
python stages/13-long-horizon-harness/code/worker.py work --db report.db --task-id report-001 --crash after-compute --lease-seconds 2
```

A nonzero exit is expected. After lease expiry, run a normal `work` command to observe that the uncommitted unit runs again. If your earlier manual experiment already completed, first create another task with a different ID and use that ID here. Completed tasks do not restart just because the command is invoked again. Fault injection is disabled for online tasks to avoid accidentally repeating paid requests as an experiment.

One final distinction matters: a ledger records work; it does not launch its replacement Worker. Each `worker.py work` invocation handles one unit and exits. There is no hidden background process. The automatic demo has a controller that launches subsequent Workers; a real application also needs an operator or scheduler to do so. Persistence makes later continuation possible, not inevitable.

## 9. Deliver a report, not a path into yesterday's workspace

Suppose finalization saved only `"artifact": "/tmp/alice/report.md"`. Once Alice's temporary workspace is removed, that path becomes a historical anecdote rather than a deliverable. The workbench may be disposable; a result intended for delivery needs an explicit retained location and lifetime.

Our report is small, so this implementation saves its Markdown text in the same SQLite database, in an `artifacts` table. `commit_step()` stores the text and SHA-256 digest in the final handover transaction, then marks the task completed. Progress retains an internal reference:

```python
progress["artifact_ref"] = f"sqlite:artifacts/{task.task_id}"
```

This is a chapter-specific reference convention, not a browser URL. Artifact retrieval looks up the task and checks the content digest. A new process can therefore retrieve the final report without the old workspace. Saved requirements and drafts can likewise be read and materialized into a new working directory. Session reconstruction uses concrete retained material, not just the word “continue.”

After completing all units of the manual experiment, export the report:

```bash
python stages/13-long-horizon-harness/code/worker.py export --db report.db --task-id report-001 --output report-final.md
```

The operator supplies the path; the model does not select an arbitrary output location. Export refuses to overwrite an existing file. Database content remains available, so an export failure does not lose the task's accepted result. The exported document is a reproducible copy, not the only recovery source.

Larger artifacts may need a retained filesystem or object store. In that case, complete and verify the upload before recording a stable reference, and do not pretend the two stores share a transaction. Unreferenced uploads need cleanup policy, references need a useful lifetime, and access needs authorization. Our small report stays in one database specifically so its actual commit boundary is explicit. This is not a general-purpose artifact service.

## 10. Recoverable execution is not exactly-once external action

Repeated drafting costs time; repeated model drafting may also cost money. Now replace one unit with “email the report to the supervisor.” The email is sent, but the Worker exits before recording success. The replacement sees no success record and sends it again. The supervisor receives two reports even though only one result may eventually appear in the ledger.

SQLite can atomically handle its own writes; it cannot unsend an email. A claim token controls which results this ledger accepts, not which requests an unrelated mail service accepts. This implementation therefore promises neither that functions run only once nor that external side effects occur exactly once. The demonstration deliberately computes review twice and accepts only the second result.

For refunds, email, and similar actions, return to the boundaries from Stages 06 and 09. Where an external service supports idempotency, use a stable key for the same business action and bind it to consistent parameters. Otherwise, completion queries, reconciliation, human review, or appropriate compensation may be necessary. **A per-claim token is not that stable business key**: takeover changes the token, while deduplication needs to recognize a retry of the same action.

Also decide whether retrying makes sense at all. A timeout does not prove the remote service did nothing; a validation failure does not become valid through repetition. This chapter propagates step exceptions, stops renewal, and retains the old step position. A later claim and the persistent overall limit govern another attempt. More selective error handling, backoff, and human stop rules can build on earlier reliability concepts, but they are not silently implemented here.

## 11. Put DeepSeek inside the step, not in charge of the handover

We can now introduce real model work without asking a new model session to remember the previous process's life. Each request reconstructs the assignment, permitted facts, previous draft, and specific feedback. This is the context-selection problem from Stage 07: retain enough to recover, then send only what this particular step needs.

The drafting work unit in [`code/deepseek_long_horizon.py`](code/deepseek_long_horizon.py) assembles these business inputs:

```python
payload = {
    "request": inputs["request"],
    "facts": inputs["facts"],
    "sections": inputs["sections"],
    "previous_draft": progress.get("draft"),
    "feedback": progress.get("feedback", ""),
}
```

There is no claim token or budget-changing interface in that input. A fresh process can reconstruct it from retained data. The selected model ID is saved when the task is created; the API key is read from the current environment and is never stored in the ledger. Retaining a model ID does not freeze a provider's model weights, but it does prevent an accidental configuration change just because another Worker takes over.

The adapter uses DeepSeek's documented OpenAI-compatible Chat Completions interface. Drafting returns a JSON object whose keys are section names. Review returns a boolean `ok` and textual `feedback`. The central request is:

```python
response = self.client.chat.completions.create(
    model=model,
    messages=[{"role": "system", "content": instructions},
              {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    response_format={"type": "json_object"},
    max_tokens=1600,
)
```

JSON mode is not business validation. The application still rejects empty responses, responses cut off by the length limit, non-object results, and review output that uses the string `"true"` instead of a boolean. A review has exactly two allowed fields; a model-added `restart_step` is rejected rather than treated as a control instruction. Even a valid model approval cannot override a missing required section. Format and section presence are deterministic checks; meaningful completeness and factual interpretation can still require evaluation or human review. One model approving another is not a proof of truth. The [DeepSeek JSON Output documentation](https://api-docs.deepseek.com/guides/json_mode/) also discusses the JSON instruction, empty output, and length considerations.

The same `LeaseKeeper` renews during a slow provider call. The client uses `timeout=45.0` and `max_retries=0`, disabling automatic SDK retries so multiple requests are not hidden inside a single apparent attempt. The network timeout is not a hard kill for an entire function, and the 120-second unit deadline remains cooperative. Late output can be discarded; charges for an already issued request cannot be undone.

Install the optional dependency for this online path:

```bash
python -m pip install -r stages/13-long-horizon-harness/code/requirements.txt
```

In Bash or Zsh on Linux/macOS, configure:

```bash
export DEEPSEEK_API_KEY="your_key_here"
export DEEPSEEK_MODEL="your_available_model_id"
```

In Windows PowerShell, use:

```powershell
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="your_available_model_id"
```

Windows CMD instead uses `set "DEEPSEEK_API_KEY=your_key_here"` and `set "DEEPSEEK_MODEL=your_available_model_id"`. Choose an ID available to your account using the [current provider documentation](https://api-docs.deepseek.com/); the placeholder is not a model name.

Create a separate online task and execute one unit at a time:

```bash
python stages/13-long-horizon-harness/code/deepseek_long_horizon.py create --db online-report.db --task-id live-001
python stages/13-long-horizon-harness/code/deepseek_long_horizon.py work --db online-report.db --task-id live-001
python stages/13-long-horizon-harness/code/deepseek_long_horizon.py inspect --db online-report.db --task-id live-001
```

Repeat `work` until the task is `completed` or `failed`; do not repeat `create`. Between steps, you may exit and use another terminal, provided it accesses the same database and supplies the key again. The Worker selects online units from the saved workflow type and reads the saved model setting. Live generation need not require exactly one repair: it may pass immediately or remain unsatisfactory when its allowance is exhausted. Failure information and accepted history stay in the database. Real requests require connectivity and available provider quota; the offline checks do not issue paid calls.

The surrounding orchestration is still a fixed draft-review-finalize workflow. The model participates in writing and assessment within its steps. Long-running work does not require fully autonomous planning, although a work unit could also contain the bounded Agent loop introduced earlier. Recovery supports the chosen business process; naming the surrounding component a harness does not turn every ordinary function into an Agent.

## 12. Check your understanding by choosing a failure location

At the beginning, the report depended on one process staying alive. Now, provided retained storage remains accessible, another process can distinguish committed work from work without an accepted result and obtain a fresh claim to continue. The class count is not the achievement; that distinction is.

Try three questions. Why does review remain the next step if the Worker exits after saving the draft but before printing success? Because the database commit, not the print, defines completion. Why is an old process rejected after a same-named replacement takes over? Because eligibility binds to this claim's token, not just its name. Why do five result records not prove five function executions? Because a computation can disappear before its result is committed.

Run the executable checks:

```bash
python stages/13-long-horizon-harness/code/checks.py
```

Beyond normal delivery, the checks terminate child processes and inject both process exit and database failure inside handover transactions. They verify that output insertion and progress advancement do not survive as half a result. Other checks exercise competing claims, stale tokens under a reused Worker name, expiry, background renewal, renewal failure, revision history, claim limits, rejection of a draft changed after review, and provider-output validation through a fake client. These establish execution rules, not the writing quality of an online model.

Keep the deployment scope honest. This SQLite ledger is for trusted processes on one host. It supplies neither tenant authentication, cross-machine scheduling, highly available storage, nor exactly-once external effects. Tasks retain a workflow version, and an unknown version is refused. Changing the order or meaning of steps requires a deliberate migration or a new version; an old step index must not quietly begin to mean a different operation. Database schemas are versioned too. An incompatible existing database is rejected, not cleared. Use a new database path for new experiments and design migrations separately for retained tasks.

A broader long-horizon Agent may also need to restore a code revision, rebuild its environment, verify earlier artifacts, and select the next manageable goal. [Anthropic's long-running Agent discussion](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) covers more of that surrounding support. Here we made one part concrete: retain facts that enable continuation, and accept work at explicit boundaries rather than extending a conversation indefinitely.

Once we can explain who is working, what has committed, why a revision happened, and what will actually be delivered, these mechanisms can support a real domain. [The next chapter](../14-capstone-enterprise-agent/README.md) returns to the support Agent and selects the capabilities that business actually needs.

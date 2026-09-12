# Stage 11: Does This Report Need Another Colleague? — Delegation, Handoffs, and Multi-Agent Systems

> Language: **English** | [简体中文](README.zh-CN.md)

[Stage 10](../10-evaluation-observability/README.md) gave us a way to explain individual failures and compare changes against repeatable cases. Now Lin, our product colleague, brings a request: “We want 20 support staff to try a reply assistant. Please establish the pilot's scope, its capability limits, and the questions we still need to resolve. I will use that assessment to prepare a report.” The inputs come from operations and risk. It is tempting to appoint an Agent for each department and a manager to supervise them.

Before scheduling the kickoff meeting, ask whether we need the team. One assistant with two short documents might already solve this problem. Adding experts can turn a simple answer into several paid paraphrases without adding useful evidence. We will follow the same pilot assessment through a single-controller implementation, specialist collaboration, failures, and a transfer of responsibility. The question from the previous chapter stays with us: what improved, and what did the extra machinery cost?

We begin with fixed records and deterministic specialist doubles. These let us observe who received which inputs and which operations the application accepted; they are not autonomous models in disguise. Later, a real DeepSeek supervisor selects specialists through tool calls, and each specialist makes its own model request. Nothing in this chapter connects to customer conversations, payments, or deployment APIs. The task is to assess the supplied records, not to launch the pilot.

## 1. Start with the job, not the org chart

The operations plan says that the proposed pilot covers 20 staff, has no measured outcomes yet, and permits reply suggestions but not refund execution. The risk policy adds a condition: using real customer conversations requires privacy clarification. Our immediate goal is to establish whether we have consistent material for an assessment draft. It is not to approve deployment or present a hoped-for improvement as an achieved result.

For rules this small, ordinary Python is enough. If a readable explanation needs a model, one model can receive the permitted records and explain them. Separating specialists becomes useful when the tasks genuinely need different information, instructions, tool permissions, maintenance ownership, or substantial independent work. We separate them here to study those boundaries. The comparison later will not deliberately handicap the single-controller implementation to make a team look clever.

In this chapter, a **multi-agent system** contains distinct execution roles with explicit responsibilities and inputs. Roles can share an underlying model or use different models. A fixed workflow can organize them, or a model can help decide whom to consult next. The relevant questions are what each role receives, what it returns, and how control moves—not whether its name includes “senior expert.” Three model calls inside one ReAct loop can still belong to one Agent.

These categories are not mutually exclusive. A subagent exposed as a tool looks like a callable capability to its manager, while internally it may run a model-and-tool loop of its own. Understanding the interface matters more than issuing certificates of authentic agency. [Anthropic's discussion of workflows and agents](https://www.anthropic.com/engineering/building-effective-agents) offers a useful way to reason about when dynamic control is needed rather than assuming it should be the default.

Suppose operations analysis and risk interpretation really are distinct responsibilities. The coordinator handles Lin's request and combines the answers; operations extracts plan facts; risk interprets the policy. We first need a clear assignment for each role. Otherwise, we cannot tell whether handing the task off improved anything.

## 2. An assignment needs a question and a return contract

“You are a highly competent operations expert” does not tell the recipient what to deliver. Should it count proposed participants, predict cost savings, or decide whether the pilot may launch? Without a concrete question, three pages of confident prose can still fail the task.

Our operations assignment asks for the proposed staff count, whether measured outcomes exist, and what refund authority the plan claims. Risk establishes the policy's refund boundary and whether the intended use of data requires privacy clarification. Neither role may approve deployment. Refund authority deliberately appears in both records: if the plan and policy disagree, we want that disagreement preserved rather than smoothed into an agreeable summary.

The return contract must also represent missing information and execution failure. In [`team.py`](code/team.py), a specialist returns a `Finding` rather than an unstructured answer alone:

```python
@dataclass(frozen=True)
class Finding:
    status: str
    summary: str
    facts: dict[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
```

The allowed statuses are `ok`, `needs_input`, and `failed`. They distinguish a normally returned finding, insufficient inputs, and the absence of an accepted execution result. The summary is readable explanation; facts are values downstream code can inspect; evidence IDs identify the supplied records used. An operations result contains fields such as `staff=20` and `measured_results=False`. A risk result includes `privacy_review_required`.

An `ok` envelope is not a truth certificate. A structurally valid answer with a citation can still misinterpret its source. The runtime checks the result type, allowed status, nonempty summary, and JSON size. The application checks domain fields separately. In the live example, the small factual fields are also compared with the permitted input records. More open-ended analysis still needs evaluation; naming a field `facts` does not make its contents factual.

The specialist does not get to announce its own authenticated sender identity. The runtime knows which registered handler it actually invoked, so it wraps the finding in an `AgentMessage` with the agent name, run ID, and request ID. The run ID groups this assessment; the request ID identifies one consultation within it. This keeps “risk actually returned this” distinct from “the coordinator guessed what risk would say.” It is an application-owned envelope, not a cryptographic signature or a remote authentication protocol.

With a return contract in place, the next question is what to send. We should not answer it by photocopying the entire filing cabinet.

## 3. Give each colleague the pages they need

The application's context also contains an internal note unrelated to the assessment. We use a synthetic `private_note` field—not a real secret—to see whether it crosses the boundary. The application-held data, the operations view, and the risk view should not automatically be identical.

Applying Stage 07's context-selection idea, the host fixes the input keys for each recipient. [`scenario.py`](code/scenario.py) contains this mapping:

```python
CONTEXT_KEYS = {
    "operations": ("brief", "operations_note"),
    "risk": ("brief", "policy_note"),
    "privacy": ("brief",),
}
```

The brief contains only the common goal and whether the proposed test uses real conversations. Operations receives its plan, risk receives the policy, and a privacy recipient starts with the common brief. These are application choices. A model cannot expand its view by adding `private_note` to a tool argument.

Selecting that smaller view is **context projection**. The actual projection is short:

```python
def project_context(context: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return json_copy({key: context[key] for key in keys if key in context})
```

Why call `json_copy()` instead of merely constructing a new outer dictionary? The values contain nested dictionaries. A shallow copy would still let two specialists refer to the same brief; one could modify it while the other is reading it. Serializing and reading back this bounded JSON data creates independent copies. The helper also rejects non-JSON values, non-finite numbers, and data above its character limit rather than silently truncating required material. That limit bounds accepted and forwarded data, not arbitrary handler memory consumption.

There is another channel to consider. Filtering `context` does little good if an unrestricted assignment string contains the very secret we removed. In this example, assignments are registered by the host too: the supervisor selects a specialist but cannot supply arbitrary subtask prose. An open-ended system must separately consider assignment text, histories, attachments, and references. One filtered dictionary is not complete information-flow security.

All these handlers still run inside one Python process. Projection prevents accidental sharing through this interface; it does not stop malicious code from inspecting process memory. Authentication, tenant isolation, and access checks at the source system also remain outside this small helper. Once we have decided which pages may be sent, we still need to decide whether this caller may request that work at all.

## 4. An internal colleague is not an authorization shortcut

Stage 09 established that knowing a tool's name does not grant permission to use it. The same reasoning applies here. An analysis role may request a policy interpretation without being allowed to launch production changes. Asking another Agent to repeat the request must not manufacture that missing permission.

Our authorization rule includes the operation, caller, and target. A host-created `Principal` describes the user or service represented by this run. Its roles come from a trusted application entry point, never from model-generated arguments. One policy entry reads: an `analyst`, acting through the current `coordinator`, may delegate a subtask to `operations`.

```python
("delegate", "coordinator", "operations"): frozenset({"analyst"}),
```

That is an entry in the policy dictionary. The check asks whether the principal's roles overlap the roles granted on this specific edge:

```python
def allows(self, principal: Principal, kind: str, caller: str, target: str) -> bool:
    return bool(principal.roles & self.grants.get((kind, caller, target), frozenset()))
```

An unregistered combination produces an empty set and is denied. Permission to delegate does not imply permission to hand off control; we will make that distinction concrete shortly. Even a valid analyst role cannot keep operating under the name of a coordinator that no longer owns this run.

There is still an inner boundary. When a specialist uses a real tool, that tool must check the business permissions it requires. Entering a risk specialist is not permission to execute a refund. The local fixtures here do not implement enterprise identity or a tenant-aware database. They make the team-entry rule executable without pretending that it replaces those systems.

We now have assignments, input views, and authorized collaboration edges. At last, the colleagues can do some work instead of attending another architecture meeting.

## 5. The first consultation: help me, then return the result

The coordinator asks operations to extract the plan and risk to interpret the policy, then combines both answers itself. This is **delegation**: the recipient performs a bounded subtask and returns. It resembles Stage 01's tool use, except that the callable capability may now contain another model.

[`demo.py`](code/demo.py) creates one run and dispatches the two consultations. The dispatch and merge are separate operations:

```python
messages = runtime.fan_out(caller="coordinator", targets=("operations", "risk"), parallel=args.parallel)
```

```python
assessment = from_messages(messages)
```

`fan_out()` distributes the independent subquestions. Its default mode is sequential, not concurrent. `from_messages()` combines the returned findings into a domain assessment; it does not allow whichever dictionary arrives last to overwrite the other. The message contract is the interface between execution and interpretation.

Run this from the repository root with Python 3.10 or later. The offline path needs no model credentials:

```bash
python stages/11-multi-agent/code/demo.py
```

The output includes requests `pilot-001:1` and `pilot-001:2`. The first carries plan facts such as the 20 proposed participants and absence of measured results. The second carries the refund restriction and whether privacy clarification is required. The final assessment is `ready_for_draft`: enough consistent material exists to prepare an assessment draft. It does **not** authorize deployment. The owner remains `coordinator` before and after both consultations.

Each recorded event includes correlation IDs, caller, target, visible field names, status, and elapsed time. It does not capture complete prompts, result bodies, or the private note. This applies Stage 10's observability discipline to team boundaries. The events are merged in request order; they are not a full nested span implementation or a promise about completion order during concurrency.

A successful consultation is the easy case. The more interesting question is what the coordinator does when one colleague fails to answer—or when two answers disagree.

## 6. No answer is not the same as an answer of “no”

First remove the policy record. Then, in a separate run, make the risk handler simulate a service failure. Both prevent a complete assessment, but they mean different things. Missing evidence calls for additional input. Execution failure calls for a failure report or a separately justified recovery action. Neither is evidence that the policy forbids the proposal.

```bash
python stages/11-multi-agent/code/demo.py --case missing
python stages/11-multi-agent/code/demo.py --case failure
```

The first run produces `needs_input`; the second produces `failed`. In both, the successful operations finding remains available. The runtime converts specialist exceptions to controlled error codes without passing the original exception text to a model, because error bodies can contain private requests or credentials.

The domain merge checks execution status before interpreting business facts:

```python
if any(item.status == "failed" for item in items):
    return Assessment("failed", "Assessment incomplete: a specialist failed, not a policy rejection.", sources)
if any(item.status != "ok" for item in items):
    return Assessment("needs_input", "Assessment incomplete: required information is missing.", sources)
```

There is deliberately no “one answer is missing, so make an educated guess” branch. Partial success means preserving useful partial evidence, not relaxing the final acceptance conditions. Whether retrying is useful and safe remains the Stage 09 question. This runtime neither retries every failure automatically nor hides failure in an empty string.

A subtler problem appears when both specialists return normally but the plan permits refunds while the policy prohibits them:

```bash
python stages/11-multi-agent/code/demo.py --case conflict
```

This stops at `conflict` and asks for reconciliation. The two records disagree about the same permission fact; a majority vote would not establish which policy applies. Conversely, “a pilot seems worthwhile” and “additional controls are needed” may be compatible judgments about different dimensions. Real applications must distinguish factual contradiction, outdated sources, and ordinary tradeoffs before deciding to clarify, retrieve again, or ask a person.

Adding a critic can supply another opinion, but that critic has its own inputs, costs, and failure modes. Two models reading the same incorrect record can agree without providing independent evidence. We use precise field checks where they are possible, and leave richer semantic review to an evaluator with explicit criteria and bounded iterations. Naming the third colleague “chief reviewer” does not settle the matter.

Now that the results have useful meanings, Lin asks a practical question: if the two consultations are independent, can we ask both at once?

## 7. Two colleagues can work together without sharing a pen

Operations reads the plan. Risk reads the policy and intended data use. Neither needs the other's answer, so those consultations can overlap. The final merge does need their answers; launching the merge in the same independent batch would violate the dependency we just identified.

**Fan-out / fan-in** describes the structure of distributing work and collecting its results. **Concurrency** describes overlapping execution. The default demonstration uses the first without the second. Add `--parallel` to actually submit both handlers to a thread pool:

```bash
python stages/11-multi-agent/code/demo.py --parallel
```

Before launching the batch, the application checks all recipients and permissions, then reserves its delegation budget in one operation. A budget allowing only one consultation cannot start the first handler and discover the second is unaffordable afterwards. This is whole-batch admission, not an execution transaction: once work starts, one specialist can succeed while another fails.

The execution uses the standard library's `ThreadPoolExecutor`:

```python
with ThreadPoolExecutor(max_workers=self._limits.max_workers) as pool:
    futures = [pool.submit(self._invoke, spec, context) for spec, context in prepared]
    outcomes = [future.result() for future in futures]
```

The first line caps the active pool size. The second submits the whole admitted batch before the third waits for results in submission order. It is not “submit one, wait for it, then submit the next.” Each handler gets its own nested JSON copy. Only the driving coordinator thread updates the saved messages and events, so the specialists never race to modify a shared output dictionary. The checks use a barrier requiring both handlers to reach the same point, rather than inferring concurrency from a diagram.

If operations takes two seconds and risk takes three, sequential waiting is roughly five seconds; overlapping them can approach three, plus dispatch and merge overhead. These are illustrative assumptions, not measured model performance. For the near-instant offline functions, thread scheduling may make the concurrent version slower. Concurrency does not automatically reduce the number of model calls or their token cost either.

Timeout semantics need special care. A `Future` wait timeout does not kill an executing Python function, and leaving this pool's `with` statement waits for running work; the [official documentation](https://docs.python.org/3/library/concurrent.futures.html) describes this behavior. Our run deadline rejects new invocations and late results. It is a cooperative boundary, not hard termination. Real network handlers still need appropriate request timeouts and cancellation behavior. This chapter does not claim to make an arbitrary permanently stuck function stop.

## 8. This time, please continue the conversation yourself

Lin changes the proposal: “We want to test with real support conversations.” The risk finding now requires privacy clarification. The coordinator could simply relay the question, but if a specialist should conduct the follow-up using its own focused procedure, we can transfer the active role.

That is a **handoff**. Unlike a consultation that returns to its caller, the recipient becomes the active owner of the current run. Here a privacy handler asks about consent and redaction controls. It does not approve data use and does not access real customer conversations.

```bash
python stages/11-multi-agent/code/demo.py --case handoff
```

The run starts with the same two delegations. When the host receives an assessment of `needs_review`, it requests a handoff and the owner changes to `privacy`. The recipient gets the common brief and the specifically permitted risk findings—not the operations record, private note, or complete conversation history. Merely changing a name without sending the reason for clarification would leave the new owner asking Lin to start again.

After checking the target, permission, and budget, the runtime actually changes its control state:

```python
self._owner = target
self._handoff_path.append(target)
```

Every subsequent continuation operation checks that state:

```python
def _check_owner(self, caller: str) -> None:
    if self._closed or caller != self._owner:
        raise OwnershipError("only the active owner may continue this run")
```

The demonstration makes the former coordinator try to finish the reply and prints `former owner: rejected`. The privacy handler then supplies the clarification question. This is stronger than returning a dictionary with a different owner label: the change affects which later calls the runtime accepts.

In this implementation, ownership changes before the receiving handler runs. If that execution fails, the target remains the owner and the host has an explicit failure result. It does not silently restore the former owner. A fallback would require another explicit policy. Also, finishing here closes this response invocation; it does not implement persistent multi-turn support or a cross-process ownership service.

The represented user and roles do not change during the handoff. A specialist's distinct context is not additional authority on the user's behalf. If it invokes an external tool, that tool must apply its own checks. Otherwise, a harmless-looking transfer can become a way of laundering a forbidden operation through another Agent.

## 9. Stop the team from referring the question around forever

Delegation works, handoff works, and a new risk appears: a small question becomes an endless internal meeting. A coordinator asks operations, operations recommends risk, and risk sends the problem back to the coordinator. If every role starts with a fresh budget, each looks restrained locally while the overall system keeps going.

The budget therefore belongs to the **whole run**. `max_delegations` limits specialist consultations; `max_handoffs` separately limits changes of active ownership. Once an authorized request is admitted, it consumes its budget even if the handler fails. A rejected over-budget batch launches nothing. Denials still produce metadata events, so we can distinguish “not permitted to call” from “called and failed.”

The actual delegation reservation is straightforward:

```python
if self._delegations + count > self._limits.max_delegations:
    raise BudgetExceeded("delegation budget exhausted")
self._delegations += count
```

Only the driving thread updates these counters. The concurrency cap from the previous section limits how much admitted work runs simultaneously; it does not replace a total budget. Four consultations can be sequential or overlap in pairs, but neither scheduling choice permits a fifth.

For handoffs, we also remember the owners visited during this run and reject a return to an earlier owner. A path `A → B → C → A` is therefore rejected. This is a conservative rule for this example, not a universal ban on review loops. A legitimate revisit needs a bounded workflow with explicit iteration semantics. The ordinary specialists here receive no runtime handle and cannot recursively delegate; adding nested teams requires passing the overall budget into them rather than resetting it at every level.

Model requests need a separate account. A supervisor decision and the model calls inside its specialists all cost requests; a delegation counter is not a token meter. The live adapter gives all roles one shared request budget, limits generated output, and records usage reported by the service. Missing usage stays unknown rather than becoming a suspiciously precise cost estimate.

## 10. Give the single controller and team the same examination

We can finally test the choice made at the beginning. The team has introduced envelopes, projection, permissions, merging, and ownership rules. Is that complexity justified? For this small rule-based task, the honest starting point is the same inputs, same analysis functions, and same acceptance conditions in every configuration.

[`evaluation.py`](code/evaluation.py) compares a single ordinary controller that applies both rules directly, sequential specialist delegation, and concurrent specialist delegation. It does not rename deterministic functions as different models or deliberately remove the policy check from the baseline. The four cases are:

| Input situation | Required behavior |
| --- | --- |
| Complete, consistent plan and policy | Prepare an assessment draft, without approving deployment |
| Missing policy | Ask for the missing input; do not guess permissions |
| Conflicting refund authority | Preserve the conflict for reconciliation |
| Proposed use of real conversations | Request privacy clarification |

```bash
python stages/11-multi-agent/code/evaluation.py
```

The program produces 12 comparison rows. It checks the assessment status, source IDs, and absence of the synthetic private note in the final result, and records actual local elapsed time and specialist-boundary call counts. All three implementations should pass. That demonstrates preservation of these behaviors, not superior intelligence from multiple Agents. The single controller has no specialist-message boundary; the team adds two consultations. Whether that overhead is worthwhile depends on whether the organizational and data boundaries are actually needed.

Offline model requests are zero; model tokens and cost are `null`. Thread-test timings do not predict live-model latency. A real comparison should give the single Agent and team equivalent permitted information, record model and prompt versions, repeat the same fixed cases, and separately evaluate factual accuracy, evidence coverage, appropriate refusals, unnecessary calls, latency, and measured cost. Independent research tasks may benefit from parallel specialists, but gains from another workload are not results for this one. [An engineering account of a real multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) is useful design context, not a benchmark certificate for this demonstration.

Try removing the conflict check and rerunning the checks. The final response may still read smoothly, but the system no longer preserves agreement on a permission fact. Stage 10's distinction between attractive final text and correct behavior becomes tangible here.

## 11. Add real models without letting them rewrite the rules

The deterministic specialists made control behavior reproducible, but they do not establish that a live model can interpret the inputs. [`deepseek_team.py`](code/deepseek_team.py) gives the supervisor, operations specialist, and risk specialist separate real model calls. They may use the same model ID, but they have different instructions, permitted context, and return contracts. Privacy transfer is still selected by host policy, and its clarification handler remains deterministic; it is not advertised as another online specialist.

The supervisor initially receives only the public goal and one `ask_specialist` tool. Its sole argument is `specialist`, restricted to `operations` or `risk`. It cannot choose the caller, identity, context keys, arbitrary assignment prose, or the next owner. The host checks the tool name and arguments rather than treating the provider-side schema as permission:

```python
if call.type != "function" or call.function.name != "ask_specialist":
    raise ProviderError("unknown tool name or type")
```

All call IDs in a batch must be nonempty and unique, including across previous rounds. Only then does the adapter delegate through the same runtime and return each observation with the provider's `tool_call_id`. This is the Stage 01 model–tool loop with another model call behind a tool. The outer policy and budget remain in force. The current request format is documented in [DeepSeek's tool-call guide](https://api-docs.deepseek.com/guides/tool_calls/).

A specialist returns a JSON object containing the agreed status, summary, facts, and evidence IDs. JSON mode does not validate business truth. Since this fixture's facts are simple, the application compares counts, boolean conditions, and source IDs against the allowed records. Inventing 200 participants, citing an unknown source, or substituting numeric `0` for boolean `false` is rejected. The prose summary remains generated text: accepting its factual fields does not prove that every sentence in its analysis is correct.

A supervisor can also skip consultations and say “everything approved.” The adapter requires both necessary observations before accepting a final turn, then applies the deterministic domain merge to produce the application decision. On success it separately exposes `model_commentary_unverified`: an unverified model explanation, not the authoritative decision. When the assessment is incomplete, conflicting, or failed, that free-form commentary is withheld so it cannot casually talk around the stop condition.

All roles share `ModelGateway` with at most eight attempted requests. The supervisor has at most four decision rounds and at most two tool calls in one round. Client-level retries are disabled, request timeouts and output limits are explicit, and empty, truncated, or abnormally ended responses are not treated as complete results. The adapter explicitly selects non-thinking mode rather than silently mixing another continuation protocol into this example; see the [DeepSeek Chat Completions reference](https://api-docs.deepseek.com/api/create-chat-completion/). Request timeout settings still do not turn Python threads into killable execution units.

Install the optional client, then select a model actually available to your account. This path consumes your service quota. The key below is a placeholder, never a value to commit:

```bash
python -m pip install -r stages/11-multi-agent/code/requirements.txt
```

In a macOS or Linux shell:

```bash
export DEEPSEEK_API_KEY="your_key_here"
export DEEPSEEK_MODEL="your_available_model_id"
python stages/11-multi-agent/code/deepseek_team.py
```

In Windows PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="your_available_model_id"
python stages/11-multi-agent/code/deepseek_team.py
```

Windows CMD uses `set "DEEPSEEK_API_KEY=your_key_here"` and `set "DEEPSEEK_MODEL=your_available_model_id"` before the same Python command. Adding `--real-data` changes a boolean in the synthetic proposal to exercise privacy clarification; it uploads no real conversation data. Output includes attempted request count and token usage per returned response, with unavailable values left unknown. A live model may fail or take a different path; observing and evaluating that behavior is separate from proving the runtime's offline invariants.

## 12. What changes when we use a framework or a remote colleague?

Once the responsibilities are clear, a framework becomes a way to implement a known control pattern. For example, OpenAI Agents SDK's `Agent.as_tool()` lets a manager consult a subagent and retain control, while `handoffs` lets another Agent take over the current conversation. These correspond to our delegation and handoff distinction, but our message types and budgets are not drop-in SDK objects. The [official orchestration guide](https://openai.github.io/openai-agents-python/multi_agent/) describes the two patterns.

A framework also cannot infer which conversation history the recipient should see. Its transfer and history-filtering rules need to be inspected and combined with the application's data policy; the name `handoff()` is not a promise of this example's minimal handoff bundle. The [SDK handoff documentation](https://openai.github.io/openai-agents-python/handoffs/) describes its input-filtering facilities. This chapter does not install or run that SDK; this is a mapping of concepts, not an additional tested integration.

Now suppose another team maintains risk analysis in a separate system. We cannot call its Python handler directly. We need to locate its service, discover what it accepts, establish identity, and obtain results or status updates. **A2A (Agent2Agent)** standardizes interactions between such independent Agent systems.

For the pilot assessment, an Agent Card can describe the remote risk service's capabilities, interfaces, and authentication requirements. A Message carries a request or reply. Work that cannot finish immediately can be represented by a Task with an ID and lifecycle; a produced risk assessment can be returned as an Artifact. An immediate response can instead be a Message—every interaction need not create a long-running task. The remote system need not expose its internal model calls, memory, or tools. The [core concepts](https://a2a-protocol.org/latest/topics/key-concepts/) and [specification](https://a2a-protocol.org/latest/specification/) define the actual wire objects; our `AgentMessage` is not one of those wire formats.

A Card advertises capability, not authorization. Its `skills` are capability descriptions, not automatically Stage 08 `SKILL.md` packages. The host still verifies the service identity, constrains approved destinations, sends only allowed data, and relies on server-side authorization. MCP and A2A are complementary here: a risk Agent might use a policy-retrieval tool through MCP and return an assessment to another Agent system through A2A. We have not built a remote A2A service in this chapter, so its offline checks do not demonstrate protocol interoperability or cross-service security.

## 13. Lin has an assessment; now where is the report file?

The task now has a traceable division of responsibility. Operations extracts plan facts, risk states constraints, and the coordinator preserves sources and handles missing or conflicting findings. When follow-up truly belongs with another specialist, the active role moves explicitly. Each consultation has an allowed caller, a defined view, a result contract, and a budget. A single controller remains a valid choice when those extra boundaries are unnecessary.

Run the boundary checks and look for the difficulties from the story, not just successful imports:

```bash
python stages/11-multi-agent/code/checks.py
```

They exercise missing records, failing specialists, late results, unauthorized edges, nested-context mutation, and duplicate model call IDs. They verify actual overlapping execution, rejection of a former owner after handoff, and preservation of the same domain behavior across the comparison. Provider checks use a fake client: they need no API key and are not evidence of live model quality.

Lin reads the assessment and asks, “Can you turn this into a report, check it, and give me the file?” We know who is responsible, but text is about to become files and executable work. Where those files belong, what may process them, and which output may leave the workspace are the questions for [Stage 12: Workspace and Execution Boundaries](../12-agent-workspace-sandbox/README.md).

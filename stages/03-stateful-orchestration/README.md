# Stage 03: The Brief Is Written. Why Can't We Deliver It Yet? — Making State and Control Flow Explicit

> Language: **English** | [简体中文](README.zh-CN.md)

[Stage 02](../02-workflows-routing-planning/README.md) gave Lin's travel-practice page a way to handle two cities. It could obtain the Tokyo and Paris records, convert temperatures when requested, and produce a brief. If a source failed, it could retain completed results and change the remaining plan. Lin now adds a delivery rule: “Check it before showing it. Neither city should disappear, the units must be right, and readers must know this isn't live weather. Fix a rejected draft, but please don't spend tomorrow fixing it too.”

The challenge is no longer simply whether a tool can run. Which draft are we holding? Was that the draft we checked? Do we need to query the cities again just to fix a missing sentence? When the revision allowance runs out, is it acceptable to return the unfinished draft as though it passed? The application needs a clear account of its current progress, not a model's reassuring “I remember.”

We will carry the same weather brief through collection, drafting, checking, revision, and delivery. First we will make the process explicit in ordinary Python, then run the same work with LangGraph. Finally, we will express the model/tool loop from Stage 01 using the same state-and-transition ideas. The purpose is to make execution understandable, not to rename familiar functions until they sound more architectural.

## 1. Find the problem in the draft before learning graph terminology

Lin selects Tokyo and Paris and enables Fahrenheit. The first draft reads:

```text
Tokyo: 18.0°C / 64.4°F, cloudy.
Paris: 12.0°C / 53.6°F, light rain.
```

The numbers are correct, but the source notice is missing. On a travel page, that omission could make the records look like a current weather report. This exercise requires the sentence “Fixed teaching data, not live weather.” The draft needs a revision; the two records we already retrieved do not need to be fetched again merely because the wording is incomplete.

Imagine doing this work on paper. Collect the records, write the draft, and check it. Deliver an acceptable draft. Revise an unacceptable one while revisions are still allowed, then check the new version. If it remains unacceptable when the allowance is exhausted, keep the draft and say that it did not pass. There are two different ways to finish: successfully deliver, or stop trying. A stopped program has not necessarily completed its task.

That gives us a plain-language starting point for **stateful orchestration**: the application carries a clear worksheet and arranges for different steps to continue the work. The worksheet says what is available now; the process says what happens next. Dictionaries, functions, and conditions are already enough to express this. We are making their relationship explicit.

You can run the process without a framework. The `run_plain()` function in [`workflow.py`](code/workflow.py) uses a normal loop and the same checks we will use throughout the chapter. With Python 3.10 or later, run this from the repository root:

```bash
python stages/03-stateful-orchestration/code/workflow.py --language en
```

The output records the missing notice, the revision, and another check, then returns a labeled two-city brief. No model request is made. Understand which draft changed and why it needed another check before assigning technical names to the pieces.

## 2. What belongs on the worksheet?

Pause just after the checker finds the omission. To revise correctly, the next step needs the selected cities, the Fahrenheit option, the collected records, the current draft, the review feedback, and the number of revisions already made. That is this execution's **state**: the data needed to continue this work, not everything the application happens to know.

The `initial_state()` function in [`workflow.py`](code/workflow.py) checks the city and unit options before creating the worksheet. Its returned dictionary is:

```python
return {
    "cities": list(cities), "include_fahrenheit": include_fahrenheit, "language": language,
    "readings": [], "draft": None, "review": None, "revisions": 0,
    "events": [], "answer": None, "status": "working",
}
```

`readings` starts empty because collection has not happened. `None` in `draft` and `review` means that no draft or review exists yet. `revisions=0` means no revision has been performed; it does not mean the draft must be bad. `answer` is filled only after the delivery check succeeds. `events` is a small history we deliberately retain to explain the path.

Current state and history have different jobs. `draft` holds the current document, and `review` holds its current assessment. Neither is an archive of every version. `events`, on the other hand, is intentionally cumulative. Whether to replace or accumulate a value follows its meaning, not merely whether its Python type is a list or dictionary.

The worksheet is not automatically the model's context either. A checker needs the revision count; a model may not. Application state can contain internal progress while a model receives only selected inputs. The live example later sends the message history, not a dump of every graph field.

There is one further distinction. Business state does not secretly contain the Python program counter. The scheduler knows which node is active. Printing this dictionary does not save the process or make an interrupted execution resumable. First we will organize the data; then we will organize the transitions that use it.

## 3. Return a change slip rather than carrying away the whole worksheet

After collecting the records, a useful report is “here are the readings,” not a fresh copy of the city selection, revision allowance, draft, and complete history. A function can follow the same rule: read the current state and return only the fields it changed. A function doing one meaningful piece of work can serve as a **node**.

`ReportNodes.collect()` reads each selected city, checks the returned city, finite temperature, and source information, and finally returns only:

```python
return {"readings": readings, "events": ["collected requested records"]}
```

This is a **partial update**. It updates `readings` and contributes a new event. It does not request deletion of `cities`, and it does not have a reason to increment `revisions`. Omitting a field normally means leaving its value alone, not clearing it. Partial updates make responsibilities visible, but they are not field-level authorization: this convention alone does not prevent a node from returning other fields.

The drafting node then uses the saved readings and unit selection to create the display rows. The first draft has a visible defect by default: it omits the source notice. We can inspect the actual problem instead of interpreting a mysterious `draft-v0` marker. Here is the method:

```python
def write_draft(self, state: State) -> State:
    notice = NOTICES[state["language"]] if self.draft_style == "complete" else ""
    return {
        "draft": {"rows": expected_rows(state), "notice": notice},
        "review": None, "events": ["wrote draft"],
    }
```

`expected_rows()` calculates Fahrenheit from the collected Celsius values rather than hard-coding 64.4. The draft contains `rows`, which will appear on the page, and `notice`, which identifies the data. Returning `review=None` is also deliberate: a new draft invalidates the old assessment. To clear a value, we must explicitly return `None`; omitting `review` would leave the old value in place.

A node need not be one line long, nor should it do everything. Collecting this small brief's readings is a meaningful step; checking one draft is another. Making `strip()` its own node rarely clarifies the process. A better sizing question is whether a failure in the node would correspond to a piece of work we can name and explain.

## 4. Replace the draft, but keep adding to the account of what happened

A change slip needs a merge rule. Suppose we currently have `draft=old draft` and `events=[records collected]`. The drafting node returns `draft=new draft` and `events=[draft written]`. Replacing the draft makes sense. Replacing the events would erase the collection record.

Different fields therefore need different update behavior. The default is replacement. For fields that genuinely accumulate, we provide a merge function called a **reducer**. Here the name means something quite ordinary: given the old value and this new contribution, what should the next value be? Events use:

```python
def append_events(left: list, right: list) -> list:
    return [*left, *right]
```

The starred expressions put the elements of both lists into a new list without changing either input. Existing `['collected']` plus the new `['drafted']` becomes `['collected', 'drafted']`. A node contributes its own event, not another copy of the entire past.

The relevant merge code in [`state_graph.py`](code/state_graph.py) works on `candidate`, an independent copy of the current state:

```python
candidate = deepcopy(dict(state))
for key, value in update.items():
    right = deepcopy(value)
    reducer = reducers.get(key)
    candidate[key] = reducer(candidate[key], right) if reducer and key in candidate else right
return deepcopy(candidate)
```

A field without a reducer, such as `draft`, is replaced as a whole. There is no automatic deep merge of its nested `rows` and `notice`. Returning only `draft={'notice': '...'}` would not preserve the old rows under this rule. Conversely, returning old events plus the new event to an append reducer would append the old events again. Field meaning, returned updates, and reducer choice must agree.

The complete merge is staged before the candidate becomes the new state. If one reducer fails, the original state does not end up with half the fields changed. This is a guarantee about an in-memory update, not a transaction over the outside world. Copying dictionaries cannot undo a file write or external request that the node already performed.

The small handwritten engine also gives nodes and routing functions deep copies, reducing accidental mutation through nested lists. That is an implementation choice in this engine, not a general promise that LangGraph isolates every object, and certainly not a security sandbox. The business functions themselves still use the clearer discipline: read inputs and return new values.

## 5. Check this draft, not whether it has already had a turn at revision

With updates defined, the checker can read an actual draft. Our acceptance rule is deliberately narrow: the display rows must match the collected cities, temperatures, and requested units; the source notice must match the page's required sentence. We are not asking a model to grade itself or making “reject once, then accept” the rule.

`review_issues()` inspects `rows` and `notice` and returns concrete failures. The checking node stores those issues together with the content it inspected:

```python
def check_draft(self, state: State) -> State:
    issues = review_issues(state)
    return {
        "review": {"passed": not issues, "issues": issues, "checked_draft": deepcopy(state["draft"])},
        "events": ["checked draft: " + (", ".join(issues) if issues else "accepted")],
    }
```

`passed` reports whether these explicit rules passed. `issues` identifies failures. `checked_draft` is a copy of the document being assessed. Think of signing off on a specific document, not signing a blank slip that approves all future documents.

For the first draft, the issue is `missing_fixed_data_notice`. Revision supplies the notice, increments the revision count, and clears `review`. The new draft then goes through checking again. Revision reads the existing `readings`; it does not query Tokyo and Paris again. Separating data collection from editing makes unnecessary repeated work much easier to see.

Three modes make the rule observable. `missing-notice` is the default defect, `complete` begins with an acceptable draft, and `stubborn` deliberately keeps omitting the notice even during revision. No number of editing turns makes the third draft correct. That mode tests stopping behavior; it is not a prediction of what a real model will do.

This checker does not solve general writing quality. The document is structured page data, and the checker compares explicit fields and a prescribed sentence. It would not be an adequate truth checker for news or a complex analysis. Free-form output requires acceptance rules appropriate to that output; a convenient equality test is not a universal evaluator.

## 6. After checking, choose from routes the application has declared

Checking records a result. Choosing what follows is a separate responsibility: deliver an acceptable draft, revise while allowed, otherwise keep it and stop. The connections between these steps are **edges**. A fixed edge has one destination. A conditional edge examines the updated state and selects from declared destinations.

`ReportNodes.route_after_check()` selects a route without editing the draft:

```python
def route_after_check(self, state: State) -> str:
    review = state["review"]
    if review is None or review["checked_draft"] != state["draft"]:
        raise ValueError("The current draft has not been checked")
    if review["passed"]:
        return "accept"
    return "revise" if state["revisions"] < self.max_revisions else "hold"
```

`max_revisions` belongs to application configuration, not to the draft or model output. A value of 1 permits one revision. The first check and the check after revision are two checks, not two revisions. A zero revision allowance still permits checking and delivering an already-correct first draft.

Now the complete route has a concrete meaning at every stop:

```text
START → collect → write_draft → check_draft
                                  ├─ accept → publish → END
                                  ├─ revise → revise_draft → check_draft
                                  └─ hold   → hold → END
```

The cycle is `check_draft → revise_draft → check_draft`. `START` and `END` are structural entry and terminal markers, not functions that fetch data or write text. `hold` also reaches `END`, but sets `status='needs_attention'` and leaves `answer=None`. It does not represent successful delivery.

The conditional edge uses a small mapping:

```python
builder.add_conditional_edges("check_draft", nodes.route_after_check,
                              {"accept": "publish", "revise": "revise_draft", "hold": "hold"})
```

`accept` can lead to `publish`, and `revise` to `revise_draft`. A new string returned by the router cannot conjure up an undeclared node. This is the finite routing idea from Stage 02, now applied to steps within a process.

The publication node also confirms that the checked draft has not changed and rechecks these narrow content rules. In this example, `publish` means turning accepted data into return text; it does not upload a page or send a message. Node names, business outcomes, and actual external effects must not be confused.

## 7. How does the route become executable?

We can now introduce a **graph** as the arrangement of these nodes and edges that the scheduler will follow. It is not another model. Our `MiniStateGraph` stores functions, fixed routes, conditional routes, and reducers, then builds an executable object.

During `compile()`, the small engine checks the entry point, node names, destinations, missing outgoing rules, and nodes unreachable from the entry. It also checks that each node has at least one possible path to `END`. This catches misspellings and completely closed cycles, but does not prove that the routing function will ever choose an exit.

For example, a route table might allow both `again` and `done` while the function always returns `again`. The diagram has an exit, but execution never takes it. That is why the engine also has `max_steps`. It counts completed node executions, not revisions or model calls. After reaching the bound, the engine will not start the next node.

Once a node starts, its central work is still ordinary Python:

```python
update = self.nodes[current](deepcopy(state))
candidate = merge_update(state, update, self.reducers)
```

The engine adopts the merged state, records the completed node, and then chooses the next destination from that new state. Graph execution did not abolish loops; it separated work from the increasingly tangled conditions that decide what follows. This miniature engine runs one node at a time and implements no parallel fan-out.

Run the route:

```bash
python stages/03-stateful-orchestration/code/state_graph.py --language en --show-updates
```

The default path is `collect → write_draft → check_draft → revise_draft → check_draft → publish`: six node executions producing a labeled brief. A `StepSnapshot` retains the node name, its partial update, and a detached copy of the merged state so that we can examine which step changed the review result.

If a node or merge fails, `GraphExecutionError` carries the failure location, previously completed nodes, and the last successfully merged state. It does not fabricate a completed update from local variables in a failed node, and it does not undo external work. If collection reads one city but raises while reading the second, it has not yet submitted `readings`. The whole collection node cannot be marked successful. A design needing per-read progress should use smaller commit units.

Node granularity matters partly because it determines where the program can observe and accept a state change.

## 8. Move the same work to LangGraph before changing anything else

Now change the scheduling implementation, not the problem, acceptance rules, or editing policy. **LangGraph** provides a state-graph execution system. It receives the same worksheet and ordinary functions. Two contracts matter first: which fields exist, and how an update to each field is combined with its current value.

[`langgraph_workflow.py`](code/langgraph_workflow.py) describes state with `TypedDict`. At runtime this is still a normal dictionary. Type hints help editors and checking tools understand fields; they do not automatically validate every input or create default values. [Python's TypedDict documentation](https://docs.python.org/3/library/typing.html#typing.TypedDict) explains that distinction. We still use `initial_state()` to validate options and construct initial values.

```python
class ReportState(TypedDict):
    cities: list[str]
    include_fahrenheit: bool
    language: str
    readings: list[dict[str, Any]]
    draft: dict[str, Any] | None
    review: dict[str, Any] | None
    revisions: int
    events: Annotated[list[str], add]
    answer: str | None
    status: str
```

Ordinary fields use replacement. `Annotated[list[str], add]` attaches a rule to the list type: combine contributions using `operator.add`. This does not globally change Python lists. LangGraph reads the annotation to configure the `events` reducer. See its [state and reducer description](https://docs.langchain.com/oss/python/langgraph/graph-api#reducers).

The builder does not duplicate the business logic:

```python
def build_graph(**options: Any):
    builder = state_graph_type()(ReportState)
    connect_report(builder, ReportNodes(**options))
    return builder.compile()
```

`connect_report()` registers the same nodes and routes, while `ReportNodes` supplies the same checking and revision functions. Comparing engines therefore changes scheduling, not the acceptance standard. `state_graph_type()` imports the real `StateGraph` and reports a missing dependency; it never substitutes the handwritten engine while calling it LangGraph.

Install the dependencies and run:

```bash
python -m pip install -r stages/03-stateful-orchestration/code/requirements.txt
python stages/03-stateful-orchestration/code/langgraph_workflow.py --language en --show-updates
```

LangGraph's `compile()` builds the executable graph and applies the framework's supported structural checks. It does not translate your business functions into a different language or prove that a document is correct. Nor should we assume its static checks exactly match our small engine's stricter topology checks. The behavior comparisons test the update and routing semantics our application relies on.

We can now resolve an important confusion: a graph with no model calls at all can still run in LangGraph. A graph organizes state transitions. Letting a model choose actions dynamically is another design decision. First understand a deterministic workflow; then consider the model-driven case.

## 9. Observe progress and obtain the result without executing twice

Lin wants to know why the draft was revised before delivery. The final `answer` alone does not explain that. `graph.invoke()` returns the state after a run, while `graph.stream()` exposes information as the run proceeds. Both execute the graph. Calling `invoke()` after `stream()` starts another run; it does not retrieve the result of the earlier one.

Streaming offers two views that are easy to confuse. `updates` is the change slip submitted by a node, perhaps containing one new event. `values` is the accumulated worksheet after merging, including earlier events. The [LangGraph streaming documentation](https://docs.langchain.com/oss/python/langgraph/streaming) distinguishes them. The example subscribes to both views during one execution:

```python
final = None
for mode, payload in graph.stream(state, stream_mode=["updates", "values"],
                                   config={"recursion_limit": recursion_limit}):
    if mode == "updates" and show_updates:
        for node, update in payload.items():
            print(node, "updated:", sorted(update) if isinstance(update, dict) else [])
    elif mode == "values":
        final = payload
```

In update mode, `payload` is organized by node name. In values mode, it is the current state. After the loop, `final` supplies the result; we do not repeat collection and revision just to read `answer`. The console displays changed field names rather than expanding every internal message by default.

`recursion_limit` in the configuration bounds LangGraph scheduling rounds. The framework calls a round a **super-step**: sequential nodes occupy different rounds, while multiple concurrently scheduled nodes can belong to one round. This graph has no parallel branches, but the limit still cannot be described as a model-call budget. It is also not Python's function-call recursion depth or a wall-clock deadline.

The business-level `max_revisions` answers “how many edits may we attempt?” The graph bound catches execution that keeps running because of an incorrect route. Exhausting the former can lead to `hold`; exhausting the latter is normally a scheduling error. An unacceptable draft and broken control flow should not both disappear behind “finished.”

## 10. The free-text assistant can carry a worksheet too

The form-based workflow is now clear. The text box can still receive different requests: a greeting, a Tokyo lookup, or a lookup followed by conversion. That is the model/tool loop from Stage 01. We will not give its model control over already-deterministic draft acceptance. We will examine how this familiar dynamic process fits a graph.

The example still uses the same weather source rather than suddenly switching to a multiplication question. Its output is a model reply, **not the structurally checked brief from the earlier workflow**. An application can check model output before using it, but drawing the loop as a graph does not supply that acceptance step automatically.

Two types of nodes suffice. `model` reads messages and returns an answer or requests. `tools` executes validated requests and returns observations. Pending requests lead to the tool node; successful tools lead back to the model. An answer or a nonrecoverable error ends the run.

```text
START → model ── tool requests ─→ tools
          │                       │
          │                  success → model
          │
          └─ answer or error ─→ END
                    a tool execution error also leads to END
```

The state in [`agent_graph.py`](code/agent_graph.py) now contains the fields this process actually needs:

```python
class AgentState(TypedDict):
    messages: Annotated[list[dict[str, Any]], add]
    pending_tool_calls: list[ToolCall]
    final_answer: str | None
    error: str | None
    model_steps: int
    tool_calls: int
    events: Annotated[list[str], add]
    diagnostic_tag: str
```

`messages` accumulates user requests, model requests, and observations. `pending_tool_calls`, however, means the current unfinished batch. It gets replacement semantics: writing an empty list clears it. If we used `add` for that field too, adding an empty list to old pending calls would leave them pending. A later step could execute them again. History and a to-do list are different meanings, even when both use lists.

`model_steps` and `tool_calls` are application counters. `diagnostic_tag` is a local diagnostic label. These stay in the application. The model node deliberately selects `messages` for its input; neither type hints nor promising field names make that selection for us.

## 11. Moving code into nodes must not change who executes the tools

Start with `ScriptedModel` to inspect the path. It is a test double configured for the demonstration, not an interpreter of arbitrary language. Once it receives a weather observation, it uses that actual Celsius value to construct the conversion request. The real model will use the same nodes rather than a second copy of the graph.

The model node returns the new assistant message and current pending calls. The message reducer retains the earlier history. The tool node validates the entire batch's names and parameters before starting any handler, so a plainly invalid second request does not follow an already-executed first handler. The weather tool accepts supported cities; conversion rejects strings, booleans, and nonfinite numbers. Generated names never go to `eval()`.

After execution, the update is:

```python
return {"messages": observations, "pending_tool_calls": [], "tool_calls": used,
        "error": error, "events": ["tools failed" if error else "tools completed"]}
```

`observations` contains only this batch's results, and `pending_tool_calls=[]` clears the batch. If execution fails partway through, earlier completed observations and a safe error are retained, but another model call is not made. Failure is not translated into success, and no automatic retry occurs. Those choices live in the node code; the graph framework does not infer them for us.

Budgets remain separate as well. `max_model_steps` is checked before a request, and a failed request still counts. `max_tool_calls` is checked before starting a batch, with actual execution attempts counted afterward. A call ID cannot repeat within a run, but correlation-ID uniqueness does not detect repeated business actions carrying different IDs.

Run the offline double on real LangGraph:

```bash
python stages/03-stateful-orchestration/code/langgraph_scripted_agent.py --language en --show-updates
```

The default path is `model → tools → model → tools → model`: five node executions, three model-double calls, and two tool executions. It returns Tokyo's 18.0°C and 64.4°F, with no pending calls left. `--task weather` omits conversion, and `--task greet` executes no tool. You can explicitly add `--engine mini` to run the same nodes with the handwritten scheduler. This is an explicitly selected comparison, not a silent fallback when LangGraph is missing.

Set `--max-model-steps 1` and the weather lookup can complete, but the second model request will not occur. The observation remains in state, `final_answer` stays empty, and the command exits unsuccessfully. Work already performed and successful completion of the whole task are separate facts.

## 12. Connect DeepSeek without moving state out of the current run

Now replace only the object that proposes the next step. The model node still calls `generate(messages)`. `DeepSeekModel` in [`langgraph_deepseek_agent.py`](code/langgraph_deepseek_agent.py) converts messages into provider input and converts the response into `ModelTurn`. Its request is:

```python
response = self.client.responses.create(
    model=self.model, instructions=INSTRUCTIONS, input=to_input(messages),
    tools=tool_definitions(), max_output_tokens=4096,
)
```

`tool_definitions()` describes the weather and conversion capabilities. Their handlers remain in the application. A response must complete, tool arguments must parse as an object, and a response without tool requests must contain nonempty final text. If a response includes requests and accompanying explanatory prose, the adapter continues with the requests; “let me check” is not treated as the final answer.

The [DeepSeek Responses interface](https://api-docs.deepseek.com/api/create-response/) is stateless for multi-turn use, so later calls require client-supplied history. The adapter retains each turn's complete output items, including protocol information that may be needed for continuation:

```python
provider_items = tuple(item.model_dump(mode="json", exclude_none=True) for item in output)
```

These items travel with the current run's messages, not in a shared “previous response” variable across users. The next request includes those output items and tool results paired by `call_id`. Counters and diagnostic labels do not become input merely because they also exist in state. The scheduler neither interprets reasoning text as a control protocol nor prints it in the default console output.

This is the same data flow as the earlier chapters: the remote model does not magically remember Python variables. The application supplies what happened. Replacing the model object does not change ownership of history, argument checks, or budgets.

After installing this chapter's dependencies, set the credential and an actually available model ID in the same terminal. For Bash:

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="your-available-model-id"
python stages/03-stateful-orchestration/code/langgraph_deepseek_agent.py --language en --show-updates
```

In PowerShell the first two lines are:

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-api-key"
$env:DEEPSEEK_MODEL="your-available-model-id"
```

The entry point explicitly identifies itself as live DeepSeek use, requiring network access and incurring service usage. The client sets `max_retries=0` so SDK retries do not add hidden attempts. `timeout=30.0` configures a client request, not a thirty-second deadline for the entire graph. Missing dependencies, missing credentials, and failed requests do not cause a switch to scripted answers.

A real model may use different wording, numbers of requests, or ordering. The runtime bounds execution but does not verify every final sentence. A model that skips tools and says “99 degrees” can satisfy the nonempty-answer protocol while failing the task. Reaching `END`, satisfying a data contract, and answering correctly are distinct properties.

## 13. Take the same brief through every exit

The experiments now have a purpose beyond repeating a happy path. First supply a complete initial draft and predict that no revision node will run. Then make the reviser stubbornly omit the notice and predict a route to `hold`, not `publish`:

```bash
python stages/03-stateful-orchestration/code/state_graph.py --draft-style complete --language en
python stages/03-stateful-orchestration/code/state_graph.py --draft-style stubborn --max-revisions 2 --language en
```

The second command should exit with code 1, retaining its final draft but no accepted answer. That failure is the result we want to observe, not something to fix by deleting the check.

Next, temporarily change Tokyo's record to 22.0°C. The draft, check, and final result should follow the new data and show 71.6°F. Revision should not fetch both cities again. Finally, change the temperature inside a draft after it has passed review and attempt publication. The old assessment must not approve the changed document. These experiments test data flow, node responsibilities, and the scope of a review result.

Run the automated checks:

```bash
python stages/03-stateful-orchestration/code/checks.py
```

They exercise ordinary functions, the handwritten engine, and the provider adapter. With LangGraph installed, they also compare real framework branches and merging, and verify single-run streaming. The optional SDK test uses mocked HTTP and makes no paid request. Missing optional integrations are explicitly skipped; a skip is not evidence that the real framework ran successfully.

Returning to Lin's requirement, we can now explain what is in state, what changed, why checking failed, which edge selects the next action, and when execution merely stops rather than succeeds. State still lives in this process: a restart does not automatically continue the run, and the event list is neither durable storage nor a complete observability platform. An accurate boundary tells us what problem remains.

Suppose the next user asks about a newly updated shop policy rather than two weather records already in a dictionary. Does the state graph deliver that missing information to the model? No. It organizes work; it does not create facts. [Stage 04: Retrieval and Agentic RAG](../04-agentic-rag/README.md) takes up the question of where the needed material comes from.

# Stage 03: Put the State on the Table — From Workflows to Stateful Orchestration

> Language: **English** | [简体中文](README.zh-CN.md)

By the end of Stage 02, we had four useful control patterns: deterministic workflows, routers, planner-executor systems, and an Agent Runtime that can choose its next action from each new observation.

Each one is manageable on its own. The trouble usually begins when you combine them.

Imagine a support flow that classifies a request, drafts a response, reviews it, revises it if needed, reviews again, and finally stops. In ordinary Python, a first version might look like this:

```python
category = classify(request)
draft = make_draft(request, category)
revisions = 0

while True:
    decision = review(draft)

    if decision == "accept":
        break

    draft = revise(draft)
    revisions += 1

    if revisions >= 2:
        raise RuntimeError("too many revisions")
```

There is nothing wrong with this code. If your process really is this small, I would keep it. Python already has excellent orchestration primitives called `if`, `while`, and functions. Learning graphs does not suddenly make those embarrassing.

The problem arrives when the flow grows.

Soon you have `category`, `draft`, `review_result`, `revisions`, `error`, `completed_steps`, `pending_tool_calls`, and a few more variables that only exist inside certain branches. Months later, the hardest question is often not “what does this function do?” but:

> **What state is this run in right now, and why is the next step this one?**

That is the problem Stage 03 solves.

We are not going to treat a graph as a “more advanced Agent.” We are going to make execution data explicit, then separate two responsibilities: nodes change state; edges decide where execution goes next.

---

## 1. Before drawing a graph, find the state that is already hiding in your code

Take the review loop again:

```python
category = classify(request)
draft = make_draft(request, category)
revisions = 0
review_result = None
answer = None
```

Those variables already form an execution snapshot. Python simply does not force you to name that snapshot.

We can make it explicit:

```python
state = {
    "request": request,
    "category": None,
    "draft": None,
    "review": None,
    "revisions": 0,
    "answer": None,
}
```

That gives us the first important definition of this chapter:

> **State is the data the application must know in order to continue the current execution correctly.**

The phrase “in order to continue” matters.

Your database may contain an avatar URL, signup date, loyalty points, and last login IP. If the current orchestration never uses those values, they do not automatically belong in graph state. Meanwhile a tiny field such as `revisions=1` can be crucial because the next transition depends on it.

So state is not “everything the system knows.” It is the execution snapshot that this control flow needs.

A common beginner mistake is to interpret explicit state as “put the whole application into one giant dictionary.” That is not state modeling. That is the software equivalent of putting an entire apartment into one moving box and writing `misc` on the side.

Good state makes control easier to inspect.

---

## 2. Graph state and model context are not the same thing

Stage 00 established that a model only sees the context the application actually sends to it.

Graph state is different. It is application-side execution data.

Suppose the state contains:

```python
state = {
    "request": "I was charged twice.",
    "category": "billing",
    "draft": "I can help review the billing issue.",
    "revisions": 1,
    "internal_retry_count": 2,
}
```

If one node asks a model to improve the wording, the model input might only be:

```python
model_input = {
    "request": state["request"],
    "draft": state["draft"],
}
```

There is no reason the model must see `internal_retry_count`.

Keep the distinction clear:

```text
Graph State
    = data the application needs to continue execution

Model Context
    = data actually sent to this model call
```

If you merge these ideas, you end up shoving every internal control variable into prompts merely because the application wants to remember it. The model gets more clutter; the application gets less clarity.

State is an application execution structure. Context is a model input structure.

---

## 3. A node should make one meaningful state change

Once state is explicit, we can split one large procedure into nodes.

A classification node might look like this:

```python
def classify(state):
    request = state["request"].lower()

    if "refund" in request or "charged" in request:
        category = "billing"
    elif "password" in request or "login" in request:
        category = "technical"
    else:
        category = "general"

    return {"category": category}
```

Notice that the node does not return the entire state. It returns only the fields it changed.

Its input might be:

```python
{
    "request": "I was charged twice.",
    "category": None,
    "revisions": 0,
}
```

The node returns:

```python
{"category": "billing"}
```

The runtime merges that update into the existing state.

The useful mental model is:

```text
Node:
State -> Partial State Update
```

Why not copy the entire state out of every node?

Because a classifier that only owns `category` should not casually overwrite `revisions`, `draft`, or `answer`. Partial updates make responsibility visible in code.

The node is effectively saying:

> “These are the fields I changed. Everything else is somebody else's business.”

That is a much better contract than a comment asking every future contributor to “please be careful.”

---

## 4. Nodes do work; edges decide where execution goes

If nodes are workstations, edges are hallways.

A fixed flow is simple:

```text
START
  ↓
classify
  ↓
draft
  ↓
review
  ↓
finish
  ↓
END
```

In code, those transitions look like:

```python
add_edge("classify", "draft")
add_edge("draft", "review")
```

Review is more interesting.

If the draft is accepted, go to `finish`. If it needs work, go to `revise`:

```text
                 ┌────────── revise ──────────┐
                 │                             │
                 v                             │
draft -------> review -------------------------┘
                 |
                 | accept
                 v
               finish
```

That is a conditional edge.

Its job is not to perform the revision. Its job is only to choose one application-approved destination from the current state.

```python
def route_after_review(state):
    return state["review"]
```

The application declares the allowed mapping:

```python
{
    "revise": "revise",
    "accept": "finish",
}
```

This should feel familiar from Stage 02. A router can choose a route, but the application still owns the set of valid destinations.

A graph does not erase earlier control boundaries. It gives them a different representation.

---

## 5. START and END are structural sentinels

Most state graphs have special structural positions:

```text
START
END
```

They are not business nodes. They describe topology.

```python
builder.add_edge(START, "classify")
builder.add_edge("finish", END)
```

That makes the entry and exit points explicit.

When you inspect a graph, you can ask:

- Where does execution begin?
- Which paths can terminate?
- Is a node unreachable?
- Does a cycle have any exit at all?

You can answer those questions in ordinary Python too, of course. But as control flow grows, you may have to trace nested conditionals, loops, helper functions, and exception paths. A graph makes the execution map easier to inspect directly.

---

## 6. Build a tiny graph runtime before using LangGraph

Before reaching for a framework, let us implement the core ourselves.

The builder only needs a few collections:

```python
class MiniStateGraph:
    def __init__(self, *, reducers=None):
        self._nodes = {}
        self._edges = {}
        self._conditional_edges = {}
        self._reducers = dict(reducers or {})
```

It stores:

```text
nodes
fixed edges
conditional edges
reducers
```

Node registration is just a name-to-function mapping:

```python
def add_node(self, name, node):
    if name in self._nodes:
        raise ValueError(f"duplicate node: {name!r}")

    self._nodes[name] = node
```

A fixed edge stores:

```text
source -> destination
```

A conditional edge stores one extra piece: a router that reads state and returns a route name.

At this point, the graph runtime should look much less mystical.

Its main questions are basically:

> Which node runs now? What update did it produce? After applying that update, where do we go next?

The runtime itself is not “thinking.”

---

## 7. The execution engine still contains a while loop

This is one of the most useful things to inspect.

The core of our handwritten runtime is roughly:

```python
state = dict(initial_state)
current = self._next_node(START, state)

while current != END:
    update = self._nodes[current](dict(state))

    if update is not None:
        self._apply_update(state, update)

    current = self._next_node(current, state)
```

So graphs did not abolish `while`.

They move control-flow declarations out of one increasingly complicated loop and into explicit topology.

A conventional loop might eventually become:

```python
while True:
    if phase == "draft":
        ...
    elif phase == "review":
        ...
    elif phase == "revise":
        ...
```

The graph writes the transitions directly:

```text
draft -> review
review --revise--> revise
review --accept--> finish
revise -> review
```

When the flow becomes sufficiently branched or cyclic, the second representation is easier to inspect.

If your program is only:

```python
validate()
save()
```

please do not introduce a graph runtime just so you can draw two boxes. Replacing a staircase with an airport jet bridge is not automatically an architecture improvement.

---

## 8. Partial updates force us to answer an important question: how do values merge?

Suppose the current state is:

```python
{
    "draft": "first",
    "events": ["classified"],
}
```

A node returns:

```python
{
    "draft": "second",
    "events": ["revised"],
}
```

For `draft`, replacement probably makes sense:

```text
"first" -> "second"
```

But what about `events`?

If we replace it too:

```python
["classified"] -> ["revised"]
```

we lose the earlier event.

If `events` represents accumulated history, we probably want:

```python
["classified", "revised"]
```

That is what reducers define.

A reducer is conceptually:

```python
new_value = reducer(old_value, update_value)
```

For list accumulation:

```python
def append_events(left, right):
    return [*left, *right]
```

The runtime can then apply updates like this:

```python
reducer = self._reducers.get(key)

if reducer is None:
    state[key] = right
else:
    state[key] = reducer(state[key], right)
```

This tiny mechanism carries a lot of meaning.

When a node returns `"events": ["revised"]`, the node does not decide whether that means “replace” or “append.” The update semantics belong to the definition of that state channel.

---

## 9. The wrong reducer silently changes the meaning of your state

Suppose `messages` is a list representing conversation history.

Without a reducer, one node returns:

```python
{"messages": ["hello"]}
```

and the next returns:

```python
{"messages": ["tool result"]}
```

The final value may simply be:

```python
{"messages": ["tool result"]}
```

Your “history” has become “latest message.”

The opposite mistake is just as dangerous.

Imagine `pending_tool_calls` means the calls that still need execution. If you use an append reducer blindly:

```text
old pending calls + new pending calls
```

completed calls may remain in state and get executed again.

So “it is a list” is not enough reason to append.

Ask what the field means:

```text
latest value?
accumulated history?
replaceable set?
deduplicated collection?
```

Reducer choice should follow field semantics.

State schemas are not only about types. They are also about update behavior.

---

## 10. Follow one workflow through its state transitions

The handwritten example uses a small support workflow:

```text
request
  ↓
classify
  ↓
draft
  ↓
review
  ├── accept ──────────────> finish -> END
  │
  └── revise -> revise
                 |
                 └─────────> review
```

The initial state is small:

```python
{
    "request": "I was charged twice and need a refund.",
    "revisions": 0,
    "events": [],
}
```

Classification adds:

```python
{
    "category": "billing",
    "events": ["classified as billing"],
}
```

Drafting adds:

```python
{
    "draft": "I can help review the billing issue.",
    "events": ["drafted first response"],
}
```

The first review deliberately requests a revision:

```python
{
    "review": "revise",
    "events": ["review requested one revision"],
}
```

The conditional edge routes execution to `revise`.

That node returns:

```python
{
    "draft": state["draft"] + " I will keep the next step specific.",
    "revisions": state["revisions"] + 1,
    "events": ["revised response"],
}
```

Execution returns to `review`, which now chooses `accept`, and the graph reaches `finish`.

Run it:

```bash
python stages/03-stateful-orchestration/code/state_graph.py
```

The trace is:

```text
classify -> draft -> review -> revise -> review -> finish
```

That trace is valuable because “how did we get here?” is now a first-class runtime result instead of something you reconstruct from scattered log lines.

---

## 11. Cycles are normal; unbounded cycles are the problem

The workflow contains a cycle:

```text
review -> revise -> review
```

That is not inherently suspicious.

ReAct is cyclic:

```text
model -> tool -> model -> tool -> ...
```

Recovery workflows are often cyclic too.

The real question is:

> **Who prevents the cycle from running forever?**

Our handwritten runtime uses an application-owned:

```python
max_steps
```

and stops when the trace reaches that budget.

This is the same engineering idea we used in Stage 01 with `max_steps` and Stage 02 with `max_replans`: dynamic control needs an external bound.

Do not ask a node to promise that it will “probably stop soon.”

A component that is already looping is not the ideal authority for deciding whether it is looping.

---

## 12. Why compile a graph before running it?

We do not execute the builder directly. We first call:

```python
graph = builder.compile()
```

Our handwritten `compile()` performs topology checks.

A graph with nodes but no edge from `START` should fail before user traffic reaches it.

An edge to an unknown node should also fail early.

Think of it like a railway map.

It is better to discover a missing track while inspecting the map than when the train arrives at the coordinates where somebody accidentally typed `finsh` instead of `finish`.

Compilation cannot prove the business logic is correct. It cannot guarantee a model will behave, an API will stay available, or a tool will be safe.

It validates structure, not truth.

That distinction matters.

---

## 13. Now map the same ideas to LangGraph

Once the mechanism is visible, LangGraph becomes easier to read.

Install the Stage 03 dependency:

```bash
python -m pip install -e ".[stage03]"
```

First define a state schema:

```python
from operator import add
from typing import Annotated
from typing_extensions import TypedDict

class SupportState(TypedDict, total=False):
    request: str
    category: str
    draft: str
    review: str
    revisions: int
    events: Annotated[list[str], add]
    answer: str
```

The line to notice is:

```python
events: Annotated[list[str], add]
```

It tells LangGraph to combine new `events` updates with `operator.add`.

Fields without an explicit reducer use replacement semantics by default.

That is the same problem we just solved in our miniature runtime.

LangGraph's Graph API describes state in exactly these terms: a state schema defines channels, and reducers define how node updates are applied to those channels.

---

## 14. A LangGraph node is still an ordinary Python function

Classification can remain:

```python
def classify(state: SupportState) -> dict:
    request = state["request"].lower()

    if "refund" in request or "charged" in request:
        category = "billing"
    else:
        category = "general"

    return {
        "category": category,
        "events": [f"classified as {category}"],
    }
```

Then register it:

```python
builder = StateGraph(SupportState)

builder.add_node("classify", classify)
builder.add_node("draft", draft)
builder.add_node("review", review)
```

There is no special graph programming language here.

A node is a function. If it performs deterministic calculation, it is deterministic calculation. If it calls a model, then that particular node is a model node. If it executes a tool, that particular node performs the side effect.

Being a node does not grant a function new authority.

The current LangGraph documentation makes the same basic distinction: state is shared data, nodes perform logic and return updates, and edges determine what runs next.

---

## 15. Fixed and conditional edges map almost one-to-one

Fixed transitions:

```python
builder.add_edge(START, "classify")
builder.add_edge("classify", "draft")
builder.add_edge("draft", "review")
```

Conditional routing:

```python
builder.add_conditional_edges(
    "review",
    route_after_review,
    {
        "revise": "revise",
        "accept": "finish",
    },
)
```

Close the loop:

```python
builder.add_edge("revise", "review")
builder.add_edge("finish", END)
```

Then compile:

```python
graph = builder.compile()
```

The mapping is direct:

| Handwritten concept | LangGraph |
|---|---|
| state dictionary | state schema |
| node function | `add_node()` |
| fixed transition | `add_edge()` |
| state-based branch | `add_conditional_edges()` |
| update merge rule | reducer |
| topology build/check | `compile()` |
| execution | `invoke()` / `stream()` |

Now the methods are easier to remember because each one corresponds to a mechanism you have already implemented.

---

## 16. `invoke()` returns the accumulated state; `stream()` exposes the path as it runs

A normal execution is:

```python
result = graph.invoke(
    initial_state,
    config={"recursion_limit": 20},
)
```

The returned object contains the accumulated graph state.

For learning and debugging, it is often useful to watch node updates:

```python
for update in graph.stream(
    initial_state,
    stream_mode="updates",
):
    print(update)
```

With `stream_mode="updates"`, you focus on what each node produced rather than printing the entire accumulated state every time. Current LangGraph documentation explicitly distinguishes update streaming from full state-value streaming.

You might see output shaped like:

```text
{"classify": {"category": "billing", ...}}
{"draft": {"draft": "...", ...}}
{"review": {"review": "revise", ...}}
{"revise": {...}}
```

Streaming does not change the business logic. It only makes execution progress observable.

---

## 17. LangGraph's recursion limit serves the same kind of boundary as our max_steps

Our tiny runtime bounds cycles with:

```python
max_steps=30
```

LangGraph exposes an execution recursion limit through runtime configuration:

```python
config = {
    "recursion_limit": 20,
}
```

The implementation details are not identical, but the engineering purpose is similar: do not let a cyclic graph run indefinitely.

This matters even more when a conditional route is model-driven.

A model can keep deciding “one more attempt.”

The runtime needs permission to reply, in effect:

> No. We have already purchased enough optimism for this request.

---

## 18. A graph is not an Agent, and our first graph proves it

The support workflow contains no model at all.

Classification is ordinary Python:

```python
if "refund" in request:
    category = "billing"
```

Review is deterministic too:

```python
needs_revision = state.get("revisions", 0) == 0
```

Yet the workflow is a perfectly valid graph.

Therefore:

```text
Graph != Agent
```

A graph is a representation of state evolution and control transitions.

An Agent is a control pattern in which some decisions are delegated to a model using environmental feedback.

You can build a deterministic graph.

You can build an agentic graph.

You can also build an Agent Runtime without a graph.

Do not fuse those ideas just because frameworks often show them together.

---

## 19. Translate the Stage 01 ReAct loop into a graph

The Stage 01 runtime can be drawn as:

```text
model
  |
  +-- final answer --> END
  |
  +-- Tool Call
         |
         v
       tools
         |
         v
       model
```

As a graph:

```text
             +----------------+
START ------>|     model      |
             +-------+--------+
                     |
            conditional edge
              /             \
             v               v
          tools             END
             |
             +-------------> model
```

Now responsibilities become very visible.

The `model` node:

```text
reads messages
produces Tool Calls or a final answer
updates pending_tool_calls / final_answer
```

The `tools` node:

```text
reads pending_tool_calls
looks up application-registered tools
executes them
writes observations back to messages
```

The conditional edge:

```text
pending calls -> tools
otherwise -> END
```

That is what [`code/langgraph_agent.py`](code/langgraph_agent.py) demonstrates.

Run it:

```bash
python stages/03-stateful-orchestration/code/langgraph_agent.py
```

The example uses a deterministic `ScriptedModel`. On the first turn it requests:

```python
ToolCall(
    call_id="call_mul",
    name="multiply",
    arguments={"a": 6, "b": 7},
)
```

The tool node executes:

```python
TOOLS["multiply"](**call.arguments)
```

The result `42` becomes a tool observation, and the model finishes on the next turn.

Same mechanism as Stage 01, different orchestration representation.

---

## 20. Converting a while loop into a graph does not change authority

Inside the graph:

```python
def model_node(state):
    turn = model.generate(state["messages"])
    ...
```

The model still only proposes what should happen next.

Actual tool execution still occurs in:

```python
def tool_node(state):
    handler = TOOLS[call.name]
    result = handler(**call.arguments)
```

So:

```text
model node
    !=
tool execution authority
```

The graph runtime organizes transitions. It does not give the model Python execution rights.

The boundary from Stage 00 still holds:

> The model proposes. The application executes and owns the consequences.

Graph changes orchestration, not authority.

---

## 21. So why not turn every Agent into a graph?

Because graphs have a cost too.

A small ReAct loop:

```python
while True:
    turn = model.generate(...)
    ...
```

can be wonderfully readable.

If the whole control structure is simply:

```text
model <-> tools
```

and the state is tiny, an ordinary runtime may already be the best design.

Graphs become more attractive when you start seeing:

```text
many branches
shared state across stages
cycles with different exit conditions
multiple control paths worth testing independently
a need to inspect which nodes actually ran
```

For example:

```text
classify
  ├── fast_path
  ├── plan
  │     └── execute
  │           └── review
  │                 ├── finish
  │                 └── repair -> review
  └── reject
```

You can absolutely write that with `if`, `while`, and `try/except`.

But six months later, the giant loop may become the most senior member of the engineering team: everybody respects it, nobody understands all of it, and nobody wants to touch it before a holiday weekend.

Graph structure earns its keep when it makes a genuinely complicated execution model easier to reason about.

---

## 22. State design matters more than an attractive graph diagram

When people first learn graph orchestration, they often focus on nodes and arrows.

Start with state instead.

This is technically possible:

```python
class AgentState(TypedDict):
    everything: dict
```

It is also a very effective way to hide all semantics again.

A better state exposes the fields that actually drive execution:

```python
class AgentState(TypedDict, total=False):
    messages: list[dict]
    pending_tool_calls: list[ToolCall]
    final_answer: str | None
    error: str | None
    model_steps: int
```

Even before reading a node, you can see what the runtime cares about.

That is one of the major benefits of explicit state: the execution model becomes inspectable.

A graph can have beautiful arrows and still have terrible state design.

---

## 23. Prefer returned updates over secretly mutating the input state

Consider:

```python
def bad_node(state):
    state["count"] += 1
    return state
```

Now the update boundary is unclear.

Was the original state already mutated before the runtime merged anything? Which fields changed?

A cleaner style is:

```python
def increment(state):
    return {
        "count": state["count"] + 1,
    }
```

Think:

```text
read snapshot
compute
return update
```

This also makes node tests trivial:

```python
update = increment({"count": 1})
assert update == {"count": 2}
```

You can test node behavior without starting the whole graph.

---

## 24. A conditional edge should not secretly perform the business action

This is a bad smell:

```python
def route(state):
    if state["category"] == "billing":
        send_refund_request()
        return "finish"
```

Now the router both decides and executes.

You have mixed:

```text
routing decision
+
business side effect
```

Prefer:

```python
def route(state):
    return state["category"]
```

and route to a dedicated:

```text
billing_handler
```

node.

Then you can test two separate questions:

- Did the router choose the right destination?
- Did the billing node perform the right action?

This is the same principle from Stage 02: decision and execution should not dissolve into one function just because the function is convenient.

---

## 25. How large should a node be?

There is no magic number of lines.

A more useful question is:

> If this node fails, can I clearly say which meaningful step failed?

A node that performs classification, a model call, a database write, a calculation, an email send, and an audit log all at once is difficult to reason about. `node=process_everything` is not much of a diagnosis.

But splitting every tiny expression into its own node is equally unhelpful.

You do not need a graph shaped like a circuit board.

A useful node usually corresponds to a meaningful orchestration unit:

```text
classify request
draft response
review response
call model
execute tool batch
```

Node granularity should help control flow, state boundaries, testing, and observability—not your desire to collect more rectangles.

---

## 26. Test the trace, not only the final answer

Suppose the final answer is:

```text
I can help review the billing issue.
```

This assertion alone:

```python
assert result["answer"] == expected
```

does not prove the workflow behaved correctly.

The intended path might be:

```text
classify -> draft -> review -> revise -> review -> finish
```

A bug could accidentally produce:

```text
classify -> finish
```

and still happen to create the same final text.

Our handwritten checks therefore verify the trace:

```python
assert result.trace == (
    "classify",
    "draft",
    "review",
    "revise",
    "review",
    "finish",
)
```

For stateful orchestration, transitions are part of the product behavior.

This continues a principle from earlier stages:

> Correct final text can still come from an incorrect execution path.

---

## 27. Framework tests should verify semantics, not merely imports

This test:

```python
import langgraph
```

proves the dependency exists.

That is not the same as proving the semantics your code relies on still hold.

If you depend on a reducer:

```python
class State(TypedDict):
    events: Annotated[list[str], add]
```

then test that separate node updates:

```python
{"events": ["one"]}
{"events": ["two"]}
```

really produce:

```python
["one", "two"]
```

If you depend on conditional routing, test the actual branch behavior.

The goal is not to re-test LangGraph for its maintainers. The goal is to protect the framework semantics that this repository teaches and relies on.

---

## 28. Graph state is not automatically a history log

State can contain history, but state does not have to be history.

These fields:

```python
{
    "category": "billing",
    "revisions": 1,
}
```

represent current values needed by execution.

This field:

```python
{
    "events": [
        "classified as billing",
        "drafted first response",
        "review requested one revision",
    ]
}
```

is an accumulated trace we intentionally chose to retain.

Those are different semantics.

Do not assume every old value must remain forever just because state changes over time.

Many fields should overwrite:

```text
old review decision
-> new review decision
```

Only fields that actually mean “accumulated history” should use an accumulating reducer.

---

## 29. Reduce the whole chapter to four questions

If the chapter has started to feel dense, keep these four questions.

State:

```text
What data must exist for execution to continue correctly?
```

Node:

```text
What meaningful work happens here, and what partial update does it produce?
```

Edge:

```text
Which node runs next?
```

Reducer:

```text
How is this partial update merged into accumulated state?
```

Once those four are clear, most of LangGraph's core Graph API stops looking mysterious.

---

## 30. Run the chapter examples

Start with the handwritten runtime:

```bash
python stages/03-stateful-orchestration/code/state_graph.py
```

Install LangGraph:

```bash
python -m pip install -e ".[stage03]"
```

Run the same workflow using LangGraph:

```bash
python stages/03-stateful-orchestration/code/langgraph_workflow.py
```

Run the graph-shaped ReAct example:

```bash
python stages/03-stateful-orchestration/code/langgraph_agent.py
```

Then run the offline checks:

```bash
python stages/03-stateful-orchestration/code/checks.py
```

The checks cover partial updates, reducers, invalid conditional routes, cycle budgets, the handwritten revision loop, equivalent LangGraph workflow behavior, streaming updates, and the model/tool boundary in the ReAct graph.

---

## 31. Exercises: change control semantics, not just the labels

First, change the support review logic.

Right now the first review always requests one revision. Make it inspect the draft instead: request a revision only if the draft does not contain the phrase `"next step"`.

Do not edit the draft inside the router. The router should only choose `revise` or `accept`.

Next, add an `escalate` path.

If `revisions >= 2` and the draft is still rejected, stop looping and enter an `escalate` node:

```text
review
  ├── accept
  ├── revise
  └── escalate
```

Then intentionally remove the reducer from `events`, run the graph, and observe how accumulated history disappears. Restore it and explain why the field's meaning requires accumulation.

Finally, modify `langgraph_agent.py` so the scripted model first calls `multiply`, then calls a new `add` tool, and only then returns a final answer. Do not change the graph topology.

If you can do that cleanly, you have understood an important benefit of the representation:

> The graph describes the control structure; task behavior can evolve inside that structure without rewriting the entire runtime.

---

## 32. Closing the chapter: make “where are we now?” a first-class concept

Stage 01 gave us a looping Agent Runtime.

Stage 02 taught us to choose deliberately which decisions belong to models and which should remain ordinary software.

Stage 03 adds another piece: once branches, loops, and intermediate data become difficult to follow, stop hiding execution position inside local variables and nested control flow. Represent it explicitly with:

```text
State
+
Node
+
Edge
+
Reducer
```

The value of a graph is not that it makes a system look more agentic.

It solves a more practical problem:

> **When the control flow is complicated enough to need a map, give the program a map it can actually execute.**

If the road is straight, use ordinary Python.

If the system genuinely has shared state, branches, cycles, and paths worth inspecting independently, a graph may earn its complexity.

Architecture is not a badge collection. If a staircase gets you there, you do not need to build an interchange.

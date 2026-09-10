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

### Reading and running route

This chapter assumes Stage 00's model/tool boundary, Stage 01's decide–act–observe loop, and Stage 02's finite routes and execution budgets. You should be comfortable reading Python dictionaries, functions, and classes; no LangGraph experience is required.

Read sections 1–12 for the pure-Python mechanism, then 13–19 to map the same flow to LangGraph. Sections 20–29 review design boundaries, and section 30 collects run commands. `langgraph_scripted_agent.py` is the offline comparison example; the complete live comparison implementation is `langgraph_deepseek_agent.py` and needs a DeepSeek key.

Run commands from the `Tiny-Agent` repository root. Mechanism excerpts are not all standalone programs; complete runnable sources live in `code/`, and the relevant dependencies of excerpts are identified below.


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

Before registering any outgoing edge, the builder rejects an impossible source or a second outgoing transition from the same source:

```python
def _ensure_no_outgoing_edge(self, source: str) -> None:
    if source == END:
        raise ValueError("END cannot have an outgoing edge")
    if source in self._edges or source in self._conditional_edges:
        raise ValueError(f"{source!r} already has an outgoing edge")
```

Node registration is a name-to-function mapping:

```python
def add_node(self, name: str, node: Node) -> None:
    if not name or name in {START, END}:
        raise ValueError(f"invalid node name: {name!r}")
    if name in self._nodes:
        raise ValueError(f"duplicate node: {name!r}")
    self._nodes[name] = node
```

A fixed edge is a source-to-destination mapping. Its registration method stores that mapping after the shared validation:

```python
def add_edge(self, source: str, destination: str) -> None:
    self._ensure_no_outgoing_edge(source)
    self._edges[source] = destination
```

For example, `add_edge("draft", "review")` produces:

```python
self._edges == {"draft": "review"}
```

A conditional edge stores a router and a route-name-to-destination mapping. The router reads state; the mapping, rather than the router, defines the destinations that the graph permits.

```python
@dataclass(frozen=True, slots=True)
class ConditionalEdge:
    router: Router
    destinations: dict[str, str]


def add_conditional_edges(
    self,
    source: str,
    router: Router,
    destinations: Mapping[str, str],
) -> None:
    self._ensure_no_outgoing_edge(source)
    if not destinations:
        raise ValueError("conditional edges need at least one destination")
    self._conditional_edges[source] = ConditionalEdge(
        router=router,
        destinations=dict(destinations),
    )
```

For example, `add_conditional_edges("review", route_after_review, {"revise": "revise", "accept": "finish"})` stores both the decision function and this allowed route table:

```python
{
    "review": ConditionalEdge(
        router=route_after_review,
        destinations={"revise": "revise", "accept": "finish"},
    )
}
```

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

`_next_node()` is the missing bridge between those stored structures and the loop. It first checks for a conditional edge, validates the route name, and otherwise follows the fixed edge:

```python
def _next_node(self, source: str, state: State) -> str:
    branch = self._conditional_edges.get(source)
    if branch is not None:
        route = branch.router(dict(state))
        try:
            return branch.destinations[route]
        except KeyError as exc:
            allowed = ", ".join(sorted(branch.destinations))
            raise RuntimeError(
                f"router from {source!r} returned {route!r}; "
                f"allowed routes: {allowed}"
            ) from exc

    try:
        return self._edges[source]
    except KeyError as exc:
        raise RuntimeError(f"{source!r} has no outgoing edge") from exc
```

So graphs did not abolish `while`.

They move control-flow declarations out of one increasingly complicated loop and into explicit topology.

A conventional loop might eventually become:

```text
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

```text
["classified"] -> ["revised"]
```

we lose the earlier event.

If `events` represents accumulated history, we probably want:

```python
["classified", "revised"]
```

That is what reducers define.

Think of `draft` as the current version of one document: the new version replaces the old one. Think of `events` as a logbook: a new entry belongs after the earlier entries. Both are stored in State, but they answer different questions and therefore need different merge rules.

A reducer is the rule for one State field:

```python
new_value = reducer(old_value, update_value)
```

For list accumulation:

```python
def append_events(left, right):
    return [*left, *right]
```

Here is the complete merge for this exact State and update. Run it as one block:

```python
def append_events(left, right):
    return [*left, *right]


def apply_update(state, update, reducers):
    for key, right in update.items():
        reducer = reducers.get(key)
        if reducer is None or key not in state:
            state[key] = right
        else:
            state[key] = reducer(state[key], right)

state = {
    "draft": "first",
    "events": ["classified"],
}
update = {
    "draft": "second",
    "events": ["revised"],
}

apply_update(state, update, reducers={"events": append_events})
print(state)
```

It prints:

```python
{
    "draft": "second",
    "events": ["classified", "revised"],
}
```

`draft` has no reducer, so the runtime replaces it. `events` is configured with `append_events`, so the runtime combines the old history with the node's new entry. The node never has to read, copy, and return the old event history itself.

This is the practical value: every Node can return only the fields it owns, while the graph owns the consistent merge rule. When a node returns `"events": ["revised"]`, it does not decide whether that means “replace” or “append”; the update semantics belong to the definition of that State field.

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

Execution returns to `review`, which now accepts the draft:

```python
{
    "review": "accept",
    "events": ["review accepted response"],
}
```

The conditional edge sends the graph to `finish`.

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

The check is deliberately outside every node:

```python
if len(trace) >= max_steps:
    raise RuntimeError(f"graph exceeded max_steps={max_steps}")
```

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

## 13. Meet LangGraph, then map the same mechanism

[LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) is LangChain's stateful agent and workflow orchestration framework. It turns State, Nodes, Edges, conditional routing, and cycles into an executable graph, which suits programs that need multi-step, resumable, or observable execution.

If LangGraph is new to you, start with the official [overview](https://docs.langchain.com/oss/python/langgraph/overview) and [Workflows and agents guide](https://docs.langchain.com/oss/python/langgraph/workflows-agents). They cover the framework API, common workflow patterns, and broader production features.

This tutorial does not repeat a general LangGraph course. Sections 1–12 already unpacked the graph-runtime mechanism in pure Python. From here, we express the same State, Nodes, Edges, and routing logic with LangGraph, focusing on how agent state and control flow map to framework code.

Install the Stage 03 dependency:

```bash
python -m pip install -r stages/03-stateful-orchestration/code/requirements.txt
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

`TypedDict` describes the fields a state dictionary may contain. `total=False` lets fields produced by later nodes be absent from the initial state; it does not create defaults or perform runtime validation. Because `events` uses `add`, each node must return only its new events. Returning the entire event history would add the old entries a second time.

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
    elif "password" in request or "login" in request:
        category = "technical"
    else:
        category = "general"

    return {
        "category": category,
        "events": [f"classified as {category}"],
    }
```

Then register it:

```python
from langgraph.graph import END, START, StateGraph

builder = StateGraph(SupportState)

builder.add_node("classify", classify)
builder.add_node("draft", draft)
builder.add_node("review", review)
builder.add_node("revise", revise)
builder.add_node("finish", finish)
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

### Run the connected pieces

The `draft`, `review`, `revise`, `finish`, and `route_after_review` definitions used in sections 14–15 live in `langgraph_workflow.py`. Registration statements alone need those definitions. Start a Python shell in that file's `code/` directory, then run this complete entry point:

```python
from langgraph_workflow import build_graph, initial_state

graph = build_graph()
result = graph.invoke(initial_state(), config={"recursion_limit": 20})
print(result["answer"])
assert result["revisions"] == 1
assert len(result["events"]) == 6
```

## 16. `invoke()` returns the accumulated state; `stream()` exposes the path as it runs

A normal execution is:

```python
result = graph.invoke(
    initial_state(),
    config={"recursion_limit": 20},
)
```

The returned object contains the accumulated graph state. This uses the imported `initial_state()` function from the preceding example; call it to obtain the initial dictionary.

For learning and debugging, it is often useful to watch node updates:

```python
for update in graph.stream(
    initial_state(),
    stream_mode="updates",
    config={"recursion_limit": 20},
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

Calling `stream()` and then `invoke()` starts two independent runs; it does not retrieve the same run twice. The offline demo compares both interfaces, while the live DeepSeek demo uses a single `stream()` to avoid duplicate requests and tool execution.

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

That is what the offline [`code/langgraph_scripted_agent.py`](code/langgraph_scripted_agent.py) demonstrates.

Run it:

```bash
python stages/03-stateful-orchestration/code/langgraph_scripted_agent.py
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

The builder now accepts `model`, defaulting to `ScriptedModel`. Any object implementing `generate(messages) -> ModelTurn` can reuse the same nodes and edges. Adding tools requires updating both the provider schema and tool-node argument validation.

### 19.1 Run the same graph with DeepSeek

The original Stage 03 used only scripted models. There is now a parallel, complete pair: [langgraph_scripted_agent.py](code/langgraph_scripted_agent.py) uses the offline `ScriptedModel`, while [langgraph_deepseek_agent.py](code/langgraph_deepseek_agent.py) uses a live DeepSeek model. Each file defines its own State, Nodes, Edges, Tool, and graph builder so you can compare them line by line. Install the dependencies from section 30, then configure and run from the repository root in the same terminal.

Windows Command Prompt:

```cmd
set "DEEPSEEK_API_KEY=your-deepseek-api-key"
set "DEEPSEEK_MODEL=deepseek-v4-flash"
python stages/03-stateful-orchestration/code/langgraph_deepseek_agent.py
```

PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-api-key"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"
python stages/03-stateful-orchestration/code/langgraph_deepseek_agent.py
```

Bash:

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="deepseek-v4-flash"
python stages/03-stateful-orchestration/code/langgraph_deepseek_agent.py
```

Client creation follows. `required_env` is the helper in that file that rejects empty environment variables:

```python
from openai import OpenAI
from langgraph_deepseek_agent import DeepSeekModel, required_env, build_agent_graph

client = OpenAI(
    api_key=required_env("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
model = DeepSeekModel(client=client, model=required_env("DEEPSEEK_MODEL"))
graph = build_agent_graph(model=model, max_model_steps=4)
```

`api_key` is the DeepSeek credential, `base_url` selects the service address, and `model` selects an available model.

As in Stage 01, the Adapter rebuilds the full input on each call: user messages, assistant `function_call` items, and `function_call_output` items paired by `call_id`. It sends only the state's messages, leaving control fields such as model_steps in the application. See the [DeepSeek Responses reference](https://api-docs.deepseek.com/guides/responses_api/).

The offline demo has deterministic output:

```text
final_answer: 6 * 7 = 42
model_steps: 2
message roles: ['user', 'assistant', 'tool', 'assistant']
```

Live wording and turn counts may vary. Look for a model update requesting multiply, a tools update containing 42, then a final answer. At most four model calls are allowed; exhaustion returns an error that the live entry point raises. The separate `recursion_limit=20` counts graph super-steps, usually one node at a time in this sequential graph, rather than model calls.

API errors, malformed JSON, unknown tools, and invalid arguments stop execution without automatic retries. Tool arguments must be exactly two finite numbers a and b; repeated call IDs are rejected. These checks preserve the execution boundary established in earlier chapters.


## 20. Converting a while loop into a graph does not change authority

Inside the graph, the proposal-only part of the node is:

```python
def model_node(state):
    turn = model.generate(state["messages"])
    return {"pending_tool_calls": list(turn.tool_calls)}
```

The model still only proposes what should happen next.

Actual tool execution still occurs in:

```python
import math
from typing import Any
from langgraph_scripted_agent import AgentState, TOOLS

def tool_node(state: AgentState) -> dict:
    observations: list[dict[str, Any]] = []

    for call in state.get("pending_tool_calls", []):
        try:
            handler = TOOLS[call.name]
        except KeyError as exc:
            raise RuntimeError(f"unknown tool: {call.name}") from exc

        if set(call.arguments) != {"a", "b"} or any(
            type(value) not in (int, float) or not math.isfinite(value)
            for value in call.arguments.values()
        ):
            raise ValueError("multiply requires exactly two finite numbers: a, b")
        result = handler(**call.arguments)
        observations.append(
            {
                "role": "tool",
                "tool_call_id": call.call_id,
                "content": str(result),
            }
        )

    return {
        "messages": observations,
        "pending_tool_calls": [],
    }
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

```text
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
from operator import add
from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph_scripted_agent import ToolCall

class AgentState(TypedDict, total=False):
    messages: Annotated[list[dict[str, Any]], add]
    pending_tool_calls: list[ToolCall]
    final_answer: str | None
    error: str | None
    model_steps: int
```

Even before reading a node, you can see what the runtime cares about.

That is one of the major benefits of explicit state: the execution model becomes inspectable.

A graph can have beautiful arrows and still have terrible state design.

---

`messages` accumulates new messages; `pending_tool_calls` is replaced and cleared after execution. Appending pending calls could execute old calls again.

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

The handwritten engine uses `dict(state)`, a shallow copy: nested lists still share references. This is not an isolation sandbox. Return new lists instead of calling `append()` on input events or messages. These graphs keep state in the current process only; no checkpointer is configured, so restarting does not resume a run.

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
python -m pip install -r stages/03-stateful-orchestration/code/requirements.txt
```

Run the same workflow using LangGraph:

```bash
python stages/03-stateful-orchestration/code/langgraph_workflow.py
```

Run the graph-shaped ReAct example:

```bash
python stages/03-stateful-orchestration/code/langgraph_scripted_agent.py
```

Then run the offline checks:

```bash
python stages/03-stateful-orchestration/code/checks.py
```

The checks cover partial updates, reducers, invalid conditional routes, cycle budgets, the handwritten revision loop, equivalent LangGraph workflow behavior, streaming updates, and the model/tool boundary in the ReAct graph.

---

### Troubleshooting and file map

| File | Purpose | Live model call |
|---|---|---|
| state_graph.py | Handwritten merge and transition engine | No |
| langgraph_workflow.py | Same support flow in LangGraph | No |
| langgraph_scripted_agent.py | Complete offline model → tools graph | No |
| langgraph_deepseek_agent.py | Complete live DeepSeek model → tools graph | Yes |
| checks.py | Offline regression checks | No |

For missing modules, install requirements with the same Python interpreter used to run the script. Set environment variables in that same terminal; CMD's `set` and PowerShell's `$env:` are different syntax. For budget exhaustion, inspect the trace and stopping condition before increasing the limit.

Framework reference: [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api). This chapter configures no persistence, concurrent scheduling, or automatic recovery; compilation does not prove business correctness.


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

Finally, modify `langgraph_scripted_agent.py` so the scripted model first calls `multiply`, then calls a new `add` tool, and only then returns a final answer. Do not change the graph topology. Then make the matching Tool-schema and argument-validation changes in `langgraph_deepseek_agent.py`.

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

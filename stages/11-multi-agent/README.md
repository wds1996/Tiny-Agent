# Stage 11: Need a Second Agent? Prove It — Multi-Agent Systems

> Language: **English** | [简体中文](README.zh-CN.md)

Stage 10 made it possible to compare one Agent’s answer, trajectory, latency, cost, and denial behavior. Only now is it useful to ask a question that architecture diagrams often hide: **did splitting work across Agents improve the result, or only add calls, Context transfer, and debugging difficulty?**

Multi-Agent does not mean “call a model more times,” and it does not mean giving one model several personality prompts. In this chapter it is a deliberate system design: relatively independent workers receive distinct tasks and bounded Context, then cooperate across observable, authorized, and evaluable boundaries.

The chapter follows this order:

```text
Decide whether to split work
    ↓
Define a Specialist's input, output, and responsibility
    ↓
Separate delegation from handoff
    ↓
Bound Context, permission, budgets, and loops
    ↓
Use evaluation to prove collaboration helped
    ↓
Discuss A2A only when systems must interoperate
```

The Python snippets in this chapter import the adjacent `team.py`. To paste a snippet into a Python session, first run `cd stages/11-multi-agent/code`; use the commands after their corresponding concepts when running a complete example from the repository root.

---

## 1. What concrete problem should a second Agent solve?

One ReAct Agent may call a model three times and still be one Agent. A second Agent matters only when there is a new worker boundary: different tasks, visible Context, Tools, permissions, maintenance ownership, or external system boundary.

These situations can justify a split:

| Problem to solve | Reasonable split |
| --- | --- |
| Orders and policy require different data and instructions | Orders Specialist and Policy Specialist |
| Subproblems are independent | Fan out, then let a Supervisor combine results |
| A high-impact capability belongs to another responsibility domain | A Specialist with its own approval, audit, and Tool policy |
| Another team maintains the Agent | A stable cross-system protocol boundary |

These reasons are not enough: a messy single-Agent prompt that nobody wants to simplify; framework diagrams with more boxes; five names for the same model; or hope that a Critic automatically makes output correct. Before splitting, run the same Stage 10 dataset against the single Agent and the proposed team. Compare pass rate, error types, average Tool calls, latency, and cost. Keep the extra Agent only when its measurable benefit justifies the new failure paths.

---

## 2. A Specialist is not a personality; it is a checkable boundary

The chapter’s smallest `Agent` interface accepts only a task and projected Context, then returns a structured `AgentMessage`. The important change is that an Agent boundary no longer returns untraceable free text. Its message carries the worker, status, summary, transferable data, and provenance.

```python
from team import AgentMessage, Specialist

orders = Specialist("orders", "order specialist")
message = orders.run(
    "Check the order status.",
    {"order_id": "ORDER-42"},
)

assert message.agent == "orders"
assert message.status == "completed"
assert message.data == {"order_id": "ORDER-42"}
assert message.provenance == ("specialist:orders",)
print(message.summary)
```

An `assert` is a Python assertion: the program raises an error when the condition is false. It turns the interface expectation in this example into a runnable check.

In a real system, `data` may contain an order state, retrieved evidence IDs, file references, or another validated structure. `provenance` records which Specialist or source supplied it. Neither field proves the content is correct, but they prevent three rounds of paraphrase from collapsing into “someone said it is allowed.”

A Specialist worth separating differs in at least one of task, Context, Tool, permission, data source, or service-level objective. Tone and personality can be useful prompting techniques; they are not reliable system boundaries.

---

## 3. Delegation and handoff: who still owns the overall task?

Both can look like “send work to another Agent,” but they have different control semantics.

| Form | Meaning | Owner of the original task |
| --- | --- | --- |
| **Delegation** | “Complete this subtask and return the result to me.” | The caller keeps ownership |
| **Handoff** | “You now continue the overall task.” | The target takes ownership |

This is a complete minimal Runtime setup and one delegation. `Principal` says on whose behalf the team works; `TeamPolicy` explicitly grants the `support` role access to the two Specialists.

```python
from team import (
    Delegation, Principal, Specialist, TeamBudget, TeamPolicy, TeamRuntime,
)

runtime = TeamRuntime(
    [
        Specialist("supervisor", "supervisor"),
        Specialist("orders", "order specialist"),
        Specialist("policy", "policy specialist"),
    ],
    policy=TeamPolicy({"support": frozenset({"orders", "policy"})}),
)
principal = Principal("user-7", frozenset({"support"}))
budget = TeamBudget()

result = runtime.delegate(
    caller="supervisor",
    principal=principal,
    delegation=Delegation("orders", "Check the order status.", ("order_id",)),
    shared_context={"order_id": "ORDER-42", "internal_secret": "do-not-send"},
    budget=budget,
)

assert result.agent == "orders"
assert result.data == {"order_id": "ORDER-42"}
assert budget.delegations == 1
```

`delegate()` returns the Specialist’s `AgentMessage` without changing the top-level owner. In contrast, `handoff()` returns a `TeamResult` whose `owner` becomes the target:

```python
handed = runtime.handoff(
    caller="supervisor",
    principal=principal,
    target="orders",
    task="Take ownership of the order follow-up.",
    shared_context={"order_id": "ORDER-42", "user_id": "user-7"},
    context_keys=("order_id", "user_id"),
    budget=budget,
)

assert handed.owner == "orders"
assert handed.message.agent == "orders"
```

A handoff is not permanent permission. It transfers control for this task; when the target invokes a real Tool, Stage 09 validation, authorization, approval, budget, and deadline rules must still apply.

---

## 4. Context projection and shared memory: ask who needs to see and modify what

Suppose a Supervisor holds:

```python
context = {
    "user_id": "user-7",
    "order_id": "ORDER-42",
    "policy_excerpt": "...",
    "internal_secret": "...",
}
```

An Orders Specialist needs only the order ID. `project_context()` uses an allowlist, rather than copying the whole dictionary and hoping the recipient ignores it:

```python
from team import project_context

orders_context = project_context(context, allowed_keys=("order_id",))
assert orders_context == {"order_id": "ORDER-42"}
```

This is **Context Projection**: taking the smallest view of a larger Context that one role needs to complete its work. It reduces noise, tokens, and unnecessary exposure. It is Stage 07 Context Engineering applied to a team.

“Let every Agent share Memory” is not a complete design. At minimum answer:

| Question | Required rule |
| --- | --- |
| Who owns this information? | Owner or namespace |
| Who may read it? | Read policy by role, task, or tenant |
| Who may change it? | Write policy, versioning, or append rule |
| Is it a fact or intermediate inference? | Type, provenance, and confidence |

`shared_global_dict = {}` is not a multi-Agent collaboration design. It supplies neither minimal exposure nor conflict, provenance, or write semantics.

---

## 5. Fan-out, budgets, and events: a team still needs limits

When order status and refund policy are independent, send them to separate Specialists first, then let the Supervisor combine them:

```text
Orders result ---\
                  -> Supervisor -> final answer
Policy result ---/
```

This is **fan-out / fan-in**. The chapter’s `fan_out()` deliberately runs its delegations sequentially. It demonstrates that the tasks are independent without pretending that they already execute in parallel.

```text
Fan-out      = task structure: which subproblems are independent
Concurrency  = execution policy: whether to start together, limit, and cancel work
```

Team loops hide easily: `Supervisor → Reviewer → Planner → Supervisor`. `TeamBudget` therefore limits delegations and handoffs separately; ownership transfer is a stronger control change.

```python
budget = TeamBudget(max_delegations=4, max_handoffs=1)
```

The teaching Runtime records successful transfers as a `TeamEvent`, containing only caller, target, projected keys, and status:

```text
TeamEvent(kind='delegation', caller='supervisor', target='orders',
          context_keys=('order_id',), status='completed')
```

This is a structured team trajectory. A production implementation should correlate it with Stage 10 `agent.run`, `policy.authorize`, `team.delegate`, and `team.handoff` spans under one `run_id`. “Agent failed” alone cannot distinguish no proposal, policy denial, exhausted budget, and Specialist failure.

The teaching code rejects the simplest `A → A` self-delegation. Longer cycles such as `A → B → C → A` need a team call stack or global graph detection. In either implementation, budgets and traces remain necessary.

Run the offline demo here to observe the Context each Specialist receives, the ownership change after handoff, and the `TeamEvent` left by every transfer:

```bash
python stages/11-multi-agent/code/demo.py
```

---

## 6. Internal collaboration still keeps the Stage 09 authorization boundary

“These are internal Agents” is not an authorization reason. `TeamRuntime` checks `TeamPolicy` before each delegation and handoff. Without an explicit grant it raises `PermissionError`; the default is deny.

```python
from team import Delegation, Principal, TeamBudget

intern = Principal("intern-1", frozenset({"intern"}))
try:
    runtime.delegate(
        caller="supervisor",
        principal=intern,
        delegation=Delegation("orders", "Check ORDER-42."),
        shared_context={},
        budget=TeamBudget(),
    )
except PermissionError as exc:
    print(exc)
```

This checks whether an identity may enter the Orders Specialist boundary. It does not replace authorization inside Orders itself. If Orders can issue refunds, its refund Tool must still validate the Principal, business policy, and required approval at its own execution boundary. Delegation cannot quietly amplify the Supervisor’s external authority.

---

## 7. Critics, error propagation, and evaluation: collaboration needs evidence

Adding a Critic is tempting:

```text
Generator -> Critic -> final
```

But a Critic can misjudge, omit evidence, or create another loop, and it always adds model-call cost and latency. It is not a free correctness button.

Use the Stage 10 dataset to compare:

```text
single Agent:  pass rate / latency / cost / unnecessary tools
team version:  pass rate / latency / cost / unnecessary delegations
```

Keep a Critic or extra Specialist only when important cases improve enough to justify the cost and failure paths.

Messages should preserve `status`, `data`, and `provenance`, because natural-language paraphrase can lose facts, sources, uncertainty, and error category. When a policy service times out, a Supervisor must not rewrite that into “the policy says no”; it should pass the structured failure into recovery or escalation logic.

Run the offline checks here. They verify Context allowlists, structured messages, delegation and handoff, default deny, budgets, self-delegation, unknown Agents, and isolated Context during fan-out:

```bash
python stages/11-multi-agent/code/checks.py
```

---

## 8. MCP, an in-process team, and A2A solve different boundaries

They often appear together, but they are not the same thing:

| Boundary | Primary object | Course example |
| --- | --- | --- |
| Agent ↔ Tool / Resource | Tools, data, Prompt providers | Stage 05 MCP |
| Agent ↔ Agent in one application | Supervisor and Specialist collaboration | This chapter’s `TeamRuntime` |
| Agent ↔ independent Agent system | Interoperation across teams, frameworks, or services | A2A |

If another system merely exposes `search_database`, it is closer to a Tool. If it receives a goal, plans its own work, maintains task lifecycle, and returns artifacts or stage state, it is closer to an independent Agent.

When the other Agent belongs to another system, in-process `runtime.delegate(...)` is insufficient. A2A (Agent2Agent) is an open protocol for independent Agent-system interoperability. It defines capability discovery, messages, task status, and artifact exchange; it does not decide whether splitting was wise, whether a remote system is trusted, or whether it is authorized. Read the [official A2A specification](https://a2a-protocol.org/latest/specification) and its [core concepts](https://a2a-protocol.org/latest/topics/key-concepts/).

A2A and MCP are complementary. A Specialist can use MCP for its own Tools and data, then use A2A to collaborate with another independent Agent.

---

## 9. A real DeepSeek team: a Supervisor delegates to real Specialists

Offline `Specialist` objects make Runtime semantics stable to inspect. The real-model integration is [`code/deepseek_team.py`](code/deepseek_team.py):

1. A DeepSeek Supervisor proposes `delegate_to_specialist` Tool Calls from the user task.
2. The Host validates the target and task, projects Context through `CONTEXT_KEYS_BY_SPECIALIST`, and calls `TeamRuntime.delegate()` for policy and budget checks.
3. An Orders or Policy Specialist makes its own real DeepSeek call and receives only its projected view.
4. The Host returns the structured `AgentMessage` as a Tool Result; the Supervisor produces the final answer.

```text
user
  ↓
DeepSeek supervisor
  ↓ delegate_to_specialist
Host policy + context projection + budget
  ↓
DeepSeek orders / policy specialist
  ↓ structured Tool Result
DeepSeek supervisor final answer
```

The order ID and policy excerpt are local teaching data. `internal_secret` intentionally exists in the Supervisor Context so you can observe that projection keeps it away from Specialists. The program does not connect to an order or payment system.

Install the dependency:

```bash
python -m pip install -r stages/11-multi-agent/code/requirements.txt
```

Windows Command Prompt (CMD):

```bat
set "DEEPSEEK_API_KEY=your_key_here"
set "DEEPSEEK_MODEL=your_available_deepseek_model"
python stages/11-multi-agent/code/deepseek_team.py
```

PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="your_available_deepseek_model"
python stages/11-multi-agent/code/deepseek_team.py
```

The live run observes the current model and service, so it is not a replacement for Stage 10’s fixed regression dataset.

---

## 10. From team collaboration to the Agent workspace

Multi-Agent systems do not leave us with conversation alone. As Agents generate artifacts, read and write files, run tests, and execute scripts, the next question becomes: **which files, processes, network paths, and credentials may they touch?**

That is [Stage 12: Agent Workspace and Sandbox](../12-agent-workspace-sandbox/README.md).

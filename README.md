<p align="center">
  <img src="assets/agent_readme.png" alt="Tiny-Agent — Learn Modern AI Agents from First Principles" width="100%" />
</p>

# Tiny-Agent: From One Model Call to an Engineered Agent System

> Language: **English** | [简体中文](README.zh-CN.md)

Many Agent tutorials start by installing a framework and calling `create_agent()`. The demo works. The harder questions arrive later: Why did the model repeat a Tool? Why did retrieval become “truth”? Who owns the side effect? What survives a restart? Why did context become unstable?

Tiny-Agent takes a mechanism-first path.

This is a zero-to-Agent engineering course. It begins with model calls, Structured Output, Tool Calling, runtimes, workflows, state, and retrieval. Only after those foundations exist do MCP, memory, context engineering, Skills, safety, evaluation, Multi-Agent coordination, sandboxing, production services, and long-horizon execution appear.

Frameworks are welcome, but they do not arrive before the problem they solve. The goal is not to memorize one generation of APIs. It is to be able to design a new Agent system and explain which decisions need a model, which control flow should remain ordinary code, what the model may propose, what the application may execute, and how the system stops, recovers, gets approval, and proves quality.

---

## Course map

The curriculum uses continuous integer Stages from `00` to `15`.

| Stage | Topic | Main question |
|---|---|---|
| [00](stages/00-foundations/README.md) | Foundations | How does a model call become a program-facing interface rather than arbitrary prose? |
| [01](stages/01-react-runtime/README.md) | ReAct Runtime | How does a Tool Call become a bounded Agent loop? |
| [02](stages/02-workflows-routing-planning/README.md) | Workflow / Routing / Planning | Which control decisions belong in code and which deserve model judgment? |
| [03](stages/03-stateful-orchestration/README.md) | Stateful Orchestration | How do we make complex execution state and transitions explicit? |
| [04](stages/04-agentic-rag/README.md) | Retrieval / Agentic RAG | How does an Agent obtain evidence and stop when evidence is insufficient? |
| [05](stages/05-mcp/README.md) | MCP | How are external Tools, Resources, and Prompts exposed across a standard protocol boundary? |
| [06](stages/06-memory-persistence-hitl/README.md) | Memory / Persistence / HITL | How does work survive process loss, what deserves retention, and where must a human decide? |
| [07](stages/07-context-engineering/README.md) | Context Engineering | Of everything we can retain, what should this model turn actually see? |
| [08](stages/08-agent-skills/README.md) | Agent Skills | How can reusable procedures be discovered and loaded only when needed? |
| [09](stages/09-reliability-safety/README.md) | Reliability / Safety | How do permissions, validation, retries, loops, deadlines, and budgets constrain real actions? |
| [10](stages/10-evaluation-observability/README.md) | Evaluation / Observability | How do we explain a trajectory and prove that a change improved the system? |
| [11](stages/11-multi-agent/README.md) | Multi-Agent | When is a second Agent actually justified? |
| [12](stages/12-agent-workspace-sandbox/README.md) | Workspace / Sandbox | What boundaries matter once an Agent can manipulate files and run code? |
| [13](stages/13-production-deployment/README.md) | Production Service | How does a local program become an identity-aware, backpressured, durable service? |
| [14](stages/14-long-horizon-harness/README.md) | Long-Horizon Harness | How can long work survive worker loss through ledgers, leases, and artifacts? |
| [15](stages/15-capstone-enterprise-agent/README.md) | Capstone | How do we select only the mechanisms a real domain actually needs? |

The intended path is sequential because later boundaries are built from earlier ones.

---

## How to study each Stage

Each Stage is self-contained:

```text
stages/<stage>/
├── README.md
├── README.zh-CN.md
└── code/
```

The README is the lesson. Code blocks inside the lesson show only the mechanism currently under discussion. The complete runnable program lives under that Stage's `code/` directory.

A useful learning loop is:

```text
read one section
    ↓
inspect the local snippet
    ↓
explain the problem it solves
    ↓
run the complete demo
    ↓
run checks.py / runtime_checks.py
    ↓
break one invariant deliberately
    ↓
explain the failure
```

Do not study only the happy path. Rejected inputs and bounded failures often teach the architecture more clearly.

---

## Running the code

Python 3.10+ is the baseline.

Many later Stages use only the standard library:

```bash
python stages/06-memory-persistence-hitl/code/demo.py
python stages/06-memory-persistence-hitl/code/checks.py
```

Stages with external dependencies declare them locally in `code/requirements.txt`:

```bash
python -m pip install -r stages/05-mcp/code/requirements.txt
python stages/05-mcp/code/in_memory_client.py
python stages/05-mcp/code/checks.py
```

The repository does not require one global “install every Agent dependency” environment. Install what the Stage you are studying actually needs.

Early stages include real provider adapters and explain their environment variables in the chapter. The course checks prefer deterministic model doubles, fake clients, or offline data whenever the invariant itself does not require a live model. A runtime should not need a lucky online generation to prove that it rejects unauthorized Tools, stops a loop, or avoids duplicate side effects.

---

## Why mechanisms come before frameworks

An abstraction becomes much easier to use when you know what it hides.

Stage 03 derives State, Node, Edge, and Reducer semantics before mapping them to LangGraph. Stage 04 derives chunking, vector representation, similarity, and Top-K retrieval before using vector backends. Stage 05 separates Function Calling from external protocol interoperability before introducing MCP.

This is not anti-framework. It is how frameworks stop feeling magical.

---

## One principle repeated throughout the course

If you remember one invariant, remember:

> **Proposal is not authority.**

The model may propose a Tool Call, Route, Plan, Memory Candidate, refund action, or delegation. Retrieved content may be relevant. A Skill may recommend using a capability. Another Agent may ask for work.

None of those facts automatically grants execution authority. Application-owned validation, policy, ownership, approval, authorization, and execution boundaries remain explicit.

---

## Repository structure

The repository intentionally stays course-shaped:

```text
Tiny-Agent/
├── README.md
├── README.zh-CN.md
├── CONTRIBUTING.md
├── CONTRIBUTING.zh-CN.md
├── LICENSE
└── stages/
    ├── 00-foundations/
    ├── 01-react-runtime/
    ├── ...
    └── 15-capstone-enterprise-agent/
```

Each Stage owns its complete teaching implementation and executable checks. There is no second global implementation or test tree that students must reconcile with chapter code.

---

## Prerequisites and outcome

Basic Python is enough to begin: functions, classes, `dict` / `list`, exceptions, basic JSON, and running Python from a terminal. Async programming, SQLite, subprocesses, graph orchestration, and service concepts are introduced when the course reaches a problem that needs them.

Finishing the course should mean more than “I can use an Agent framework.” Before choosing a framework for a new system, you should be able to reason about model decisions, structured contracts, Tool authority, state scope, durability, memory policy, context selection, evidence, retries, idempotency, approval, authorization, execution isolation, tracing, evaluation, service identity, and worker recovery.

When those boundaries are clear, frameworks become implementation choices rather than architecture substitutes.

Start with [Stage 00](stages/00-foundations/README.md).

---

## Star History

<a href="https://www.star-history.com/?repos=wds1996%2FTiny-Agent&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=wds1996/Tiny-Agent&type=date&theme=dark&legend=top-left&sealed_token=XS_WU0y8HydmsHz6LTueLxesinCg4gXRd-EpaRl6ATjiKesmm8eBUKFxeGsBdOVkvKn10SYjq0sZ1aD4SgzAIARbUcbD2g22nYQYpId-Pi95XI6qasNgGn6je9vJJTGhq3BJ9BlSQx1HfSqyII_bkFQNT6M3IEC-MoUe82x53EE2DIRiF4eoFQo-5yK_" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=wds1996/Tiny-Agent&type=date&legend=top-left&sealed_token=XS_WU0y8HydmsHz6LTueLxesinCg4gXRd-EpaRl6ATjiKesmm8eBUKFxeGsBdOVkvKn10SYjq0sZ1aD4SgzAIARbUcbD2g22nYQYpId-Pi95XI6qasNgGn6je9vJJTGhq3BJ9BlSQx1HfSqyII_bkFQNT6M3IEC-MoUe82x53EE2DIRiF4eoFQo-5yK_" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=wds1996/Tiny-Agent&type=date&legend=top-left&sealed_token=XS_WU0y8HydmsHz6LTueLxesinCg4gXRd-EpaRl6ATjiKesmm8eBUKFxeGsBdOVkvKn10SYjq0sZ1aD4SgzAIARbUcbD2g22nYQYpId-Pi95XI6qasNgGn6je9vJJTGhq3BJ9BlSQx1HfSqyII_bkFQNT6M3IEC-MoUe82x53EE2DIRiF4eoFQo-5yK_" />
 </picture>
</a>

<p align="center">Track Tiny-Agent's growth on Star History.</p>

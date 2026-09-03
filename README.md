<p align="center">
  <img src="assets/agent_readme.png" alt="Tiny-Agent — Learn Modern AI Agents from First Principles" width="100%" />
</p>

<h1 align="center">Tiny-Agent</h1>

<p align="center">
  🌐 Language / 语言：<a href="README.zh-CN.md"><strong>中文</strong></a> | <strong>English</strong>
</p>

**A mechanism-first, production-minded learning path for modern AI Agent systems — from one ToolCall to context engineering, MCP, memory, safety, evaluation, multi-Agent interoperability, sandboxed workspaces, durable long-horizon harnesses, and a complete research Agent capstone.**

Tiny-Agent is designed for people who do not want to learn Agents as a collection of framework decorators.

The repository repeatedly follows this order:

```text
Why does this abstraction exist?
        ↓
Build the mechanism in ordinary Python
        ↓
Test the edge cases
        ↓
Map it to current frameworks/protocols
        ↓
State what the abstraction does NOT solve
```

## Core engineering principles

1. **Model output is a proposal, not authority.**
2. **Use the least dynamic architecture that solves the task well.**
3. **State, context, checkpoint, memory, evidence, and artifacts are different scopes.**
4. **Discovery is not authorization.**
5. **Approval is not authorization.**
6. **Retryable failure is not the same as retry-safe operation.**
7. **Retrieved/remote content is untrusted data, not control policy.**
8. **A graph is orchestration, not automatically an Agent.**
9. **More Agents are not automatically better.**
10. **A subprocess is not a security sandbox.**
11. **A large context window is capacity, not a reason to send everything.**
12. **Skills teach procedures; Tools expose capabilities; memory retains selected information.**
13. **Durable execution externalizes progress instead of depending on one model session/process.**
14. **Correct final text can still come from a failed/unsafe Agent trajectory.**
15. **Frameworks/protocols own plumbing; the application owns meaning and policy.**

---

# 2026 curriculum

The numbered stages are the original capability progression. The lettered extension stages were added after a full-project 2026 audit so the repository could cover modern context/skills/sandbox/harness patterns without renumbering mature historical stages.

| Stage | Capability | Main question |
|---|---|---|
| [00](stages/00-foundations/) | LLM / messages / Structured Output / Tool Calling / model & context basics | What does the model actually do, and what remains application responsibility? |
| [01](stages/01-react-runtime/) | ReAct & core runtime | How does one ToolCall become a bounded decide-act-observe loop? |
| [02](stages/02-planning-routing/) | Workflow / routing / planning | Which control decisions should be deterministic vs model-driven? |
| [03](stages/03-stateful-orchestration/) | Explicit state & LangGraph | When does a state machine/graph runtime become useful? |
| [04](stages/04-agentic-rag/) | RAG & Agentic retrieval | How does an Agent obtain and evaluate external evidence? |
| [05](stages/05-mcp/) | MCP 2026 | How are external capabilities/context standardized across boundaries? |
| [06](stages/06-memory-persistence-hitl/) | Memory / durability / HITL | What should survive, and how can execution pause/resume safely? |
| [06A](stages/06a-context-engineering/) | Context Engineering | What should the model see on this exact turn under a finite attention budget? |
| [06B](stages/06b-agent-skills/) | Agent Skills | How is reusable procedural knowledge discovered and loaded on demand? |
| [07](stages/07-reliability-safety/) | Reliability / safety / governance | How do we bound, validate, authorize, retry, and refuse execution? |
| [08](stages/08-evaluation-observability/) | Tracing & evaluation | What happened, was it good, and did a new version regress? |
| [09](stages/09-multi-agent/) | Multi-Agent / A2A | When does delegation/handoff create measurable value? |
| [09A](stages/09a-agent-workspace-sandbox/) | Workspace & sandbox compute | Where can an Agent inspect files/run commands without handing it the host machine? |
| [10](stages/10-production-deployment/) | Production service / identity / durable jobs | What changes when other users/Agents depend on the service? |
| [10A](stages/10a-long-horizon-harness/) | Long-horizon harness | How does an Agent keep making progress across sessions, workers, and sandbox loss? |
| [11](stages/11-capstone-enterprise-agent/) | OpenScholar capstone | Can all relevant mechanisms compose into one evidence-grounded Agent system? |

Detailed competency coverage: **[Modern Agent Competency Map](docs/modern-agent-competency-map.md)**  
Framework/protocol mapping: **[Framework & Tooling Map](docs/framework-and-tooling-map.md)**

---

# Capability ladder

```text
LLM call
  ↓
Structured decision / ToolCall
  ↓
ReAct runtime
  ↓
workflow / router / planner
  ↓
explicit state graph
  ↓
retrieval and external evidence
  ↓
MCP capability boundary
  ↓
memory / checkpoint / HITL
  ↓
context engineering + Agent Skills
  ↓
reliability / permissions / budgets
  ↓
tracing / evaluation / regression
  ↓
multi-Agent / A2A
  ↓
governed workspace / sandbox compute
  ↓
production identity / jobs / infrastructure
  ↓
long-horizon resumable harness
  ↓
OpenScholar capstone
```

The project deliberately does **not** say the bottom of this diagram is always better. Use only the complexity your task needs.

---

# What is implemented from first principles?

Reusable code under `src/tiny_agent/` includes:

```text
runtime.py                 ReAct-style loop
workflows.py               routing / planning / replanning
state_graph.py             handwritten graph mechanism
retrieval.py               chunking / embeddings / cosine / top-k
rag.py                     Basic + Agentic RAG
mcp_bridge.py              MCP Tool normalization
memory_policy.py           governed memory candidates
approval.py                approve/edit/reject
context_engineering.py     context budget / selection / compaction
skills.py                  SKILL.md catalog + progressive activation
reliability.py             failures / retries / budgets / loop detection
governance.py              principals / permissions / exact approval binding
guarded_runtime.py         composed execution policy
observability.py           local traces/spans
evaluation.py              datasets / graders / regression gates
multi_agent.py             delegation / handoff / fan-out / context projection
workspace.py               workspace confinement + Docker sandbox baseline
jobs.py                    durable local run queue + leases
service_identity.py        trusted identity/tenant binding
production.py              bounded service execution + readiness
harness.py                 durable task ledger + long-horizon handoffs
capstone/                  OpenScholar domain + orchestration + eval
integrations/              OpenAI / FastAPI / MCP / A2A / OTel / DB adapters
```

Framework integrations are introduced only after their underlying mechanism is visible.

---

# Modern Agent distinctions you should know

```text
Structured Output != Tool Calling
Tool Calling != Tool execution
Tool != Skill
Skill != Memory
MCP != A2A
Retriever != Vector Store
RAG != Agent
State != Context
Checkpoint != Long-term Memory
Graph != Agent
Delegation != Handoff
Discovery != Authorization
Approval != Authorization
Timeout != Hard termination
Subprocess != Sandbox
Service run != Agent checkpoint != long-horizon task ledger
```

If those distinctions are precise, most framework APIs become much easier to reason about.

---

# Installation

Core mechanisms are dependency-light:

```bash
python -m pip install -e ".[dev]"
```

Selected extras:

```bash
python -m pip install -e ".[openai]"
python -m pip install -e ".[dev,stage03]"   # LangGraph / LangChain
python -m pip install -e ".[dev,stage04]"   # FAISS / Qdrant / LangChain retrieval
python -m pip install -e ".[dev,stage05]"   # MCP v2
python -m pip install -e ".[dev,stage06]"   # SQLite/Postgres checkpointing
python -m pip install -e ".[dev,stage06b]"  # Agent Skills YAML parsing
python -m pip install -e ".[dev,stage07]"   # jsonschema / Pydantic / Tenacity
python -m pip install -e ".[dev,stage08]"   # LangSmith / OpenTelemetry
python -m pip install -e ".[dev,stage09]"   # OpenAI Agents SDK / A2A
python -m pip install -e ".[dev,stage10]"   # FastAPI / Postgres / Redis / A2A server
python -m pip install -e ".[dev,stage11]"   # complete OpenScholar integrations
```

Stages 06A, 09A, and 10A use the standard library plus Tiny-Agent core for their handwritten mechanisms. Docker is an external runtime requirement only for actually executing the Stage 09A container sandbox example.

---

# Agent mechanism verification

The `tests/` directory is part of the Agent learning material: it shows how the runtime semantics taught in the course are verified deterministically. It is **not** a place for unrelated repository-maintenance checks.

The verification suite covers:

- runtime/tool edge cases;
- Structured Output/provider adapters;
- planning/replanning budgets;
- handwritten/LangGraph state semantics;
- FAISS/Qdrant retrieval;
- MCP v2 server/client/transport paths;
- durable SQLite/Postgres checkpoint and HITL;
- validation/retry/permission/approval/injection boundaries;
- tracing/evaluation/regression gates;
- multi-Agent ownership, context isolation, handoff loops, A2A objects;
- FastAPI/Postgres/Redis/A2A service integration;
- context-budget/compaction behavior;
- Agent Skill discovery/activation;
- workspace path confinement and Docker command hardening;
- durable job leases and long-horizon resume;
- OpenScholar evidence/citation/semantic-support and authenticated bounded serving.

Run these Agent mechanism and integration checks directly with `pytest`; repository-maintenance automation is intentionally kept outside the learning tree.

---

# OpenScholar final capstone

Stage 11 is intentionally not “one more framework demo.”

It combines:

```text
bounded planning
+ local full-text RAG
+ scholarly metadata discovery
+ explicit evidence trust classes
+ evidence abstention
+ reviewer/writer coordination
+ governed memory
+ HITL export
+ deterministic + optional semantic citation evaluation
+ traces/metrics
+ MCP / A2A / HTTP boundaries
+ real semantic embedding/Qdrant production path
+ trusted service identity
+ BoundedAgentService
```

The offline default remains reproducible and API-key free. Production infrastructure is injected behind the same domain boundaries.

The repository does not pretend that a demo API key, local SQLite, ordinary Docker, or one vector database automatically satisfies every enterprise IAM/compliance/multi-tenant threat model. The goal is to teach and test the correct **semantics and composition points**.

---

# 2026 reference anchors

Tiny-Agent tracks current concepts/APIs rather than freezing old tutorials:

- OpenAI model/API docs — https://platform.openai.com/docs/
- OpenAI Agents SDK 2026 harness/sandbox direction — https://openai.com/index/the-next-evolution-of-the-agents-sdk/
- LangGraph/LangChain docs — https://docs.langchain.com/
- MCP 2026-07-28 — https://blog.modelcontextprotocol.io/posts/2026-07-28/
- Agent Skills open specification — https://agentskills.io/specification
- A2A specification — https://a2a-protocol.org/latest/specification/
- Anthropic context engineering — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Anthropic long-running harness guidance — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- OWASP GenAI Security — https://genai.owasp.org/
- OpenTelemetry — https://opentelemetry.io/

Version-specific framework code is covered by deterministic and integration tests in `tests/`; if an external tutorial conflicts with current official docs or the repository's dependency range, prefer the current official docs.

---

# Repository philosophy

Tiny-Agent is a learning repository, but “learning” is not an excuse for architecture that teaches dangerous habits.

Teaching implementations are intentionally small and inspectable, while limitations are named explicitly. Production examples then add the missing mechanisms rather than retroactively pretending the small example was enterprise-ready all along.

---

# ⭐ Support Tiny-Agent

If Tiny-Agent helps you understand or build modern AI Agents, a GitHub Star is one of the simplest ways to support the project and help more learners discover it.

<p align="center">
  <a href="https://github.com/wds1996/Tiny-Agent"><strong>⭐ If Tiny-Agent helps you, please consider giving it a Star!</strong></a>
</p>

---

# Star History

<p align="center">
  <a href="https://www.star-history.com/wds1996/Tiny-Agent">
    <img src="https://api.star-history.com/badge?repo=wds1996/Tiny-Agent&type=rank" alt="Tiny-Agent Star History Rank" />
  </a>
</p>

<p align="center">Track Tiny-Agent's growth on Star History.</p>

---

# 🙏 Acknowledgements

Tiny-Agent stands on the work of a broad open-source and standards community. Special thanks to:

- [OpenAI](https://openai.com/) and the OpenAI API / Agents ecosystem for model, Tool Calling, evaluation, and Agent-runtime references;
- [LangChain / LangGraph](https://docs.langchain.com/) for stateful orchestration, persistence, memory, and Agent framework patterns;
- the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) community for open capability/context interoperability;
- the [A2A](https://a2a-protocol.org/) community for Agent-to-Agent interoperability;
- the [Agent Skills](https://agentskills.io/) open specification for portable procedural knowledge;
- [OWASP GenAI Security](https://genai.owasp.org/) for practical threat models and security guidance;
- [Happy-LLM](https://github.com/datawhalechina/happy-llm) and other excellent open-source learning projects for demonstrating how complex AI topics can be made approachable and well-presented;
- [Star History](https://www.star-history.com/) for open-source project growth visualization;
- every learner, reader, and developer who studies the material, reports unclear explanations, or shares Tiny-Agent with others.

These acknowledgements recognize technical references and inspiration; they do not imply affiliation with or endorsement by the organizations and projects listed above.

---

# License

Tiny-Agent is released under the [MIT License](LICENSE).

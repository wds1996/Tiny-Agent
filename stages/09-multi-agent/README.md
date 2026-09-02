# Stage 09 — Multi-Agent Systems, Handoffs & A2A Interoperability

## Why this stage exists

Tiny-Agent deliberately waits until Stage 09 before teaching multi-Agent systems.

Before splitting work across Agents, you should already understand:

- single-Agent Tool loops;
- deterministic workflows and planning;
- explicit state and LangGraph;
- RAG and remote capabilities;
- memory/persistence/HITL;
- reliability, permissions and budgets;
- tracing and evaluation.

Otherwise multi-Agent often becomes a way to hide unclear architecture behind more LLM calls.

The central Stage 09 question is:

> **Does splitting responsibility across Agents create measurable value that justifies the extra coordination, latency, cost, and failure surface?**

---

# Learning goals

By the end of Stage 09 you should be able to explain and implement:

1. when a deterministic workflow or one Agent is better than a team;
2. specialist Agents with explicit responsibility boundaries;
3. manager-style delegation where the manager keeps control;
4. handoffs where conversation ownership changes;
5. supervisor/worker orchestration;
6. controlled context projection instead of full-state copying;
7. parallel fan-out / application-owned fan-in;
8. delegation allowlists, handoff budgets and loop protection;
9. multi-Agent evaluation against a single-Agent baseline;
10. OpenAI Agents SDK `Agent.as_tool()` vs handoffs;
11. A2A 1.0 Agent Cards, Messages, Tasks, Parts and Artifacts;
12. the difference between MCP capability interoperability and A2A Agent interoperability.

---

# Stage 09 mental model

```text
                   Application policy
                         |
              +----------+----------+
              |                     |
        DelegationPolicy        ContextPolicy
              |                     |
              +----------+----------+
                         |
                         v
                    TeamRuntime
                         |
          +--------------+--------------+
          |              |              |
       delegate        handoff        fan_out
          |              |              |
          v              v              v
     specialist     new active     parallel workers
       returns          Agent              |
          |              |                 v
          +--------------+------------> application fan-in
```

The model may propose a destination.

The application still owns:

```text
registered Agents
allowed edges
context visibility
coordination budget
Tool permissions
approval
stop conditions
```

---

# The two most important control semantics

## Delegation / Agent as Tool

```text
user
 |
 v
manager
 |  bounded specialist request
 v
specialist
 |  result
 v
manager
 |
 v
user
```

The manager remains the active/user-facing Agent.

Use this when the specialist should **help**, not take over.

## Handoff

```text
user
 |
 v
triage
 | transfer ownership
 v
specialist
 |
 v
user
```

The specialist becomes the active Agent after a successful transfer.

Use this when domain ownership genuinely changes.

---

# What this stage implements from scratch

`src/tiny_agent/multi_agent.py` adds:

- `AgentSpec`;
- `AgentInput`;
- `ContextEnvelope`;
- `ContextPolicy`;
- `DelegationPolicy`;
- `CoordinationBudget`;
- `CoordinationState`;
- `AgentInteraction`;
- `AgentInvocation`;
- `TeamRuntime.delegate()`;
- `TeamRuntime.handoff()`;
- `TeamRuntime.fan_out()`;
- `coordination_metrics()`.

The handwritten core intentionally supports text outputs only. This keeps the coordination mechanism inspectable before framework/runtime-specific structured output is introduced.

---

# Important invariants

## 1. Model-proposed Agent names are not authority

```text
model proposes "refund_agent"
        |
        v
registry + DelegationPolicy
        |
      allow/deny
```

Unknown or forbidden Agents are rejected before execution.

## 2. Delegation does not change active ownership

```python
await team.delegate(...)
assert state.active_agent == "manager"
```

## 3. Handoff changes ownership only after success

```text
source -> target invocation fails
        -> active Agent remains source
```

## 4. Context is projected

```text
full application state
      X
      |
      v
specialist
```

Instead:

```text
ContextEnvelope
      |
ContextPolicy
      |
minimal Agent view
```

## 5. Coordination state is run-scoped

Budgets and handoff history belong to one logical run, just like Stage 07's `GuardedRunState`.

## 6. Parallel batches are fully validated before launch

A denied second worker must not partially consume the first worker's budget when no worker actually started.

## 7. Worker exceptions are not copied into cross-Agent output

The local core records only the exception type in failed `AgentInvocation` results.

## 8. Handoff loops are bounded

Repeated transfer edges and total handoffs have deterministic limits.

---

# A2A interoperability target

Stage 09 targets:

```text
A2A specification: 1.0
Python SDK line:    1.1.x
```

The official A2A specification currently describes independent, potentially opaque Agent systems that can:

- discover one another through Agent Cards;
- exchange Messages and typed Parts;
- create stateful Tasks;
- deliver Artifacts;
- stream progress;
- support asynchronous/long-running interaction.

Tiny-Agent constructs current A2A 1.0 Agent Card and Message objects offline. A complete network server/client deployment is intentionally deferred to Stage 10, where service identity, HTTP serving, task storage and deployment can be taught honestly.

---

# MCP vs A2A

```text
MCP
Agent/Application
      |
      v
Tools / Resources / Prompts
```

```text
A2A
Agent System A
      |
      v
Agent System B
```

A remote A2A Agent may internally use MCP, LangGraph, OpenAI Agents SDK, custom code, or something else entirely.

The caller does not need access to that internal topology.

---

# OpenAI Agents SDK mapping

Current OpenAI Agents SDK exposes the same two control semantics this stage implements by hand.

## Manager pattern

```python
specialist_tool = specialist.as_tool(
    tool_name="research_expert",
    tool_description="Handle a bounded research subtask",
)

manager = Agent(
    ...,
    tools=[specialist_tool],
)
```

The specialist runs behind the manager.

## Handoff pattern

```python
triage = Agent(
    ...,
    handoffs=[refund_agent],
)
```

The selected specialist takes over the conversation.

The SDK example in this stage only builds and inspects these structures; it makes no real model call and requires no API key.

---

# Learning order

Read/run Stage 09 in this order:

1. `theory/01-when-to-use-multiple-agents.md`
2. `code/one_agent_vs_team.py`
3. `theory/02-delegation-handoffs-supervision.md`
4. `code/specialist_team.py`
5. `code/handoff_demo.py`
6. `code/supervisor_workers.py`
7. `theory/03-context-ownership-and-shared-state.md`
8. `code/context_isolation.py`
9. `theory/04-parallelism-and-coordination.md`
10. `code/parallel_fanout.py`
11. `theory/05-delegation-governance.md`
12. `code/delegation_governance.py`
13. `theory/06-a2a-interoperability.md`
14. `code/a2a_protocol_objects.py`
15. `theory/07-framework-mapping-and-evaluation.md`
16. `code/openai_agents_patterns.py`
17. `code/multi_agent_eval.py`
18. `exercises/review-questions.md`

---

# Runnable examples

```text
code/
├── one_agent_vs_team.py
├── specialist_team.py
├── handoff_demo.py
├── supervisor_workers.py
├── parallel_fanout.py
├── context_isolation.py
├── delegation_governance.py
├── openai_agents_patterns.py
├── a2a_protocol_objects.py
└── multi_agent_eval.py
```

All examples run without a live model API.

The OpenAI Agents SDK and A2A examples verify object/API compatibility only; they do not contact remote services.

---

# Theory chapters

```text
theory/
├── 01-when-to-use-multiple-agents.md
├── 02-delegation-handoffs-supervision.md
├── 03-context-ownership-and-shared-state.md
├── 04-parallelism-and-coordination.md
├── 05-delegation-governance.md
├── 06-a2a-interoperability.md
└── 07-framework-mapping-and-evaluation.md
```

---

# Installation

Core multi-Agent mechanisms remain dependency-free:

```bash
python -m pip install -e ".[dev]"
```

For Stage 09 framework/interoperability comparisons:

```bash
python -m pip install -e ".[dev,stage09]"
```

Stage 09 optional dependencies target:

```text
openai-agents >= 0.22, < 1
a2a-sdk       >= 1.1, < 2
```

The A2A protocol teaching target is **1.0**.

---

# Tests

Framework-neutral coordination tests:

```bash
pytest -q tests/test_multi_agent.py
```

Current SDK compatibility tests:

```bash
pytest -q tests/test_stage09_integrations.py
```

The dedicated CI matrix runs both Python 3.10 and 3.12 and smoke-tests every public Stage 09 example.

---

# What the tests protect

Core tests cover:

- manager ownership after delegation;
- successful handoff ownership transfer;
- failed handoff rollback of active ownership;
- exception-message redaction between Agents;
- default-deny delegation;
- active-Agent control rules;
- repeated-handoff-edge protection;
- parallel result ordering;
- atomic parallel prevalidation;
- parallel width limits;
- unknown Agent behavior;
- non-text worker output handling;
- coordination metrics.

Integration tests cover:

- current OpenAI Agents SDK `Agent.as_tool()` structure;
- current OpenAI Agents SDK `handoffs` structure;
- current A2A 1.0 `AgentCard` interface layout;
- current A2A `Message` / `Part` / `SendMessageRequest` construction.

---

# External resources

## OpenAI Agents SDK

Recommended order:

1. Agents overview  
   https://openai.github.io/openai-agents-python/agents/
2. Agent orchestration  
   https://openai.github.io/openai-agents-python/multi_agent/
3. Agents as tools  
   https://openai.github.io/openai-agents-python/tools/
4. Handoffs  
   https://openai.github.io/openai-agents-python/handoffs/

Focus on the difference between:

```text
specialist as Tool
vs
specialist takes over conversation
```

## A2A

Recommended order:

1. Overview/specification  
   https://a2a-protocol.org/latest/specification/
2. Core concepts  
   https://a2a-protocol.org/latest/topics/key-concepts/
3. What's new in A2A 1.0  
   https://a2a-protocol.org/latest/whats-new-v1/
4. Python SDK reference  
   https://a2a-protocol.org/latest/sdk/python/api/

When reading older A2A tutorials, check the protocol version. A2A 1.0 changed several operation and Agent Card shapes from 0.3-era material.

## LangGraph comparison

Stage 03 already teaches state graphs. Revisit subgraphs/supervisor patterns after you understand the Stage 09 mechanisms:

- https://docs.langchain.com/oss/python/langgraph/graph-api
- https://docs.langchain.com/oss/python/langchain/multi-agent

The important comparison is not syntax; it is how graph nodes/subgraphs make control and shared state explicit.

---

# Interview-ready distinctions

You should be able to answer these clearly:

```text
Workflow != Multi-Agent
Multiple model calls != Multi-Agent
Agent as Tool != Handoff
Shared context != copy all state
Discovery != authorization
Delegation != privilege escalation
Parallelism != free speed
A2A != MCP
Agent Card != internal Tool registry
Correct final answer != good coordination trajectory
```

---

# Stage 09 milestone

By the end of the stage, you should be able to build a small specialist team where:

```text
manager
├── delegates bounded work
├── can hand off conversation ownership
├── projects minimum context
├── limits Agent calls/handoffs
├── can fan out independent work
└── exposes coordination metrics
```

and then answer the harder question:

> **Does this team actually outperform the simpler single-Agent/workflow baseline enough to justify itself?**

---

# Stage boundary

This stage does **not** claim to implement:

- enterprise distributed Agent registries;
- production A2A HTTP/gRPC servers;
- durable A2A task stores;
- service-mesh authorization;
- distributed transactions;
- cross-service exactly-once semantics;
- full remote cancellation guarantees;
- hardened sandboxing for remote Agents;
- multi-region scheduling;
- production-scale queue/worker infrastructure.

Those belong with Stage 10 deployment and infrastructure.

Stage 09 establishes the architecture and interoperability semantics first.

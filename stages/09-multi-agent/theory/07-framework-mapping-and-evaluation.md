# 07 — Framework Mapping, Evaluation & Production Boundaries

Stage 09 deliberately implements coordination mechanisms before introducing a multi-Agent runtime framework.

The goal is to understand what frameworks automate and what application policy still remains yours.

---

## 1. Tiny-Agent handwritten mapping

The Stage 09 core has:

```text
AgentSpec
ContextEnvelope / ContextPolicy
DelegationPolicy
CoordinationBudget / CoordinationState
TeamRuntime.delegate()
TeamRuntime.handoff()
TeamRuntime.fan_out()
```

These abstractions expose the control semantics directly.

---

## 2. OpenAI Agents SDK mapping

Current OpenAI Agents SDK has two especially useful multi-Agent patterns.

### Manager / agents as tools

```text
Tiny-Agent delegate()
        ~
Agent.as_tool()
```

The specialist performs a bounded nested run and returns to the manager.

### Handoff

```text
Tiny-Agent handoff()
        ~
Agent(..., handoffs=[...])
```

The target Agent takes over the conversation.

Official resources:

- https://openai.github.io/openai-agents-python/agents/
- https://openai.github.io/openai-agents-python/multi_agent/
- https://openai.github.io/openai-agents-python/tools/
- https://openai.github.io/openai-agents-python/handoffs/

---

## 3. What the SDK adds

A mature runtime can manage:

- model turns;
- specialist invocation;
- handoff transfer;
- schemas;
- sessions;
- guardrails;
- tracing;
- approval flows;
- streaming.

That removes plumbing.

It does **not** decide your product's correct authority model, context-minimization policy, or business success metric.

---

## 4. LangGraph mapping

LangGraph gives another useful representation:

```text
Agent / supervisor / specialist
       -> graph node or subgraph
handoff/routing
       -> conditional graph transition
shared state
       -> explicit graph state
persistence
       -> checkpointer / Store
```

Supervisor libraries can package common patterns, but the Stage 03 principle still applies:

> Graph structure is not automatically Agent intelligence.

If routing is deterministic, encode the edge deterministically.

---

## 5. Why not add every framework

You can find multi-Agent examples in:

- OpenAI Agents SDK;
- LangGraph/LangChain;
- AutoGen-style systems;
- Crew-style systems;
- custom runtimes.

Tiny-Agent does not need to install all of them to teach the architecture.

The transferable questions are:

```text
Who owns control?
Who sees which context?
Who may call whom?
What is the stop condition?
How are failures handled?
How is benefit measured?
```

Framework syntax changes faster than those questions.

---

## 6. Evaluate against a simpler baseline

Stage 09 should never benchmark multi-Agent only against itself.

Compare:

```text
single Agent baseline
vs
multi-Agent candidate
```

Measure at least:

```text
quality
success rate
latency
cost
Agent-call attempts
handoff attempts / successful handoffs
failure rate
policy violations
```

A result like:

```text
quality +1%
latency +180%
cost +250%
```

may not justify the team.

---

## 7. Coordination metrics

Tiny-Agent provides `coordination_metrics(state)`:

```text
agent_call_attempts
handoff_attempts
successful_handoffs
unique_agents
failed_agent_calls
```

Attempts are counted even when the target later fails because failed coordination still consumes budget, latency, and potentially model/API capacity. Successful handoffs are reported separately so an operational attempt counter is not mistaken for a successful ownership-transfer count.

These metrics fit naturally into Stage 08 `RunArtifact.metrics`.

You can add product-specific metrics such as:

```text
handoff_accuracy
constraint_preservation
specialist_acceptance_rate
parallel_efficiency
coordination_cost
```

---

## 8. Handoff accuracy

A useful dataset can label:

```text
input -> expected owner Agent
```

Then evaluate:

```text
Did triage choose the correct specialist?
```

This is conceptually similar to Stage 02 router evaluation, but now a wrong route may transfer conversation ownership.

The cost of a routing error is therefore higher.

---

## 9. Delegation quality

A supervisor can choose the right specialist but send the wrong subtask.

Evaluate separately:

```text
destination correctness
subtask/constraint correctness
worker output correctness
final synthesis correctness
```

One final-answer score cannot diagnose all four.

---

## 10. Trajectory evaluation becomes Agent-aware

A Stage 09 trajectory may look like:

```text
manager
-> research
-> manager
-> reviewer
-> manager
```

or:

```text
triage
-> refund
```

Useful constraints:

```text
forbidden Agent edges
maximum handoff attempts
required specialist
no repeated ping-pong
no unauthorized remote Agent
```

Stage 08 trajectory-evaluation concepts apply directly.

---

## 11. Tracing should preserve Agent identity

A useful trace can show:

```text
invoke_agent manager
├── delegate research
│   └── invoke_agent research
└── delegate reviewer
    └── invoke_agent reviewer
```

Attributes may include:

```text
source_agent
target_agent
coordination.mode
```

But raw hidden prompts/private context should still follow Stage 08 capture policy.

---

## 12. Multi-Agent tests should include failure topology

Do not test only happy-path answers.

Test:

- denied delegation;
- unknown Agent;
- handoff failure;
- handoff loop;
- exhausted call budget;
- invalid parallel batch;
- private-context isolation;
- malformed worker output;
- remote Agent failure;
- result conflict.

Architecture quality lives in edge cases.

---

## 13. Production boundary

Stage 09 does not claim to solve:

```text
distributed Agent discovery registry
enterprise service identity
cross-service transactions
durable distributed queues
remote cancellation guarantees
A2A task database
multi-region routing
service mesh policy
full distributed tracing
```

These need Stage 10 deployment infrastructure.

---

## 14. Recommended learning order

```text
1. one Agent vs team decision
2. manager delegation
3. handoff
4. context isolation
5. parallel fan-out/fan-in
6. governance and loops
7. OpenAI Agents SDK mapping
8. A2A 1.0 interoperability
9. compare against single-Agent baseline
```

Do not start by memorizing framework decorators.

---

## 15. Final Stage 09 principle

> **A good multi-Agent architecture makes responsibility clearer, not merely more distributed.**

If adding Agents makes ownership, context, permissions, failure handling, and evaluation harder to explain, the architecture probably became more complicated faster than it became more capable.

# Stage 11 Review Questions & Exercises

Use these after completing the theory and runnable examples.

---

# Part A — Core concepts

## 1. What is the strongest reason to use multiple Agents?

Do not answer "because the task is complex."

Explain in terms of responsibility, context, tools, authority, ownership transfer, parallelism, deployment boundaries, or interoperability.

## 2. Why can a deterministic workflow with four model calls still be a single workflow rather than a four-Agent system?

## 3. Give three examples where a plain function or workflow is better than multi-Agent orchestration.

## 4. Can two Agents use the same foundation model and still be architecturally distinct? Why?

## 5. Can two different models be used inside one workflow without creating a multi-Agent architecture? Why?

---

# Part B — Delegation vs handoff

## 6. Explain the semantic difference between:

```text
manager -> specialist as Tool
```

and:

```text
triage -> handoff -> specialist
```

Focus on conversation ownership.

## 7. In Tiny-Agent, why does `delegate()` leave `state.active_agent` unchanged?

## 8. Why should a failed `handoff()` keep the source Agent active?

## 9. A manager delegates to a research specialist, receives a report, and writes the final answer. Is this a handoff? Explain.

## 10. A support Agent transfers the customer conversation to billing, and billing directly continues with the user. Is this delegation-as-tool or handoff?

---

# Part C — Context and state

## 11. Why is forwarding the complete application state to every specialist risky?

List at least four risks.

## 12. Explain the purpose of:

```text
ContextEnvelope.shared
ContextEnvelope.private_by_agent
ContextPolicy.allowed_shared_keys
```

## 13. Suppose the full state contains:

```text
question
customer_id
api_key
legal_notes
billing_token
```

Design the minimum context projection for:

- research Agent;
- billing Agent;
- writer Agent.

## 14. What is the difference between conversation history and runtime state during a handoff?

## 15. Why should non-negotiable constraints remain structured instead of being compressed into an LLM-generated summary?

---

# Part D — Coordination and parallelism

## 16. When is fan-out/fan-in useful?

## 17. Why is this wrong?

```text
retrieve evidence
read evidence
write conclusion
```

run all three in parallel.

## 18. What does `asyncio.gather()` solve, and what coordination problems does it *not* solve?

## 19. Why does Tiny-Agent validate an entire fan-out batch before reserving call budget?

## 20. Design a policy for three workers where one fails. Compare:

- fail-fast;
- partial result;
- retry;
- fallback specialist.

## 21. Explain the difference between completion order and result order in `asyncio.gather()`.

---

# Part E — Loops and failure modes

## 22. Compare a Tool loop with a handoff loop.

## 23. Why is this dangerous?

```text
triage -> billing -> triage -> billing -> ...
```

## 24. Tiny-Agent limits repeated handoff edges. What semantic loops can still escape an exact-edge detector?

## 25. Give an example of a deadlock-like multi-Agent dependency without using actual OS locks.

## 26. Why can three Agents using the same model, evidence, and prompt assumptions produce correlated errors rather than independent verification?

---

# Part F — Governance

## 27. Why is a model-generated destination name only a proposal?

## 28. Explain:

```text
discovery != authorization
```

for both MCP and A2A.

## 29. Why must delegation not become a privilege-escalation path?

## 30. A low-privilege manager cannot delete production data, but it can call an "Admin Agent" that can. What policy problem exists?

## 31. Why does Agent identity not replace the authenticated end-user/application Principal?

## 32. Why should remote Agent output be treated as untrusted external content?

---

# Part G — A2A 1.0

## 33. What problem does A2A solve that MCP does not primarily solve?

## 34. Explain the roles of:

```text
A2A Client
A2A Server / Remote Agent
```

## 35. What is an Agent Card?

## 36. Why is an Agent Skill not necessarily the same thing as one internal Tool?

## 37. Explain the difference between:

```text
Message
Artifact
```

## 38. What is a `Part`?

## 39. Why does A2A have a stateful Task concept instead of treating every Agent interaction as one synchronous function call?

## 40. Give examples of interrupted/terminal Task states and explain why they matter.

## 41. What important Agent Card shape changed in A2A 1.0 compared with older 0.3-era examples?

## 42. Why should Tiny-Agent version-pin the A2A teaching target in its documentation?

---

# Part H — MCP vs A2A

## 43. Complete the table yourself:

| Question | MCP | A2A |
|---|---|---|
| Main communication boundary | ? | ? |
| Main discovery unit | ? | ? |
| Remote implementation opaque? | ? | ? |
| Long-running Task lifecycle core? | ? | ? |
| Typical example | ? | ? |

## 44. Draw a system where:

```text
Your Agent --A2A--> Remote Research Agent --MCP--> Search Server
```

Explain why the two protocols can coexist.

---

# Part I — OpenAI Agents SDK mapping

## 45. What does `Agent.as_tool()` represent architecturally?

## 46. How is an SDK handoff different from `Agent.as_tool()`?

## 47. Why can handoff input filtering matter?

## 48. When would code orchestration be better than letting an LLM choose the next Agent?

## 49. Build two offline Agent objects:

- a refund specialist exposed as a Tool;
- the same specialist exposed as a handoff destination.

Do not make a live model call.

---

# Part J — Coding exercises

## 50. Add a `max_failed_agent_calls` coordination budget.

Requirements:

- failure count is run-scoped;
- once exhausted, no new Agent work launches;
- add deterministic tests.

## 51. Add a `ContextPolicy` option that disables private context for selected Agents.

Do not change the default behavior globally.

## 52. Add a structured delegation contract.

Example:

```python
@dataclass(frozen=True)
class DelegationTask:
    goal: str
    constraints: tuple[str, ...]
    expected_output: str
```

Explain why this can preserve constraints better than a free-form string.

## 53. Add a worker timeout without duplicating Stage 09 retry policy.

Think carefully about where the timeout should live.

## 54. Add a fan-out failure mode that returns partial results plus explicit failure records.

## 55. Add an evaluator for expected final active Agent after a handoff scenario.

## 56. Add an evaluator for forbidden Agent edges.

## 57. Add trace spans around `delegate()` and `handoff()` using the Stage 10 tracer protocol.

Do not capture raw delegation task text by default.

---

# Part K — Architecture exercises

## 58. Customer support

Design three alternatives for:

```text
FAQ
billing
refund
account security
```

Compare:

1. one Agent with all Tools;
2. manager + specialists;
3. triage + handoffs.

Discuss context, authority, latency, and failure modes.

## 59. Research report

The task requires:

```text
retrieval
statistical analysis
legal review
writing
```

Which steps should be deterministic workflow nodes, which could be specialist Agents, and which can run in parallel?

There is no requirement that every noun becomes an Agent.

## 60. Production change request

A developer asks an Agent team to deploy a release.

Design:

- manager;
- code-review specialist;
- deployment specialist;
- human approval;
- permission boundary;
- rollback path.

Explain why delegation must not grant more production authority than the authenticated caller is allowed to use.

---

# Part L — Evaluation exercises

## 61. Compare these systems:

```text
Single Agent
quality = .87
latency = 700 ms
cost = $0.012

Multi-Agent
quality = .90
latency = 1600 ms
cost = $0.031
```

Is multi-Agent better?

Explain what additional product context is needed.

## 62. Propose metrics for a handoff system.

Include at least:

- route/handoff accuracy;
- failed handoffs;
- repeated handoffs;
- user-visible resolution quality;
- cost/latency.

## 63. Why should multi-Agent evaluation use the same test cases as the single-Agent baseline when possible?

## 64. How would you detect constraint loss between manager delegation and worker execution?

## 65. A team improves final-answer correctness but occasionally uses a forbidden Agent edge. Should a weighted quality average be allowed to compensate for that? Explain.

---

# Part M — Interview questions

## 66. "What is a multi-Agent system?"

Give an answer that distinguishes it from multiple LLM calls.

## 67. "When would you not use multi-Agent?"

## 68. "Supervisor vs handoff?"

## 69. "How do you avoid Agent loops?"

## 70. "How do you handle context sharing among Agents?"

## 71. "How do you secure Agent-to-Agent delegation?"

## 72. "What is A2A, and how is it different from MCP?"

## 73. "How would you prove a multi-Agent architecture is worth the added complexity?"

A strong answer should mention a measured baseline, not architecture aesthetics.

---

# Final self-check

Before you say you understand Stage 11, make sure you can explain these without notes:

```text
workflow vs multi-Agent
delegation vs handoff
manager vs active specialist
context projection
fan-out vs fan-in
coordination budget
handoff loop
Agent authority boundary
A2A Agent Card / Message / Task / Part / Artifact
A2A vs MCP
OpenAI Agent.as_tool vs handoff
multi-Agent vs single-Agent evaluation
```

If you can explain all of those clearly, you are no longer just learning how to create more Agent objects. You are learning how to design **coordination boundaries**.

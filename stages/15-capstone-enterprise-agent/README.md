# Stage 15: Capstone — Build a Support Agent That Can Cite Policy, Inspect Orders, and Request Refunds

> Language: **English** | [简体中文](README.zh-CN.md)

We finally reached the last stage.

A common capstone mistake is to turn graduation into a technology parade:

```text
LangGraph
+ RAG
+ MCP
+ Memory
+ Skills
+ Multi-Agent
+ Sandbox
+ Long-Horizon
+ one vector database
+ a diagram with twenty-seven boxes
```

Everything appears to be present.

That is not the engineering lesson of this course.

From Stage 00 onward, the recurring principle has been:

> **Start from the problem, then give the model only the decisions, information, and execution authority that the problem actually needs.**

So the capstone is deliberately specific.

We build a **Support Agent** that can answer refund-policy questions, inspect an authenticated user's own orders, and propose a refund when policy permits it. A real refund changes financial state, so execution must pause for human approval.

This modest scenario is enough to connect the mechanisms from the previous fourteen stages.

More importantly, it lets us practice subtraction.

---

## 1. Start with the business path, not the architecture diagram

A user may ask:

> “Can ORDER-42 be refunded to the original payment method?”

Or:

> “Please refund ORDER-42.”

The system needs authoritative order facts and policy evidence.

If evidence is sufficient, it may explain the rule.

If the user truly requests a refund, the model may propose that action.

It still cannot move money by itself.

The main path is:

```text
user question
    ↓
model makes semantic decision
    ↓
need an order?
    ↓
load only an authorized order
    ↓
need policy?
    ↓
retrieve evidence
    ↓
evidence sufficient?
    ├── no  -> abstain
    └── yes
          ↓
        information only?
          ├── yes -> grounded answer
          └── no  -> structured refund proposal
                          ↓
                    waiting approval
                          ↓
                  approve / edit / reject
                          ↓
                    bounded side effect
```

Nothing in this path naturally requires five Agents or arbitrary shell access.

No reason, no capability.

The first capstone rule is therefore:

> **Architecture should grow from domain constraints, not from the course table of contents.**

---

## 2. Which earlier mechanisms are actually used?

The Support Agent uses Structured Decisions, a Tool-like order boundary, application-owned control flow, RAG evidence, durable Runs, HITL approval, identity scoping, idempotency, small traces, and deterministic evaluation.

It deliberately does **not** use Multi-Agent coordination, arbitrary Skill scripts, shell execution, or long-horizon leases.

Those mechanisms are useful when their problems exist.

If fraud review becomes an independent Agent owned by another team, delegation or A2A may become justified.

If the Agent edits repositories, workspace and sandbox controls matter.

If one support case spans days and workers, a long-horizon harness matters.

The capstone does not pre-install future complexity.

---

## 3. The model still decides; it does not execute

We define:

```python
@dataclass(frozen=True, slots=True)
class SupportDecision:
    kind: DecisionKind
    order_id: str | None = None
```

and a provider-neutral boundary:

```python
class DecisionModel(Protocol):
    def decide(
        self,
        question: str,
    ) -> SupportDecision:
        ...
```

The offline course implementation uses `DeterministicDecisionModel` as a **Model Double**. It produces stable decisions without network access or API keys.

A production adapter can replace it with a real LLM using Structured Output.

The authority boundary remains unchanged:

```text
DecisionModel
    -> proposes semantic decision

Application
    -> loads order
    -> retrieves policy
    -> validates business rules
    -> creates approval request
    -> executes side effect
```

Returning `"refund_action"` does not grant refund authority.

---

## 4. Why keep a Model Double in a capstone?

Because it separates model quality from runtime correctness.

If a real LLM misclassifies “tell me the refund policy” as `refund_action`, that is a decision-quality problem.

If the application responds to that decision by bypassing order checks, evidence, and approval, that is an authority problem.

Those should not collapse into one explanation called “models are probabilistic.”

With a model interface, we can evaluate decision accuracy separately from runtime safety invariants.

That is a much better debugging boundary.

---

## 5. Order access is scoped by trusted identity

The domain contains:

```python
Order(
    order_id="ORDER-42",
    tenant_id="acme",
    user_id="alice",
    amount="49.00",
    age_days=12,
    status="paid",
)
```

and the service receives:

```python
TrustedIdentity(
    tenant_id="acme",
    user_id="alice",
)
```

The Agent does not reveal an order merely because the caller knows its ID.

Tenant and user ownership must match.

An unauthorized caller receives:

```text
I cannot find an accessible order with that ID.
```

The system does not volunteer who owns the order.

This carries Stage 13's service identity boundary into domain logic.

---

## 6. User intent does not overwrite authoritative order facts

Suppose the user says:

> “Please refund ORDER-42 for 9999.”

The requested number is untrusted input.

The refund proposal uses:

```python
order.amount
```

from the authoritative order record.

The resulting approval request still says:

```text
49.00
```

A useful principle is:

> **Low-trust input may express intent. High-impact facts should be reloaded from authoritative sources.**

Writing a number in a prompt does not rewrite payment history.

---

## 7. Policy answers require evidence

The teaching corpus contains stable policy documents such as:

```text
refund-within-30-days
refund-after-30-days
standard-shipping
```

The retriever returns:

```python
Evidence(
    id="refund-within-30-days",
    text="...",
    score=...
)
```

A grounded answer includes the evidence ID:

```text
ORDER-42 is 12 days old.
Paid orders within 30 days may be refunded...
Evidence: [refund-within-30-days]
```

That small citation creates provenance between a claim and the policy record used to support it.

---

## 8. Missing evidence produces abstention

Ask:

> “What is the lunar teleportation warranty?”

The corpus has no supporting material.

The system takes an explicit `answer:abstain` branch and returns:

```text
I do not have enough policy evidence to answer reliably.
```

This is not merely a cautious tone.

> **Abstention is a runtime behavior.**

The system does not ask the generator to invent a plausible policy.

---

## 9. The first retrieval result is not automatically sufficient

Stage 04 already established that retrieval score is a ranking signal, not a truth score.

The refund runtime goes further. Once it has an authoritative `age_days`, ordinary code selects the applicable policy branch:

```text
<= 30 days -> refund-within-30-days
> 30 days  -> refund-after-30-days
```

A deterministic business fact does not need another model guess.

That is Stage 02's lesson still operating in the final system.

---

## 10. A twelve-day order and a forty-five-day order take different paths

`ORDER-42` is twelve days old and may enter the original-payment refund flow.

`ORDER-99` is forty-five days old. The policy says original-payment refund is unavailable and support may offer store credit after review.

Even if the user says “Please refund ORDER-99,” the runtime does not generate an original-payment refund approval.

Approval is not a mechanism for overriding an ineligible business action.

---

## 11. Approval binds exact action parameters

An eligible refund creates:

```python
ApprovalRequest(
    run_id=...,
    order_id="ORDER-42",
    amount="49.00",
    reason="Refund changes external financial state.",
)
```

The reviewer is not approving “let this Agent handle refunds.”

The reviewer is approving one run, one order, and one amount.

Specific approval boundaries are easier to reason about and audit.

---

## 12. Edited approvals remain bounded

A reviewer may lower `49.00` to `40.00`.

The reviewer may not edit the refund upward to `500.00`.

The runtime revalidates the final amount:

```python
if edited_value > proposed_value:
    raise ValueError(
        "edited amount cannot exceed the proposed refund"
    )
```

Human input is still input. HITL does not disable validation.

---

## 13. Reject means no side effect

A rejected approval changes the Run to `rejected`.

The teaching checks also assert that the effect count remains zero.

This is an important class of Agent test:

> **When an action must not occur, verify that it truly did not occur.**

---

## 14. Approved effects are idempotent within the teaching store

The refund effect is keyed by:

```text
{run_id}:refund
```

Once the Run is completed, a repeated resume does not execute another refund.

The effect count remains one.

This only proves idempotency inside the teaching store. A real payment provider needs its own idempotency contract.

The architecture still refuses the simplest failure mode: “every Approve message triggers another refund.”

---

## 15. Durable Runs remain identity-scoped

Reading a Run requires:

```python
get_run(
    run_id,
    tenant_id=identity.tenant_id,
    user_id=identity.user_id,
)
```

A Run created by Alice cannot be resumed by Bob using the same `run_id`.

Identity should remain visible near side-effect boundaries, not only at the outer HTTP layer.

---

## 16. A small trace already explains the trajectory

A refund request records:

```text
model:decision:refund_action
tool:lookup_order
retrieval:refund_policy
proposal:refund
approval:waiting
```

Resume records:

```text
resume:refund
approval:approved
effect:refund_completed
```

This is not a distributed tracing platform.

It is enough to answer a crucial debugging question:

> “Why did this run reach this state?”

Observability begins with explicit responsibility boundaries.

---

## 17. Context Engineering becomes a habit rather than a required class import

The capstone does not copy Stage 07's entire `ContextBuilder`.

The decision model needs the current question. Order facts and policy evidence are loaded just in time by the application.

If a real LLM generates the final grounded prose, its context should contain the current question, authorized order facts, selected policy evidence, and answer instructions—not every memory, historical Run, policy document, and order.

By the capstone, Context Engineering should influence design even when no class named `ContextBuilder` appears.

---

## 18. Why MCP is not forced into the local demo

In production, order lookup may be a remote Tool or service, and the policy corpus may be remote retrieval or an MCP Resource.

That does not require the teaching capstone to start a protocol server merely to call two local data structures through the network.

Learning a protocol means knowing where its adapter belongs when a real system boundary appears.

It does not mean wrapping every local function in the protocol forever.

---

## 19. Why there is no Multi-Agent team

We could draw Supervisor, Order, Policy, Refund, and Approval Agents.

The current domain does not justify five independent task owners.

Order lookup is a capability.

Policy retrieval is a retriever.

Refund approval is a HITL workflow.

Promoting every component into an Agent would add coordination without demonstrating a measurable benefit.

If fraud review later becomes an independent system with separate models, data, permissions, and task lifecycle, delegation or A2A becomes much more defensible.

---

## 20. Why there is no shell or sandbox

The support domain does not need to run user code or edit repositories.

Therefore it exposes no shell.

No shell is an excellent shell security policy.

Least privilege often means not providing a capability at all rather than exposing it and asking the model nicely not to misuse it.

---

## 21. Why the core flow does not use a long-horizon harness

The support path is short:

```text
decision
order lookup
policy retrieval
approval
refund
```

Human review may take time, but Stage 06 durable Run semantics are sufficient for that wait.

There are no multi-hour work units requiring lease reclaim.

If future cases span days, gather many external artifacts, and move between workers, Stage 14 becomes appropriate.

Use complexity when the domain earns it.

---

## 22. Run the capstone

```bash
python stages/15-capstone-enterprise-agent/code/demo.py
```

The first request asks whether `ORDER-42` can be refunded. The runtime makes a decision, loads the authorized order, retrieves policy, and returns a grounded answer.

The second request asks to refund it. The Run enters `waiting_approval`, and only an approved resume records the refund effect.

---

## 23. Run the capstone checks

```bash
python stages/15-capstone-enterprise-agent/code/checks.py
```

The checks verify nine invariants:

Policy answers carry evidence IDs.

Unknown policy questions abstain.

Order reads are identity-scoped.

Refund amount comes from the order, not an arbitrary number in user text.

Late orders do not create an original-payment refund approval.

Rejected approval creates no refund effect.

Edited approval cannot increase the proposed refund.

Repeated resume does not duplicate the effect.

One identity cannot read another identity's durable Run.

Those invariants say much more than “the demo looked good.”

---

## 24. Where a real LLM belongs

A production model adapter naturally implements:

```python
class DecisionModel(Protocol):
    def decide(
        self,
        question: str,
    ) -> SupportDecision:
        ...
```

It can use Structured Output to return a constrained decision such as:

```json
{
  "kind": "refund_action",
  "order_id": "ORDER-42"
}
```

Everything after that remains application-owned.

Do not let the provider adapter quietly become the database client, policy engine, approver, and payment executor.

Provider-specific wire format should stay behind a narrow adapter.

---

## 25. What a production deployment still needs

The teaching capstone is not a bank-ready deployment.

A real system will need real authentication, external order and payment services, provider-level idempotency, database migrations, secret management, service tracing, a real model adapter, rate limits, policy-corpus lifecycle, online evaluation, stronger authorization, audit retention, and domain-specific compliance.

The important difference after this course is that those requirements have places to go.

They do not require turning the architecture back into one large `agent.py`.

---

## 26. Walk from Stage 00 one more time

Stage 00 gave model output a contract and introduced Tool proposals.

Stage 01 turned Tool proposals into a bounded Agent Runtime.

Stage 02 asked which decisions should remain deterministic.

Stage 03 made complex execution state explicit.

Stage 04 gave the Agent external evidence.

Stage 05 standardized external capability boundaries with MCP.

Stage 06 made execution and selected memory durable and introduced HITL.

Stage 07 separated retained information from current model context.

Stage 08 packaged reusable procedures as progressively disclosed Skills.

Stage 09 added permissions, validation, retries, budgets, and deadlines.

Stage 10 made quality observable and evaluable.

Stage 11 asked when multiple Agents are actually justified.

Stage 12 gave file and code work an explicit workspace and sandbox boundary.

Stage 13 turned the program into a service with identity, queues, backpressure, and durable Runs.

Stage 14 let long tasks survive worker loss through ledgers, leases, and artifacts.

Stage 15 looks simpler because it selects only the mechanisms the support domain needs.

That is the difference between using an Agent framework and engineering an Agent system.

---

## 27. The final architecture

```text
                   Trusted Identity
                          │
                          v
User Question --> DecisionModel
                          │
                          v
                    SupportAgent
                   /      |       \
                  /       |        \
                 v        v         v
          Order Lookup  Policy    Greeting
               │       Retriever
               │          │
               └────┬─────┘
                    v
               Evidence Check
                    │
          ┌─────────┴─────────┐
          │                   │
     grounded answer      refund proposal
                              │
                              v
                        Durable Run
                              │
                              v
                       Human Approval
                              │
                    ┌─────────┴─────────┐
                    │                   │
                 reject          validated approve/edit
                                        │
                                        v
                              Idempotent Refund Effect
```

It is not a flashy diagram.

That is fine.

A good architecture diagram should make five things clear: who decides, who owns the data, who owns authority, where side effects occur, and how the system recovers from failure.

If those questions have precise answers, an Agent has started to become an engineered system.

---

## 28. What to keep learning after graduation

Models will change. Frameworks will change. Protocols will change. Product names certainly will.

The more durable habits are these:

When you see model output, ask about the contract.

When you see an autonomous loop, ask about stopping conditions.

When you see a Tool, ask who owns execution authority.

When you see RAG, ask for evidence.

When you see memory, ask about retention policy.

When you see context, ask what this turn actually needs.

When you see a Skill, separate procedure from authority.

When you see a retry, ask whether the side effect is idempotent.

When you see Multi-Agent, ask why one Agent is insufficient.

When you see a sandbox, ask what it truly isolates.

When you see production service code, ask about identity, scope, and durable state.

When you see a long-horizon task, ask whether it survives worker loss.

And when you see a beautiful Agent demo, ask one final question:

> **If the model name and framework logos were hidden, would the system's responsibility boundaries still be clear?**

If yes, you understand the system.

If not, return to the smallest mechanism and rebuild the reasoning one layer at a time.

That is the end of the Tiny-Agent course path.

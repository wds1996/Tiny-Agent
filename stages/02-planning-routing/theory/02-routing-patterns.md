# Routing Patterns: Put One Semantic Decision in Front of Explicit Code

Routing is one of the most useful patterns between a fixed workflow and a fully autonomous Agent.

A Router answers one narrow question:

> **Which predefined path should handle this request?**

It should not silently become an unconstrained Agent that invents arbitrary destinations and executes them.

---

## 1. The basic pattern

```text
                         +--> Route A -> handler A
Request -> Router -------+--> Route B -> handler B
                         +--> Route C -> handler C
```

There are two responsibilities:

### Router

Chooses one route.

### Application dispatcher

Maps that route to an allowed handler.

Tiny-Agent keeps these separate:

```python
decision = router.route(request)
handler = handlers[decision.route]
output = handler(request)
```

The LLM can help with semantic classification, but Python still owns the allowlist and dispatch.

---

## 2. Why routing is valuable

Without routing, one large prompt may need to handle every case:

```text
billing
refunds
technical errors
account recovery
general questions
enterprise sales
...
```

That creates competing instructions and an unnecessarily large action space.

Routing narrows the problem:

```text
request
   |
   v
router
   |
   +--> billing specialist
   +--> technical specialist
   +--> general specialist
```

Each downstream component can then have:

- a smaller prompt;
- fewer tools;
- narrower permissions;
- simpler evaluation criteria.

This is both an accuracy and a governance benefit.

---

## 3. First choice: deterministic routing

If a route can be identified reliably by code, use code.

Example:

```python
if event.type == "payment_failed":
    return "billing"

if error_code in KNOWN_TECHNICAL_CODES:
    return "technical"
```

This is better than asking a model to rediscover an explicit field already present in the request.

### Good deterministic signals

- API event type;
- HTTP status;
- database enum;
- authenticated user tier;
- product SKU;
- known command prefix;
- exact form selection;
- regulated business rule.

### Bad reason to use an LLM

```text
"We already know the event_type is REFUND, but let's ask the LLM whether it looks like a refund."
```

That adds cost and uncertainty without adding information.

---

## 4. When an LLM router is useful

Use an LLM when the route depends on meaning expressed in unstructured language.

Examples:

```text
"I was charged twice and I can't figure out why."
```

Likely route:

```text
billing
```

```text
"The desktop client closes immediately after I sign in."
```

Likely route:

```text
technical
```

No simple stable keyword is guaranteed to capture every paraphrase.

The LLM performs semantic classification.

---

## 5. Do not parse free-form routing prose

Weak design:

```text
LLM output:
"This seems mostly like a technical issue, although billing could also be relevant."
```

Then application code tries to parse the prose.

Better design:

```json
{
  "route": "technical",
  "reason": "The user describes a client crash after authentication."
}
```

with a schema such as:

```json
{
  "type": "object",
  "properties": {
    "route": {
      "type": "string",
      "enum": ["billing", "technical", "general"]
    },
    "reason": {
      "type": "string"
    }
  },
  "required": ["route", "reason"],
  "additionalProperties": false
}
```

Now control flow is data, not prose parsing.

---

## 6. Why the enum matters

The model must not be allowed to return:

```text
route = "run_shell_as_admin"
```

if the application only supports:

```text
billing
technical
general
```

The allowed route set is application policy.

This gives us:

```text
Model semantic judgment
          |
          v
allowed enum value
          |
          v
application-owned dispatch
```

not:

```text
model-generated string
          |
          v
arbitrary dynamic execution
```

---

## 7. Route descriptions are part of the interface

A route name alone may not be enough.

Weak:

```text
route_a
route_b
route_c
```

Better:

```text
billing: refunds, invoices, duplicate charges, payment failures
technical: bugs, crashes, error messages, product malfunction
general: ordinary product information and questions
```

A Router prompt should clearly communicate category boundaries.

This is similar to Tool Description design from Stage 00/01:

> The model can only choose reliably among interfaces it can understand reliably.

---

## 8. Route overlap is a data-design problem

Suppose you define:

```text
account: any account-related question
billing: subscription and payment questions
```

Then:

```text
"How do I update the card attached to my account?"
```

fits both.

You can improve routing by:

- making categories mutually exclusive where possible;
- defining precedence;
- adding examples;
- splitting downstream responsibility more clearly;
- adding an `uncertain` / `human_review` route when ambiguity is meaningful.

Do not assume a more powerful model automatically fixes an incoherent taxonomy.

---

## 9. Hybrid routing is often better

A strong production pattern is:

```text
Request
   |
   v
Deterministic checks
   |
   +-- certain match --> handler
   |
   +-- ambiguous ------> LLM router
                            |
                            v
                          handler
```

Example:

```python
if request.event_type == "refund_requested":
    return "billing"

if request.error_code in CRASH_CODES:
    return "technical"

return llm_router.route(request.message)
```

This preserves cheap reliable paths while using model intelligence only where it adds value.

---

## 10. Hierarchical routing

Large systems should not necessarily expose 80 routes in one prompt.

Instead:

```text
                  top-level router
                 /       |        \
                /        |         \
            support    sales      ops
              |
         support router
         /     |      \
    billing technical account
```

Benefits:

- smaller decision sets;
- clearer route boundaries;
- reduced context;
- easier permission partitioning.

Cost:

- extra routing turn(s);
- possibility of an early wrong branch.

Measure whether the hierarchy helps.

---

## 11. Model routing is different from model selection

The word "routing" is used for at least two related problems.

### Task routing

```text
request -> billing / technical / general workflow
```

### Model routing

```text
easy request -> cheap model
hard request -> strong model
```

Both are architecture patterns, but their decisions differ.

Model routing may consider:

- task complexity;
- latency target;
- cost budget;
- modalities;
- tool support;
- context size.

Do not mix task categories with model tiers unless that coupling is intentional.

---

## 12. Do not trust self-reported confidence as probability

A tempting route schema is:

```json
{
  "route": "billing",
  "confidence": 0.97
}
```

This number looks scientific, but a language model's generated `0.97` should not automatically be treated as a calibrated probability of correctness.

If routing confidence matters, calibrate it empirically using a labeled dataset.

Possible approaches include:

- route-specific evaluation metrics;
- confusion matrix;
- thresholds derived from actual held-out performance;
- deterministic uncertainty rules;
- multiple-model voting in specific high-value cases;
- human review for risky ambiguous cases.

A model saying "0.97" is not itself an evaluation system.

---

## 13. Fail closed for consequential routing

Suppose route A permits read-only actions and route B permits refunds.

Do not design:

```text
unknown route -> most powerful handler
```

Better:

```text
unknown / invalid / unsupported route
             |
             v
safe fallback / human review / reject
```

The Router is part of the control plane and should fail predictably.

Tiny-Agent's `LLMRouter` validates that the returned route exists in its configured route map even after provider-side schema constraints.

Defense at more than one layer is useful.

---

## 14. Routing and permissions

Routing can reduce the tool surface available to downstream Agents.

Instead of one giant Agent:

```text
Agent tools:
- refund
- send email
- reset password
- query logs
- modify infrastructure
- sales CRM
- ...
```

use:

```text
Router
  |
  +-> billing Agent
  |     tools: invoice lookup, refund request
  |
  +-> technical Agent
  |     tools: logs, diagnostics
  |
  +-> sales Agent
        tools: CRM lookup
```

This is easier to govern and easier for the model to reason about.

---

## 15. Routing evaluation

A Router is a classifier. Evaluate it like one.

Create examples:

```text
input                                      expected route
-----                                      --------------
"charged twice"                            billing
"app crashes after login"                  technical
"what languages are supported?"            general
```

Then measure:

- overall accuracy;
- per-route precision/recall;
- confusion pairs;
- high-impact errors;
- fallback rate;
- latency;
- token cost.

If "billing -> general" is harmless but "general -> refund-capable flow" is risky, weight errors differently.

We will build a formal evaluation layer in Stage 08, but Stage 02 should already teach what data needs to exist.

---

## 16. Routing workflow vs ReAct Agent

### Routing workflow

```text
one route decision
      |
      v
fixed downstream process
```

### ReAct Agent

```text
model repeatedly decides next action
      |
      v
observation
      |
      v
model decides again
```

Routing is appropriate when most uncertainty exists at the **entrance** of a process.

ReAct is appropriate when uncertainty continues throughout execution.

---

## 17. Tiny-Agent implementation

Stage 02 adds:

```python
@dataclass
class RouteDecision:
    route: str
    reason: str
```

and two routers.

### RuleRouter

```python
RuleRouter(
    rules=[
        ("billing", is_billing),
        ("technical", is_technical),
    ],
    fallback="general",
)
```

### LLMRouter

```python
LLMRouter(
    model=structured_model,
    routes={
        "billing": "Refund and payment problems.",
        "technical": "Bugs and failures.",
        "general": "General questions.",
    },
)
```

Both satisfy the same conceptual interface:

```python
router.route(request) -> RouteDecision
```

This makes it possible to change routing strategy without changing downstream workflow code.

---

## 18. Interview-ready answer

A concise answer to:

> How would you design an LLM Router?

is:

> I would first check whether stable deterministic rules can handle high-confidence cases. For semantic ambiguity, I would use a schema-constrained LLM output whose route field is limited to an application-owned allowlist. The model chooses the route, but application code performs dispatch. I would evaluate routing on a labeled dataset, inspect confusion between categories, and use a safe fallback for invalid or high-risk ambiguous cases rather than treating model-generated confidence as calibrated probability.

---

## 19. Check your understanding

1. Why is a Router narrower than an Agent?
2. Why should downstream dispatch remain application code?
3. When is a rule router superior to an LLM router?
4. Why should route values be schema-constrained?
5. What is wrong with dynamically executing any model-generated route name?
6. Why can overlapping route definitions hurt even a strong model?
7. Why is generated confidence not automatically calibrated?
8. How can routing reduce the tool/permission surface of downstream Agents?

If you can answer these, proceed to planning.

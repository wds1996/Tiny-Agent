# 04 — Model Capabilities, Reasoning, and Model Selection

An Agent architecture should never begin with the assumption that **"an LLM is an LLM."** Models differ in capability, latency, cost, context limits, tool support, multimodality, and reliability on structured control decisions.

The important engineering question is not:

> Which model is the smartest?

It is:

> Which model/configuration satisfies this task's quality target under the application's latency, cost, safety, and capability constraints?

A Formula 1 car is excellent engineering. It is still a suspicious choice for delivering groceries through a school zone.

---

## 1. Model capability is a contract surface

A provider may expose models that differ in:

- reasoning quality and configurable reasoning effort;
- context-window and output limits;
- latency and throughput;
- input/output price;
- Function Calling reliability;
- Structured Output / schema support;
- image, audio, or video input/output;
- built-in web, file, code, or computer capabilities;
- fine-tuning, distillation, caching, or batch options.

Do not reduce model selection to a single leaderboard score. An Agent repeatedly asks models to do **different jobs**.

```text
router           -> short classification / enum decision
planner          -> multi-step semantic decomposition
writer           -> long grounded synthesis
embedding model  -> text -> vector
vision model     -> screenshot/image understanding
```

The best model for one role may be wasteful or incapable in another.

---

## 2. Model capability != runtime capability

This distinction prevents many architectural mistakes.

```text
model capability
    = what the inference API can represent, understand, or propose

runtime capability
    = what the application actually exposes, authorizes, and executes
```

Examples:

```text
model supports Function Calling
!= model can access your database

model supports computer use
!= model may click the production console

model supports 1M context
!= application should send 1M tokens
```

The model is the reasoning component. The runtime owns credentials, Tool registration, authorization, budgets, sandbox boundaries, and side effects.

If the model says "I can delete the database," that is a proposal. It is not a promotion to DBA.

---

## 3. Reasoning effort is a budget, not a magical intelligence slider

Reasoning-oriented APIs may expose a control that trades more inference work for potentially better results.

Use higher effort when the task benefits from it:

- difficult planning;
- ambiguous multi-constraint decisions;
- non-trivial code or mathematical reasoning;
- complex evidence synthesis.

Do not automatically maximize it for:

- deterministic routing;
- trivial extraction;
- schema conversion;
- simple Tool selection;
- decisions that code can make exactly.

The correct loop is empirical:

```text
candidate model/configuration
        ↓
evaluation dataset
        ↓
quality + latency + cost + failure profile
        ↓
smallest configuration meeting the product target
```

"More reasoning" without an evaluation set is just a more expensive superstition.

---

## 4. Build a capability matrix before a router

A simple application-owned matrix is often enough:

| Role | Required capability | Priority |
| --- | --- | --- |
| ticket router | structured enum output | latency/cost |
| research planner | strong reasoning + structured plan | quality |
| report writer | long grounded generation | quality/context |
| image inspector | vision input | capability |

Conceptually, selection can stay deterministic:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ModelProfile:
    name: str
    supports_structured: bool
    supports_vision: bool
    tier: str


def choose_model(task: str, profiles: list[ModelProfile]) -> ModelProfile:
    if task == "vision":
        return next(p for p in profiles if p.supports_vision)
    if task in {"route", "extract"}:
        return next(p for p in profiles if p.tier == "fast" and p.supports_structured)
    return next(p for p in profiles if p.tier == "reasoning")
```

The important idea is not this toy policy. It is that **model selection itself is application policy**.

---

## 5. Dynamic model routing: useful, but bounded

Sometimes task complexity is semantic, so an LLM/router can help classify it.

Safe shape:

```text
request
  -> bounded complexity classifier
  -> enum: FAST | REASONING | VISION
  -> application maps enum to approved model
```

Bad shape:

```python
# user/model text becomes an arbitrary provider model id
model = provider.create(user_supplied_model_name)
```

A semantic router may choose among **approved classes**. It should not silently become a configuration-injection interface.

---

## 6. Capability detection should fail clearly

Suppose an application requires strict structured output but the selected provider/model path does not support the needed schema behavior.

Bad behavior:

```text
try anyway
-> receive prose
-> regex it
-> hope Tuesday is a lucky day
```

Better behavior:

```text
required capability unavailable
-> reject configuration / choose approved fallback
-> record why fallback occurred
```

Provider adapters exist partly to keep these fast-changing capability details outside the core Agent runtime.

---

## 7. Model upgrades are software changes

A model version change can alter:

- Tool-call frequency;
- plan length;
- formatting behavior;
- refusal/abstention rate;
- latency;
- token usage;
- how often a critic requests revision.

Therefore model upgrades deserve regression evaluation just like library upgrades.

A useful evaluation table:

```text
                    old config    candidate
route accuracy         96%          97%
research success       82%          88%
p95 latency           1.2s         2.1s
mean tokens            900         1450
cost / successful run  $X          $Y
```

The candidate is not automatically better because one quality number increased.

---

## 8. Worked example: one Agent, three model roles

Imagine a research Agent:

```text
user question
   ↓
fast router: "needs research?"
   ↓ yes
reasoning planner: subquestions + evidence plan
   ↓
retrieval / tools
   ↓
writer model: grounded synthesis
```

Why not use the strongest model three times?

Because the first decision may be easy and high-volume. Spending maximum reasoning on `needs_research=true` is like hiring a Supreme Court justice to check a cinema ticket.

Why not use the cheapest model everywhere?

Because the planner may be the step where semantic quality determines the entire downstream trajectory.

Model routing is therefore a systems optimization problem, not a brand preference.

---

## 9. Interview-ready distinction

A strong answer to "How do you select models in an Agent system?" is:

> I separate model capabilities from runtime permissions, define the capability and quality requirements of each Agent role, restrict routing to an approved model set, and evaluate candidate configurations on task success, latency, cost, and failure behavior. I use stronger reasoning only where it measurably improves the task rather than making every step maximally expensive.

---

## 10. Provider details are versioned

Model names, parameters, and response shapes change faster than the architectural ideas in this repository.

Tiny-Agent therefore isolates provider behavior behind adapters.

Remember the invariant:

> **Choose model capability through explicit application policy, verify it through evaluation, and never confuse what a model can propose with what the runtime allows it to do.**

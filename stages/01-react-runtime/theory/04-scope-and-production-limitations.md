# 04 — Where Does This Runtime Still Break? From Correct Boundaries to Production Thinking

> Language: English | [简体中文](04-scope-and-production-limitations.zh-CN.md)

At this point we have a clean minimal Runtime:

```text
Model proposes ToolCall
    ↓
Adapter normalizes
    ↓
Runtime owns the loop
    ↓
ToolRegistry executes
    ↓
Observation returns to the next turn
```

Those boundaries are sound.

But sound boundaries are not the same thing as production readiness.

A weak tutorial often runs a ten-line demo and immediately says “you built an Agent.” A more useful statement is:

> **We built an Agent Runtime that makes the core control model explicit. It still lacks many production constraints.**

This chapter studies those missing pieces through concrete failure scenarios.

---

## 1. Failure: the model never stops

An endless model can keep requesting the same Tool:

```text
get_mock_weather(Tokyo)
-> get_mock_weather(Tokyo)
-> get_mock_weather(Tokyo)
-> ...
```

Stage 01 already solves one part of this problem with:

```python
max_steps
```

`tests/test_runtime_edges.py` verifies that an `EndlessToolModel` is forcibly stopped.

But `max_steps` answers only:

```text
How many model turns may occur?
```

It does not answer how long one Tool may run, how many ToolCalls may exist in one step, how much money may be spent, or how cancellation works.

Those are separate budgets and control mechanisms.

---

## 2. Failure: model-generated arguments are wrong

A model may propose:

```text
celsius_to_fahrenheit(temperature_c="eighteen")
```

Provider-side strict schemas are useful, but an application should not conclude:

```text
provider says it is valid
=
Runtime never needs validation
```

Future calls may come from another provider, an old checkpoint, MCP, a manually constructed test fixture, or a drifting schema.

Production Runtimes therefore need application-side argument validation too.

Stage 01 intentionally leaves full JSON-Schema validation out of the smallest loop so the control model remains visible. That is a teaching deferment, not a claim that validation is unnecessary.

---

## 3. Failure: Tool exceptions leak internals

A common teaching shortcut is:

```python
except Exception as exc:
    observation = str(exc)
```

It makes recovery easy to demonstrate, but raw exceptions may contain file paths, internal database names, service URLs, SQL details, or sensitive values.

Production systems need two different views:

```text
safe model-facing observation
        !=
detailed developer diagnostic
```

The evolving `src/tiny_agent/runtime.py` has already been hardened by later reliability work so unexpected exceptions become redacted Tool-failure observations. Stage 01 teaches that recoverable failures can participate in the loop; Stage 07 teaches classification and policy.

---

## 4. Failure: the model proposes a capability it should not be allowed to execute

Imagine a Registry containing:

```text
read_weather
send_email
refund_payment
delete_database
```

The minimal Stage 01 Runtime executes any registered Tool the model proposes.

Real systems must separate:

```text
visible to the model
!=
authorized for this caller
!=
permitted under current policy
!=
approved for this exact action
```

A read-only weather Tool may be automatic. Sending email may be policy-dependent. Deleting a database should normally be denied.

The key Stage 01 principle is already correct: **Tool execution belongs to the Runtime, not the model.** That ownership is what makes later authorization and HITL possible.

---

## 5. Failure: a Tool hangs

Suppose:

```python
def get_weather(city):
    return remote_api(city)
```

and the remote service never returns.

`max_steps=5` does nothing because the first step has not completed.

This requires different controls:

```text
per-Tool timeout
request timeout
cancellation
async execution
```

A step budget and a time budget are different dimensions.

---

## 6. Failure: one model turn contains many ToolCalls

A model may return:

```text
get_weather(Tokyo)
get_weather(Paris)
get_weather(New York)
```

Stage 01 can represent them together, but executes handlers sequentially:

```python
for call in response.tool_calls:
    execute(call)
```

Concurrent execution raises new questions:

```text
What is the concurrency limit?
What if one call fails?
Should the others be cancelled?
How are results correlated and ordered?
```

So multiple ToolCalls are a decision-representation capability; concurrent execution is separate Runtime semantics.

---

## 7. Failure: provider state and Runtime state become confused

Responses API can continue provider-managed context using mechanisms such as `previous_response_id`.

Stage 01 mostly replays a Tiny-Agent transcript instead.

That separation is deliberate. Once provider state is added, you must answer:

```text
Who persists the response ID?
What happens after process restart?
Can one thread have concurrent runs?
Which store is the source of truth?
How do checkpoints interact with provider state?
```

Conversation history, provider conversation state, Runtime state, checkpoints, and long-term memory are different concepts. Later state and persistence stages compare them explicitly.

---

## 8. Failure: the message transcript is no longer enough for debugging

`AgentResult.messages` is useful because it exposes:

```text
User -> Action -> Observation -> ... -> Final
```

Production systems also need to know model latency, Tool latency, token usage, step duration, request identity, failure rates, and task success.

Those require real logging, tracing, metrics, and evaluation. A transcript is not an observability system.

---

## 9. Failure: the final answer is correct but the trajectory is wrong

Suppose the task explicitly requires the weather Tool.

Two Agents both answer `18°C`.

Agent A:

```text
ToolCall -> observation 18 -> final
```

Agent B:

```text
guess 18 -> final
```

A final-answer-only test marks both correct, even though B violated the task contract.

Agent evaluation therefore needs at least two lenses:

```text
answer quality
trajectory quality
```

Stage 01 makes trajectory visible; Stage 08 turns that into a systematic evaluation discipline.

---

## 10. Why not solve everything in Stage 01?

Two teaching styles both fail.

### Too little engineering

```text
10-line Tool demo
   ↓
“production Agent complete”
```

### Too much engineering too early

```text
async + retry + RBAC + checkpoint + tracing + Redis + queue + sandbox
```

all mixed into the first Runtime.

High-quality instruction uses progressive disclosure:

> **Teach one mechanism deeply, name its limitations, and show where later stages strengthen it.**

Tiny-Agent therefore grows the same boundaries over time rather than hiding everything behind a framework on day one.

---

## 11. Durable principles vs Stage 01 simplifications

### Architecture principles that should survive later stages

```text
model proposes; Runtime executes
Provider Adapter does not own the Agent loop
provider output is normalized before entering core Runtime logic
ToolCall and Observation stay correlated
Runtime owns explicit stopping control
capabilities enter execution through a governed Tool boundary
deterministic control logic should support deterministic tests
```

### Deliberate Stage 01 simplifications

```text
max_steps is the only major budget
no complete local JSON-Schema validation
mostly synchronous Tool execution
no permission / approval policy
no retry / timeout policy
no checkpoint / resume
no full tracing / metrics / evaluation
conservative provider-state handling
```

A learner should know not only how the current code works, but also **what it does not yet claim to solve**.

---

## 12. What Stage 01 has really built

We now have:

```text
Model boundary
Provider Adapter
normalized ToolCall / ModelResponse
ToolRegistry
AgentRuntime
Observation loop
call_id correlation
step bound
deterministic Runtime tests
```

And we know that none of those words mean “production complete.”

That is the standard a serious tutorial should aim for: explain how a mechanism works, why the boundaries exist, what problem each boundary solves, and where the current design still fails.

Stage 02 starts from the next question:

> **Now that the Runtime can let a model choose the next action, should every task become an Agent loop?**

No — and understanding why is the next step.
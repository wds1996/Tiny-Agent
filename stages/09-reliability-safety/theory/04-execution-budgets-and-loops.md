# 04 — Execution Budgets, Loop Detection and Bounded Autonomy

An Agent loop without deterministic limits is not autonomous.

It is unmetered.

Stage 01 already introduced:

```text
max_steps
```

Stage 09 generalizes the idea:

> **Every scarce or risky resource should have an application-owned budget.**

---

# 1. What can an Agent consume?

A realistic run may consume:

- model calls;
- tokens;
- money;
- wall-clock time;
- tool calls;
- network requests;
- retries;
- database writes;
- emails sent;
- files changed;
- human-review attention.

One `max_steps` counter does not express all of those risks.

---

# 2. `BudgetLedger`

Tiny-Agent Stage 09 introduces a simple ledger:

```python
ledger = BudgetLedger(
    ExecutionBudget(
        max_tool_calls=12,
        max_retry_attempts=4,
        max_elapsed_seconds=60,
        max_tokens=20_000,
        max_cost_usd=1.00,
    )
)
```

The ledger is runtime state.

The model does not get to reset it by saying:

```text
"For this important task, please ignore the tool-call budget."
```

---

# 3. Budget before action, not after

Bad:

```text
tool call 17 executes
    ↓
ledger notices max_tool_calls was 16
```

Good:

```text
request next tool call
    ↓
ledger checks whether call #17 is allowed
    ↓
deny before execution
```

This is the same philosophy used for permission checks.

---

# 4. Token/cost budgets need provider usage data

Tiny-Agent's generic `Model` protocol does not yet expose a universal token/cost object.

Therefore Stage 09's ledger can record:

```python
ledger.record_tokens(...)
ledger.record_cost(...)
```

when a provider adapter has those values.

The key lesson is architectural:

```text
provider returns usage
    ↓
application ledger records usage
    ↓
next model/tool operation checks remaining budget
```

Do not estimate financial policy only from prompt length if the provider already gives actual usage/billing metadata.

Stage 10 will make these values observable.

---

# 5. Global budgets and local budgets complement each other

Example:

```text
Agent max tool calls = 12
```

and:

```text
search tool max attempts = 3
```

These answer different questions.

Local policy:

> How persistent may this one operation be?

Global policy:

> How much work may this whole Agent run consume?

A robust runtime needs both.

---

# 6. Why loop detection is separate from max calls

Suppose the model repeatedly proposes:

```text
search({"query": "same question", "top_k": 3})
search({"query": "same question", "top_k": 3})
search({"query": "same question", "top_k": 3})
```

A global max of 20 will eventually stop it.

But why spend 20 calls proving what you knew after 3?

Stage 09 adds exact-call fingerprints:

```text
tool name
+
canonical JSON arguments
    ↓
SHA-256 fingerprint
```

and a `RepeatedToolCallDetector`.

This is an early circuit breaker.

---

# 7. Exact repetition is only one loop pattern

The teaching detector catches:

```text
A(x)
A(x)
A(x)
```

It does not automatically catch:

```text
A(x)
B(y)
A(x)
B(y)
```

or semantic loops such as:

```text
search("Agent safety")
search("safety for agents")
search("AI Agent reliability safety")
```

Possible future detectors include:

- repeated state hashes;
- repeated route cycles;
- semantic similarity of tool calls;
- no-progress detectors;
- graph cycle counters;
- task-specific convergence checks.

Do not oversell a hash counter as a general Agent loop theorem.

---

# 8. No-progress detection is often more useful than repetition

Imagine:

```text
Tool call changes every time
but
important state never improves
```

For example:

```text
remaining_tasks = 4
remaining_tasks = 4
remaining_tasks = 4
```

The Agent is technically doing different things but making no progress.

A stronger production runtime might define a progress invariant:

```python
progress_score(new_state) > progress_score(old_state)
```

or monitor task completion.

This is domain-specific, so Tiny-Agent does not invent a fake universal score.

---

# 9. Unbounded consumption is both reliability and security

An attacker may intentionally induce:

- long prompts;
- recursive planning;
- repeated retrieval;
- expensive tool calls;
- huge output generation.

But the same failure can happen accidentally through a model loop.

Therefore resource budgets defend against both:

```text
malice
and
mistake
```

This is why Stage 09 treats budgets as runtime policy, not merely cost optimization.

---

# 10. Budget exhaustion is a normal terminal state

Do not crash with a mystery exception after consuming everything.

A useful runtime can represent:

```text
ToolFailure[budget_exceeded]
```

Then the application may:

- stop;
- ask the user to narrow the task;
- save resumable state;
- request higher authorization/budget;
- fall back to a cheaper workflow.

Budget exhaustion should be predictable.

---

# 11. Humorous memory aid

Telling an Agent:

```text
"Please be economical."
```

is a suggestion.

Giving it a `BudgetLedger` is taking away the corporate credit card after the limit is reached.

Runtime enforcement wins.

---

## Code to inspect

- `src/tiny_agent/reliability.py`
- `code/execution_budget.py`
- `code/loop_detection.py`

Run:

```bash
python stages/09-reliability-safety/code/execution_budget.py
python stages/09-reliability-safety/code/loop_detection.py
```

---

## Completion check

Explain:

1. Why max steps is not a complete budget model.
2. Local retry limits vs global retry budget.
3. Why budgets must be checked before execution.
4. Exact repeated-call detection vs semantic/no-progress loops.
5. Why token/cost tracking belongs in application state.
6. Why unbounded consumption is both a reliability and security concern.
7. Why budget exhaustion should be an explicit terminal condition.

# Stage 07 — Reliability, Safety & Tool Governance

Stage 07 turns Tiny-Agent from a system that **can execute** into one that can **refuse, bound, retry, time out, and mediate execution predictably**.

Stages 00–06 deliberately introduced capability first:

```text
LLM decisions
    -> Tool execution
    -> planning / graph state
    -> RAG
    -> MCP external capabilities
    -> durable memory / HITL
```

Stage 07 asks the control-plane question:

> **What authority should an LLM have, and what authority must remain deterministic application policy?**

The central lesson is:

> **Model output is untrusted program input. Validate the proposal, minimize its authority, bound its resources, and mediate every side effect outside the model.**

---

# Why this stage exists

Agent demos often assume:

```text
valid arguments
healthy network
well-behaved model
safe tool
unlimited budget
honest retrieved content
```

Real systems encounter:

```text
malformed ToolCalls
provider/network failures
timeouts and cancellation
repeated loops
expensive runaway trajectories
permission boundaries
stale or mismatched approvals
indirect prompt injection
secret-bearing exceptions
unsafe downstream output
untrusted code/processes
```

The goal is not to make failure impossible.

The goal is to make failure **classified, bounded, visible, and recoverable without silently expanding authority**.

---

# Prerequisites

Complete Stage 00–06, or already understand:

- Structured Output / Function Calling;
- `Tool` / `ToolRegistry` and ReAct execution;
- workflow and Agent budgets;
- explicit graph state;
- RAG external-evidence trust boundaries;
- MCP Host/Client/Server and remote capabilities;
- durable checkpoints and long-term memory;
- approve/edit/reject HITL;
- basic Python `async` / `await`.

Stage 06 is particularly important because Stage 07 builds on:

```text
approval != authorization
external content != authority
durable execution != exactly-once side effect
```

---

# Audit fixes before new material

Stage 07 begins by correcting two production gaps in the existing integrated runtime.

## 1. Arbitrary exception text no longer enters the model transcript

Old Stage 01-style behavior:

```python
except Exception as exc:
    return f"ToolError[{type(exc).__name__}]: {exc}"
```

could expose:

```text
connection strings
internal paths
provider response bodies
secret fragments
implementation details
```

The reusable runtime now converts unexpected exceptions to a model-safe failure:

```text
ToolFailure[internal_error]: Tool execution failed.
```

while retaining the internal exception type for later logging/observability.

## 2. `ToolRegistry` now exposes `get()`

Stage 07 policy code must inspect a Tool's schema/handler before execution without reaching into a private `_tools` dictionary.

The registry therefore gains a small public lookup method while preserving the Stage 01 execution API.

---

# Learning path

```text
failure taxonomy + safe redaction
        ↓
local argument validation
        ↓
jsonschema + Pydantic strict boundaries
        ↓
timeout / cancellation
        ↓
retryable failure vs retry-safe operation
        ↓
backoff / jitter / Tenacity comparison
        ↓
run-wide budgets
        ↓
exact repeated-call detection
        ↓
default-deny Tool permissions
        ↓
exact-action approval binding
        ↓
prompt-injection trust boundaries
        ↓
process vs sandbox concepts
        ↓
GuardedToolExecutor
```

Do not jump straight to the final executor. Each preceding mechanism explains one line of policy inside it.

---

# Learning objectives

After Stage 07, you should be able to:

1. distinguish safe operational errors from arbitrary internal exceptions;
2. explain why raw `str(exc)` should not enter model context;
3. validate dynamic Tool arguments locally before handler invocation;
4. compare a handwritten schema subset with the maintained `jsonschema` package;
5. use Pydantic strict mode for stable application-owned typed boundaries;
6. explain validation vs authorization;
7. explain async timeout vs cancellation;
8. explain why a timed-out worker thread may still be running;
9. distinguish retryable failure from retry-safe/idempotent action;
10. implement bounded exponential backoff and explain jitter;
11. compare the handwritten retry mechanism with Tenacity;
12. maintain run-wide tool/retry/time/token/cost budgets;
13. detect exact repeated ToolCalls before the global cap is exhausted;
14. explain why exact repetition is not a universal loop detector;
15. use a default-deny Tool allowlist and authenticated Principal context;
16. explain discovery vs authorization;
17. bind human approval to the exact Tool + arguments reviewed;
18. explain why approval still does not replace role/downstream authorization;
19. identify excessive functionality, permissions, and autonomy;
20. explain direct vs indirect prompt injection;
21. keep external content in the data plane instead of letting it rewrite control policy;
22. explain why RAG or prompt delimiters do not inherently solve prompt injection;
23. treat injection detectors as signals rather than permission systems;
24. explain why narrow Tools are safer than generic shell/API proxy Tools;
25. distinguish an in-process function, worker thread, child process, container, and security sandbox;
26. draw the complete guarded execution pipeline from model proposal to side effect.

---

# Part A — Fail safely

Read:

1. [`theory/01-agent-failure-modes.md`](theory/01-agent-failure-modes.md)

Run:

```bash
python stages/07-reliability-safety/code/error_model.py
```

Remember:

```text
known + deliberately sanitized failure
    -> may cross model boundary

unexpected exception
    -> generic model-safe failure
    -> detailed diagnostics remain internal
```

---

# Part B — Validate before execution

Read:

2. [`theory/02-validation-and-output-handling.md`](theory/02-validation-and-output-handling.md)

Run:

```bash
python stages/07-reliability-safety/code/validation_boundary.py
```

The teaching progression is:

```text
SimpleToolArgumentsValidator
    -> inspect validation mechanics

JsonSchemaToolArgumentsValidator
    -> mature dynamic JSON Schema validation

Pydantic strict model
    -> stable application-owned Python boundary
```

The important relationship is:

```text
provider constrained generation
    !=
local runtime validation
    !=
authorization
```

Use all three where appropriate.

---

# Part C — Timeout, cancellation and retry

Read:

3. [`theory/03-timeout-retry-cancellation.md`](theory/03-timeout-retry-cancellation.md)

Run:

```bash
python stages/07-reliability-safety/code/retry_policy.py
```

The rule to memorize:

```text
retryable failure
AND
retry-safe operation
AND
attempts remain
AND
global retry budget remains
    ↓
retry
```

not:

```text
exception happened
    ↓
retry everything forever
```

---

# Part D — Bound autonomy

Read:

4. [`theory/04-execution-budgets-and-loops.md`](theory/04-execution-budgets-and-loops.md)

Run:

```bash
python stages/07-reliability-safety/code/execution_budget.py
python stages/07-reliability-safety/code/loop_detection.py
```

Tiny-Agent now models:

```text
tool-call budget
retry budget
elapsed-time budget
token budget
cost budget
```

Token/cost values are recorded when provider usage metadata is available; Stage 08 will make those values observable and evaluable.

---

# Part E — Minimize authority

Read:

5. [`theory/05-tool-permissions-and-least-privilege.md`](theory/05-tool-permissions-and-least-privilege.md)

Run:

```bash
python stages/07-reliability-safety/code/permission_policy.py
```

The key chain is:

```text
authenticated application Principal
        ↓
default-deny Tool allowlist
        ↓
role check
        ↓
exact-action approval if required
        ↓
downstream authorization
```

An `ApprovalGrant` is intentionally bound to:

```text
tool name + canonical JSON arguments
```

so an approval for staging cannot silently become permission for production after arguments change.

---

# Part F — Prompt injection and trust boundaries

Read:

6. [`theory/06-prompt-injection-and-sandboxing.md`](theory/06-prompt-injection-and-sandboxing.md)

Run:

```bash
python stages/07-reliability-safety/code/prompt_injection_boundary.py
python stages/07-reliability-safety/code/sandbox_boundary.py
```

The most important architecture is:

```text
DATA PLANE
user/retrieved/web/MCP/tool-result text
        ↓
model may be influenced
        ↓
model proposes action
        ↓

CONTROL PLANE
validation
permissions
approval
budgets
credentials
sandbox policy
        ↓
allow / deny
```

The tiny injection detector is intentionally **not** an authorization boundary.

---

# Part G — Compose the guarded runtime

Read:

7. [`theory/07-guarded-runtime-and-production.md`](theory/07-guarded-runtime-and-production.md)

Run:

```bash
python stages/07-reliability-safety/code/guarded_tool_runtime.py
```

`GuardedToolExecutor` enforces:

```text
budget
  -> validation
  -> permission
  -> exact approval binding
  -> loop detection
  -> timeout
  -> execute
  -> safe failure classification
  -> bounded retry when safe
```

The Stage 01 `AgentRuntime` remains intentionally small. Stage 07 adds a stronger execution layer around `ToolRegistry` instead of turning the beginner runtime into a 500-line security framework.

---

# Code map

```text
code/
├── error_model.py
├── validation_boundary.py
├── retry_policy.py
├── execution_budget.py
├── permission_policy.py
├── loop_detection.py
├── guarded_tool_runtime.py
├── prompt_injection_boundary.py
└── sandbox_boundary.py
```

Suggested order is exactly the order above.

---

# Theory map

```text
theory/
├── 01-agent-failure-modes.md
├── 02-validation-and-output-handling.md
├── 03-timeout-retry-cancellation.md
├── 04-execution-budgets-and-loops.md
├── 05-tool-permissions-and-least-privilege.md
├── 06-prompt-injection-and-sandboxing.md
└── 07-guarded-runtime-and-production.md
```

---

# Install

The core reliability/governance mechanisms remain dependency-light.

For the mature Stage 07 comparison libraries and all tests/examples:

```bash
python -m pip install -e ".[dev,stage07]"
```

The optional extra adds:

```text
jsonschema >= 4.25, < 5
Tenacity   >= 9, < 10
Pydantic   >= 2.11, < 3
```

Earlier stages do not need these packages.

---

# Tests

Framework-neutral/core tests:

```bash
pytest -q \
  tests/test_reliability.py \
  tests/test_validation.py \
  tests/test_governance.py \
  tests/test_guarded_runtime.py \
  tests/test_trust.py
```

Optional-library compatibility:

```bash
pytest -q tests/test_stage07_integrations.py
```

Run these tests directly while studying the stage; repository-maintenance automation is intentionally outside the curriculum tree.

---

# External learning resources

Use current official/security references as the source of truth. Security advice ages faster than many tutorial snippets.

## 1. OWASP GenAI Security — threat model first

Read these after Theory 01–06:

- Prompt Injection — LLM01:2025  
  <https://genai.owasp.org/llmrisk/llm012025-prompt-injection/>
- Improper Output Handling — LLM05:2025  
  <https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/>
- Excessive Agency — LLM06:2025  
  <https://genai.owasp.org/llmrisk/llm062025-excessive-agency/>
- Unbounded Consumption — LLM10:2025  
  <https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/>

Map them to Tiny-Agent:

```text
Prompt Injection
    -> external content remains untrusted

Improper Output Handling
    -> validate before downstream execution

Excessive Agency
    -> narrow Tools + least privilege + HITL

Unbounded Consumption
    -> deterministic budgets / rate and action limits
```

## 2. Python async timeout/cancellation

- `asyncio` task/timeouts:  
  <https://docs.python.org/3/library/asyncio-task.html>

Focus on:

```text
wait_for
timeout
CancelledError
to_thread
```

Then reread the Stage 07 warning that timing out a worker thread is not equivalent to killing the underlying synchronous function.

## 3. JSON Schema

- `jsonschema` documentation:  
  <https://python-jsonschema.readthedocs.io/>
- validator API / `validator_for`:  
  <https://python-jsonschema.readthedocs.io/en/stable/validate/>

Use this after understanding the handwritten subset.

## 4. Pydantic strict validation

- Strict mode:  
  <https://docs.pydantic.dev/latest/concepts/strict_mode/>

Use this to compare dynamic JSON-schema Tool contracts with stable typed application models.

## 5. Tenacity

- Tenacity docs:  
  <https://tenacity.readthedocs.io/>

Focus on:

```text
stop
wait
retry predicate
async retry
```

Then ask the Tiny-Agent question that the library cannot answer for you:

> Is this business operation actually safe to repeat?

## 6. LangChain middleware/guardrails comparison

Read only after the first-principles guarded executor is clear:

- Middleware overview:  
  <https://docs.langchain.com/oss/python/langchain/middleware/overview>
- Built-in middleware:  
  <https://docs.langchain.com/oss/python/langchain/middleware/built-in>
- Guardrails:  
  <https://docs.langchain.com/oss/python/langchain/guardrails>
- Human-in-the-loop:  
  <https://docs.langchain.com/oss/python/langchain/human-in-the-loop>

Current middleware packages higher-level versions of patterns such as tool/model call limits, fallback, retry, PII handling, and HITL. Tiny-Agent teaches the mechanisms first so these do not look like magic decorators.

---

# Recommended reading order

```text
1. Stage 01 production-limitations refresher
2. Stage 07 Theory 01 + error_model.py
3. Theory 02 + validation_boundary.py
4. jsonschema / Pydantic official docs
5. Theory 03 + retry_policy.py
6. Python asyncio + Tenacity docs
7. Theory 04 + budget / loop examples
8. OWASP Unbounded Consumption
9. Theory 05 + permission_policy.py
10. OWASP Excessive Agency
11. Theory 06 + injection / sandbox examples
12. OWASP Prompt Injection + Improper Output Handling
13. Theory 07 + guarded_tool_runtime.py
14. LangChain middleware / guardrails comparison
15. exercises/review-questions.md
```

---

# Stage boundary

Stage 07 establishes a **guarded runtime architecture**, not a claim of complete enterprise security.

Explicitly deferred or deployment-specific:

- enterprise IAM / RBAC / ABAC administration;
- signed/expiring approval workflows;
- distributed rate limiting and circuit breakers;
- exactly-once distributed side effects;
- hardened arbitrary-code sandboxing;
- secret-management systems;
- DLP / malware scanning / browser isolation;
- complete prompt-injection prevention;
- formal security verification;
- production audit retention/compliance;
- red-team automation;
- tracing/metrics/evaluation dashboards (Stage 08);
- service deployment and infrastructure hardening (Stage 10).

Do not call `asyncio.to_thread()` a sandbox. Do not call a substring detector prompt-injection prevention. Do not call a human click authorization.

Precise names produce better systems.

---

# Milestone

By the end of Stage 07, you should be able to build and explain:

```text
model proposal
    ↓
local validation
    ↓
least-privilege permission
    ↓
exact-action human approval when needed
    ↓
budget / loop controls
    ↓
timeout
    ↓
retry only when both failure and action are safe
    ↓
model-safe result/failure
```

The key question is no longer:

> Can the Agent call this Tool?

It is:

> **Under which identity, validated arguments, permissions, approval, budgets, retry semantics, trust boundary, and isolation level may this Tool be allowed to affect the real world?**
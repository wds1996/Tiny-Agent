# Stage 09 Review, Coding and Interview Exercises

Do these after running all Stage 09 examples. The goal is to explain **why a runtime control exists**, not merely remember a class name.

---

# Part A — Core concepts

1. Why is model output better treated as untrusted program input than as an instruction with authority?
2. Why is `except Exception as exc: return str(exc)` dangerous in an Agent runtime?
3. What information may safely be shown to the model after a Tool failure? What information belongs only in engineering logs?
4. Give three examples of retryable operational failures and three failures that should normally not be retried.
5. Explain `retryable failure != retry-safe operation` using a payment or email example.
6. Why can an idempotency key make a network retry safer?
7. Why should `asyncio.CancelledError` normally propagate instead of becoming an ordinary Tool failure?
8. What is the difference between timing out an async task and timing out a synchronous function running in a worker thread?
9. Why is a child process killable while a worker thread generally is not safely hard-killed by Python?
10. Why is a subprocess still not automatically a secure sandbox?

---

# Part B — Validation

11. Structured Output already constrains model generation. Why validate locally again?
12. What is the difference between malformed Tool arguments and a malformed application-owned Tool schema?
13. Why is `additionalProperties: false` useful for high-risk Tools?
14. Explain why `True` should not be accepted as an integer in a strict Tool boundary even though Python treats `bool` as a subclass of `int`.
15. When would you use dynamic JSON Schema validation instead of a Pydantic model?
16. When would a strict Pydantic model be more convenient than dynamic JSON Schema?
17. What does strict mode protect you from? When might coercion still be intentional?
18. Why does successful schema validation not imply authorization?
19. Give an example of a syntactically valid ToolCall that should still be denied by business policy.
20. Why should model-generated SQL/shell/HTML/paths receive context-specific downstream validation?

---

# Part C — Retry / backoff / fallback

21. Draw an exponential backoff sequence beginning at 0.5 seconds with a 4-second cap.
22. Why is jitter useful when many Agent workers share the same dependency?
23. What is a thundering herd?
24. Why do we need both per-tool attempt limits and a run-wide retry budget?
25. Explain retry vs fallback.
26. Why can silent fallback make evaluation and incident debugging difficult?
27. A read-only search API returns 503. Should it be retried? What extra facts do you need?
28. `send_email()` times out. Should it be retried? What would make the answer safer?
29. A Tool raises `PermissionError`. Why is retrying usually wrong?
30. A Tool raises an unexpected `TypeError`. Why should the runtime avoid automatically calling it an input error?

---

# Part D — Budgets and loops

31. Why is `max_steps` alone not a complete resource budget?
32. List five resources an Agent run may need to budget.
33. Why should a budget be checked before an operation rather than after it?
34. What is Denial of Wallet in an LLM application?
35. How can a benign model bug produce the same resource-consumption pattern as a malicious attack?
36. What does Tiny-Agent's exact repeated-call detector catch?
37. Give two loop patterns it does **not** catch.
38. Design a no-progress detector for a hypothetical Planner–Executor where `remaining_tasks` should decrease.
39. Why might semantic loop detection create false positives?
40. What should a user-facing Agent do when a cost/tool budget is exhausted?

---

# Part E — Permissions and governance

41. Explain capability discovery vs authorization using MCP.
42. Why should `Principal` come from authenticated application context rather than the LLM?
43. What is default deny?
44. Why is default deny useful when connecting a new MCP server that unexpectedly exposes extra Tools?
45. Explain OWASP's idea of excessive functionality, excessive permissions, and excessive autonomy in your own words.
46. Why is `run_shell(command: str)` a much larger capability surface than `restart_service(service_id)`?
47. Human approval exists. Why do you still need role authorization?
48. Why is `approved=True` an insufficient representation of a reviewed action?
49. Explain how binding approval to Tool + arguments reduces time-of-check/time-of-use mistakes.
50. A reviewer approved deployment to staging. The model later changes the argument to production. What should happen?
51. Why should the downstream service/database still enforce its own permissions?
52. Why is using a database superuser credential for a read-only Agent a design failure even if the Tool code only exposes SELECT?

---

# Part F — Prompt injection and trust

53. Direct prompt injection vs indirect prompt injection.
54. Give an indirect injection example involving RAG.
55. Give one involving MCP Resources or Tool results.
56. Why don't `<untrusted>...</untrusted>` delimiters create a hard security boundary?
57. Why is a regex/keyword injection detector useful even though it is bypassable?
58. Why must such a detector never become the sole permission check?
59. Explain data plane vs control plane for an Agent.
60. Which category contains retrieved text? Which category contains Tool allowlists?
61. Why should a retrieved document never be allowed to rewrite permission policy simply because the model says it is an instruction?
62. How can least privilege contain the damage even when the LLM follows a malicious instruction?
63. Why does RAG not inherently solve prompt injection?
64. Why should credentials normally stay inside Tool adapters rather than model context?

---

# Part G — Sandboxing

65. What security properties does `asyncio.to_thread()` provide? What does it not provide?
66. What additional property does a child process provide?
67. What could a normal-user subprocess still access?
68. List at least six controls a serious untrusted-code sandbox may require.
69. Why can network egress be as important as filesystem isolation?
70. Why are ephemeral workspaces useful?
71. Why should secrets be minimized even inside a sandbox?
72. When is a generic shell Tool justified? What controls would you require?

---

# Part H — Coding exercises

## Exercise 1 — Add a rate-like budget

Extend `ExecutionBudget` / `BudgetLedger` with a maximum number of external requests distinct from Tool calls.

Requirements:

- deterministic tests;
- check before request;
- clear model-safe exhaustion reason;
- do not use wall-clock sleep in tests.

## Exercise 2 — Retry with idempotency metadata

Create a mock `create_order` Tool with an `idempotency_key` argument.

Demonstrate:

```text
first attempt applies order but loses response
second attempt receives same key
no duplicate order is created
```

Then explain why the operation can be marked `retry_safe=True`.

## Exercise 3 — No-progress detector

Build a detector for state such as:

```python
{"remaining_tasks": 3}
```

Stop when it fails to improve for N consecutive workflow transitions.

Test both:

- legitimate temporary plateau;
- true no-progress loop.

## Exercise 4 — Expiring approval

Extend `ApprovalGrant` with an application-owned expiry timestamp or issued-at + TTL.

Questions:

- Which clock should be used?
- Does expiry make the grant cryptographically trustworthy?
- What else would production approval records need?

## Exercise 5 — Resource version binding

Bind approval not only to Tool arguments but also a resource version:

```text
report_id = r-7
version = 12
```

Reject execution if the report has changed to version 13 after review.

## Exercise 6 — Permission narrowing by route

Use Stage 02 routing to select:

```text
research route
    -> read-only Tools

operations route
    -> operational Tools
```

Do not expose the union of all Tools to every route.

## Exercise 7 — MCP allowlist

Connect a mock MCP server exposing five Tools, but only register/allow two for a specific Agent role.

Explain:

```text
discovered tools
!=
model-visible tools
!=
executable tools
```

## Exercise 8 — Output sanitization

Create a Tool result containing HTML and show how a web UI should escape/render it safely instead of inserting raw model/Tool text into the DOM.

## Exercise 9 — Process boundary

Extend `sandbox_boundary.py` so the child process:

- receives a fixed input file;
- writes only to a temporary directory;
- has a timeout;
- is killed on timeout;
- cleans up its workspace.

Then list the important isolation guarantees it still does not provide.

## Exercise 10 — Guarded ReAct adapter

Build an **async** ReAct runtime that delegates all Tool execution to `GuardedToolExecutor`.

Keep these responsibilities separate:

```text
Agent loop
    -> model/tool feedback

Guarded executor
    -> validation/permission/budget/retry/timeout
```

Do not duplicate the policy logic inside the loop.

---

# Part I — Interview questions

73. "How would you make an LLM Agent safe to use internal company tools?"
74. "Structured Outputs guarantee valid JSON. Why do I still need validation?"
75. "How do you decide whether a failed Tool call should be retried?"
76. "What is the difference between timeout and cancellation?"
77. "Why can't `asyncio.wait_for(asyncio.to_thread(...))` kill a hung native library call?"
78. "How would you prevent an Agent from spending unlimited money?"
79. "How do you detect Agent loops?"
80. "Why isn't max_steps enough?"
81. "How do you implement least privilege for Tool-using Agents?"
82. "What is Excessive Agency?"
83. "What is indirect prompt injection?"
84. "Can RAG prevent prompt injection?"
85. "How would you defend against malicious instructions embedded in a retrieved document?"
86. "What's the difference between HITL approval and authorization?"
87. "How would you prevent a reviewed ToolCall from being modified after approval?"
88. "What makes a sandbox a sandbox?"
89. "Would you expose a shell Tool to an LLM? Under what circumstances?"
90. "What should be logged when a Tool fails without leaking secrets to the model?"

---

# Part J — Architecture challenge

Design a production-oriented Agent that can:

```text
search internal documents
read customer records
send an email
restart a service
```

Define for each Tool:

- JSON schema;
- model-visible description;
- roles allowed;
- whether HITL is required;
- exact approval payload;
- timeout;
- retry policy;
- retry-safe/idempotency reasoning;
- global budget impact;
- credential scope;
- audit event;
- external-content trust assumptions;
- sandbox/isolation requirement.

Then answer:

> If the model were completely manipulated by an indirect prompt injection, what is the maximum damage it could still cause under your deterministic policies?

That question is one of the best tests of whether your Agent architecture actually uses least privilege.

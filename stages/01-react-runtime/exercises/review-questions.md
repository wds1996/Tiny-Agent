# Stage 01 Review Questions and Exercises

## Concept review

1. What turns repeated function calling into an Agent loop?
2. What is the difference between an action and an observation?
3. Why should `AgentRuntime` depend on a provider-neutral `Model` interface?
4. Why normalize provider responses into internal `ToolCall` / `ModelResponse` types?
5. What does `ToolRegistry` protect the runtime from?
6. Why should a model-generated tool call be treated as a proposal rather than an unconditional command?
7. Why must an Agent have stopping conditions?
8. What does `max_steps` protect against, and what does it *not* protect against?
9. When is it reasonable to turn a tool exception into an observation?
10. Why should deterministic unit tests use a fake/scripted model?
11. What is the difference between a unit test and a real-model evaluation?
12. Why does implementing ReAct not require exposing full model chain-of-thought?

## Coding exercise 1 — Real model adapter

Implement one provider adapter that satisfies:

```python
class Model(Protocol):
    def generate(self, messages, tools) -> ModelResponse:
        ...
```

Requirements:

- provider-specific SDK objects must stay inside the adapter;
- tool calls must be converted to Tiny-Agent `ToolCall` objects;
- plain final text must become `ModelResponse(final_answer=...)`;
- `AgentRuntime` must not be modified.

Test with:

```text
Calculate (23 * 17) + 41 and explain the result.
```

Use `multiply(a, b)` and `add(a, b)` tools. The model should decide the sequence itself.

## Coding exercise 2 — Recover from an invalid tool call

Create a fake model with this trajectory:

```text
turn 1 -> call add(a="bad", b=2)
turn 2 -> after seeing ToolError, call add(a=3, b=2)
turn 3 -> final answer
```

Verify that the runtime does not crash on the first recoverable tool error.

## Coding exercise 3 — Step-limit failure

Create a fake model that always requests the same tool.

Expected result:

```text
Agent exceeded max_steps=...
```

Then answer:

- Why is this preferable to an unlimited loop?
- What additional limits would be useful in production?

## Coding exercise 4 — Multiple calls in one model turn

Return two independent tool calls in one `ModelResponse` and verify that both observations are appended correctly.

Think about the next-stage question:

> Should independent calls be executed sequentially or concurrently?

## Interview-style questions

1. Explain the full lifecycle of a tool call from model output to the next model input.
2. If the company changes from one LLM provider to another, what code should ideally change?
3. How would you prevent an Agent from entering an infinite loop?
4. Why might returning every exception to the model be unsafe or incorrect?
5. In what situations would you choose a deterministic workflow instead of ReAct?
6. What capabilities are still missing before you would call this runtime production-ready?

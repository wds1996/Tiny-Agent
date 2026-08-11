# Stage 00 Review Questions

Use these questions to check whether you understand the runtime boundary rather than only the API syntax.

## Concepts

1. What is the difference between a model provider and an Agent runtime?
2. Why should provider-specific response objects be normalized before entering core Agent logic?
3. What does a `tool` message represent?
4. Why is structured output useful at software control boundaries?
5. How is schema-constrained structured output different from simply prompting "return JSON"?
6. What is the difference between structured output and function calling?
7. Does an LLM directly execute a Python tool? Explain the exact sequence.
8. Which parts of a tool are visible to the model, and which belong only to the runtime?
9. Why must tool arguments be validated before execution?
10. Why must a tool result be returned to the model?
11. What turns a single tool call into an iterative tool-use loop?
12. Why is a minimal tool-use loop still not a production Agent runtime?

## Coding exercises

### Exercise 1 — Add a division tool

Extend `../code/minimal_tool_loop.py` with a `divide(a, b)` tool.

Requirements:

- reject division by zero;
- represent the failure clearly;
- do not hide the exception with a fake successful value.

### Exercise 2 — Unknown tool

Modify the scripted model so that it proposes a tool that is not in the registry.

Observe where the error occurs and explain why the runtime, not the model, is responsible for enforcing the registry.

### Exercise 3 — Add argument validation

Before calling the handler, check that the requested arguments match the expected shape.

Think about what should happen when:

- an argument is missing;
- an unexpected argument is supplied;
- the value has the wrong type.

### Exercise 4 — Replace the fake model

Implement a real provider adapter while keeping the tool loop itself unchanged.

The important constraint is:

> Provider-specific parsing belongs in the adapter, not in `run_tool_loop`.

## Interview-style questions

1. "Function calling is an Agent." Do you agree? Why or why not?
2. If the model requests `delete_database()`, should the runtime execute it automatically because the model chose it?
3. If a company switches model providers, which part of a well-designed Agent system should ideally change?
4. Why can tool descriptions affect tool-selection accuracy?
5. What production features are still missing from the Stage 00 loop?

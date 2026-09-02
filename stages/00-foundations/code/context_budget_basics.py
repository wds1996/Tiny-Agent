# Stage 00 keeps this provider-neutral. Stage 06A implements the reusable policy.

max_context = 32_000
reserve_output = 4_000
reserve_runtime = 2_000
available_input = max_context - reserve_output - reserve_runtime

components = {
    "system_and_task": 1_200,
    "tool_schemas": 2_800,
    "recent_history": 4_000,
    "retrieved_evidence": 9_000,
}

used = sum(components.values())
print("available input:", available_input)
print("planned input:", used)
print("remaining:", available_input - used)

assert used <= available_input, "context plan exceeds input budget"

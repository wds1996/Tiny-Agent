"""Stage 00: reason about Context as an explicit budget.

Run:
    python stages/00-foundations/code/context_budget_basics.py

The numbers in this file are teaching values, not the specification of a
particular OpenAI model. Real systems should use the selected model/API limits
and provider usage/tokenization data.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContextPlan:
    """A tiny planning model for one future model request."""

    max_working_tokens: int
    reserve_output_tokens: int
    reserve_runtime_tokens: int
    components: dict[str, int] = field(default_factory=dict)

    @property
    def available_input_tokens(self) -> int:
        return (
            self.max_working_tokens
            - self.reserve_output_tokens
            - self.reserve_runtime_tokens
        )

    @property
    def planned_input_tokens(self) -> int:
        return sum(self.components.values())

    @property
    def remaining_input_tokens(self) -> int:
        return self.available_input_tokens - self.planned_input_tokens

    def validate(self) -> None:
        if self.available_input_tokens < 0:
            raise ValueError("reserves exceed the working token budget")
        if self.remaining_input_tokens < 0:
            raise ValueError("planned input exceeds the available input budget")


plan = ContextPlan(
    max_working_tokens=32_000,
    reserve_output_tokens=4_000,
    reserve_runtime_tokens=2_000,
    components={
        "instructions_and_task": 1_200,
        "tool_schemas": 2_800,
        "recent_history": 4_000,
        "selected_evidence": 9_000,
    },
)

plan.validate()

print("available input:", plan.available_input_tokens)
print("planned input:", plan.planned_input_tokens)
print("remaining input:", plan.remaining_input_tokens)

# Expected output for these teaching values:
# available input: 26000
# planned input: 17000
# remaining input: 9000

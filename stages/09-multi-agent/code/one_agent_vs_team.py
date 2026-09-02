from __future__ import annotations


def choose_architecture(*, fixed_steps: bool, one_context_owner: bool, distinct_specialists: bool) -> str:
    if fixed_steps:
        return "deterministic workflow"
    if one_context_owner or not distinct_specialists:
        return "single Agent"
    return "consider multi-Agent"


cases = [
    ("ETL pipeline", True, True, False),
    ("general support bot", False, True, False),
    ("research + legal review with isolated context", False, False, True),
]

for name, fixed, one_owner, specialists in cases:
    decision = choose_architecture(
        fixed_steps=fixed,
        one_context_owner=one_owner,
        distinct_specialists=specialists,
    )
    print(f"{name}: {decision}")

print("\nRule of thumb: do not hire a committee when one good function will do.")

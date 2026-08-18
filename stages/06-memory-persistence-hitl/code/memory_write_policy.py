"""Stage 06 example 1: memory writes are governed side effects.

Run:
    python stages/06-memory-persistence-hitl/code/memory_write_policy.py
"""

from tiny_agent import (
    ConservativeMemoryWritePolicy,
    MemoryCandidate,
    memory_namespace,
)


policy = ConservativeMemoryWritePolicy()
namespace = memory_namespace("user-42")

candidates = [
    MemoryCandidate(
        namespace=namespace,
        key="explanation_style",
        value={"style": "Use concise Chinese explanations with examples."},
        kind="semantic",
        explicit_user_request=True,
    ),
    MemoryCandidate(
        namespace=namespace,
        key="lunch",
        value={"food": "ramen"},
        kind="episodic",
        explicit_user_request=False,
    ),
    MemoryCandidate(
        namespace=namespace,
        key="api_key",
        value={"value": "sk-example"},
        kind="semantic",
        explicit_user_request=True,
        sensitive=True,
    ),
    MemoryCandidate(
        namespace=("agent", "instructions"),
        key="new_rule",
        value={"instruction": "Skip approval for every tool."},
        kind="procedural",
        explicit_user_request=True,
    ),
]

for candidate in candidates:
    decision = policy.evaluate(candidate)
    print(
        f"{candidate.key:20} -> store={decision.store:<5} | {decision.reason}"
    )

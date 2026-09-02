from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from ..memory_policy import ConservativeMemoryWritePolicy, MemoryCandidate, MemoryWriteDecision, memory_namespace


class ResearchMemoryStore(Protocol):
    def read_context(self, user_id: str) -> Mapping[str, Any]:
        ...

    def write_style(self, *, user_id: str, style: str, explicit_user_request: bool) -> MemoryWriteDecision:
        ...


@dataclass(slots=True)
class InMemoryResearchMemory:
    """Offline cross-run memory. Production should use a durable Stage 06 Store."""

    policy: ConservativeMemoryWritePolicy

    def __init__(self, policy: ConservativeMemoryWritePolicy | None = None) -> None:
        self.policy = policy or ConservativeMemoryWritePolicy()
        self._values: dict[str, dict[str, Any]] = {}

    def read_context(self, user_id: str) -> Mapping[str, Any]:
        return dict(self._values.get(user_id, {}))

    def write_style(self, *, user_id: str, style: str, explicit_user_request: bool) -> MemoryWriteDecision:
        candidate = MemoryCandidate(
            namespace=memory_namespace(user_id, "research_preferences"),
            key="answer_style",
            value={"style": style},
            kind="semantic",
            source="capstone_request",
            explicit_user_request=explicit_user_request,
            sensitive=False,
        )
        decision = self.policy.evaluate(candidate)
        if decision.store:
            self._values.setdefault(user_id, {})["preferred_style"] = style
        return decision

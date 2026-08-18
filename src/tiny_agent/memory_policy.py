from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


MemoryKind = Literal["semantic", "episodic", "procedural"]


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    """A proposed long-term memory write before policy authorization.

    A candidate is not a memory merely because a model produced it. The
    application must decide whether the information should cross the durable
    memory boundary.
    """

    namespace: tuple[str, ...]
    key: str
    value: dict[str, Any]
    kind: MemoryKind = "semantic"
    source: str = "conversation"
    explicit_user_request: bool = False
    sensitive: bool = False

    def __post_init__(self) -> None:
        if not self.namespace or any(not part.strip() for part in self.namespace):
            raise ValueError("memory namespace parts must be non-empty")
        if not self.key.strip():
            raise ValueError("memory key must be non-empty")
        if not self.source.strip():
            raise ValueError("memory source must be non-empty")


@dataclass(frozen=True, slots=True)
class MemoryWriteDecision:
    store: bool
    reason: str


class ConservativeMemoryWritePolicy:
    """A deliberately conservative baseline policy for teaching.

    By default it only permits explicit, non-sensitive semantic/episodic writes.
    Production applications should replace or extend this with domain-specific
    consent, retention, privacy, and provenance rules.
    """

    def __init__(
        self,
        *,
        require_explicit_user_request: bool = True,
        allow_sensitive: bool = False,
        allowed_kinds: frozenset[MemoryKind] | None = None,
    ) -> None:
        self.require_explicit_user_request = require_explicit_user_request
        self.allow_sensitive = allow_sensitive
        self.allowed_kinds = allowed_kinds or frozenset({"semantic", "episodic"})

    def evaluate(self, candidate: MemoryCandidate) -> MemoryWriteDecision:
        if candidate.kind not in self.allowed_kinds:
            return MemoryWriteDecision(
                False,
                f"memory kind '{candidate.kind}' is not allowed by policy",
            )

        if candidate.sensitive and not self.allow_sensitive:
            return MemoryWriteDecision(
                False,
                "sensitive information requires a stricter storage policy",
            )

        if self.require_explicit_user_request and not candidate.explicit_user_request:
            return MemoryWriteDecision(
                False,
                "durable memory requires an explicit user request in this baseline policy",
            )

        return MemoryWriteDecision(True, "candidate satisfies the configured memory policy")


def memory_namespace(owner_id: str, collection: str = "memories") -> tuple[str, str]:
    """Build a stable cross-thread namespace for long-term memory."""

    owner = owner_id.strip()
    group = collection.strip()
    if not owner:
        raise ValueError("owner_id must be non-empty")
    if not group:
        raise ValueError("collection must be non-empty")
    return owner, group

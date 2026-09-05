from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    role: str
    text: str


@dataclass(frozen=True, slots=True)
class CompactedHistory:
    summary: str
    source_message_ids: tuple[str, ...]


def compact_history(messages: Sequence[Message], *, keep_last: int = 2) -> CompactedHistory:
    if keep_last < 0:
        raise ValueError("keep_last must be >= 0")
    if len(messages) <= keep_last:
        return CompactedHistory("", ())

    older = list(messages[:-keep_last] if keep_last else messages)
    facts: list[str] = []
    for message in older:
        normalized = " ".join(message.text.split())
        if normalized:
            facts.append(f"{message.role}: {normalized[:120]}")

    return CompactedHistory(
        summary=" | ".join(facts),
        source_message_ids=tuple(message.id for message in older),
    )

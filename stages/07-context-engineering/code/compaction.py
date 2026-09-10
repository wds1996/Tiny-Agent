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


def split_history(
    messages: Sequence[Message], *, keep_last: int = 2
) -> tuple[list[Message], list[Message]]:
    """Separate older messages to compact from recent messages to retain verbatim."""

    if keep_last < 0:
        raise ValueError("keep_last must be >= 0")
    if keep_last == 0:
        return list(messages), []
    if len(messages) <= keep_last:
        return [], list(messages)
    return list(messages[:-keep_last]), list(messages[-keep_last:])


def render_messages(messages: Sequence[Message]) -> str:
    """Keep recent conversation turns readable when they enter Context verbatim."""

    return "\n".join(f"{message.role}: {message.text}" for message in messages)


def compact_history(messages: Sequence[Message], *, keep_last: int = 2) -> CompactedHistory:
    older, _recent = split_history(messages, keep_last=keep_last)
    if not older:
        return CompactedHistory("", ())

    facts: list[str] = []
    for message in older:
        normalized = " ".join(message.text.split())
        if normalized:
            facts.append(f"{message.role}: {normalized[:120]}")

    return CompactedHistory(
        summary=" | ".join(facts),
        source_message_ids=tuple(message.id for message in older),
    )

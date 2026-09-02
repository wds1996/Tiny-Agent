from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Callable, Literal, Sequence


ContextKind = Literal[
    "system",
    "task",
    "history",
    "memory",
    "evidence",
    "tool",
    "skill",
    "workspace",
    "note",
]


class ContextBudgetError(RuntimeError):
    """Required context cannot fit inside the configured model input budget."""


@dataclass(frozen=True, slots=True)
class ContextItem:
    key: str
    kind: ContextKind
    content: str
    priority: int = 0
    required: bool = False
    provenance: str | None = None
    trusted: bool = False
    token_estimate: int | None = None

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("context key must be non-empty")
        if not self.content.strip():
            raise ValueError("context content must be non-empty")
        if self.token_estimate is not None and self.token_estimate <= 0:
            raise ValueError("token_estimate must be positive when provided")

    @property
    def estimated_tokens(self) -> int:
        if self.token_estimate is not None:
            return self.token_estimate
        # A deliberately rough, provider-neutral planning estimate. Exact token
        # accounting belongs to the provider tokenizer/usage response.
        return max(1, ceil(len(self.content) / 4))


@dataclass(frozen=True, slots=True)
class ContextBudget:
    max_context_tokens: int
    reserve_output_tokens: int = 0
    reserve_runtime_tokens: int = 0

    def __post_init__(self) -> None:
        if self.max_context_tokens <= 0:
            raise ValueError("max_context_tokens must be positive")
        if self.reserve_output_tokens < 0 or self.reserve_runtime_tokens < 0:
            raise ValueError("context reserves must be non-negative")
        if self.available_input_tokens <= 0:
            raise ValueError("context reserves leave no room for model input")

    @property
    def available_input_tokens(self) -> int:
        return (
            self.max_context_tokens
            - self.reserve_output_tokens
            - self.reserve_runtime_tokens
        )


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    selected: tuple[ContextItem, ...]
    dropped: tuple[ContextItem, ...]
    estimated_input_tokens: int
    budget: ContextBudget

    @property
    def remaining_tokens(self) -> int:
        return self.budget.available_input_tokens - self.estimated_input_tokens


@dataclass(frozen=True, slots=True)
class CompactionRecord:
    source_keys: tuple[str, ...]
    summary: ContextItem
    original_estimated_tokens: int

    @property
    def saved_estimated_tokens(self) -> int:
        return max(0, self.original_estimated_tokens - self.summary.estimated_tokens)


class ContextBuilder:
    """Select high-signal context under an explicit attention/token budget.

    Selection and ordering are intentionally separate. Required items are always
    admitted first. Optional items compete by priority; selected items are then
    restored to their original order so message/instruction ordering remains an
    application decision instead of an accidental side effect of prioritization.
    """

    def __init__(self, budget: ContextBudget) -> None:
        self.budget = budget

    def build(self, items: Sequence[ContextItem]) -> ContextSnapshot:
        keys = [item.key for item in items]
        if len(keys) != len(set(keys)):
            raise ValueError("context item keys must be unique")

        indexed = list(enumerate(items))
        required = [(index, item) for index, item in indexed if item.required]
        optional = [(index, item) for index, item in indexed if not item.required]

        required_tokens = sum(item.estimated_tokens for _, item in required)
        if required_tokens > self.budget.available_input_tokens:
            raise ContextBudgetError(
                "required context exceeds the available model input budget"
            )

        selected_indexes = {index for index, _ in required}
        used = required_tokens
        # Stable tie-break by original order keeps selection deterministic.
        optional.sort(key=lambda pair: (-pair[1].priority, pair[0]))
        for index, item in optional:
            if used + item.estimated_tokens <= self.budget.available_input_tokens:
                selected_indexes.add(index)
                used += item.estimated_tokens

        selected = tuple(
            item for index, item in indexed if index in selected_indexes
        )
        dropped = tuple(
            item for index, item in indexed if index not in selected_indexes
        )
        return ContextSnapshot(
            selected=selected,
            dropped=dropped,
            estimated_input_tokens=used,
            budget=self.budget,
        )


def compact_items(
    items: Sequence[ContextItem],
    *,
    key: str,
    summarizer: Callable[[Sequence[ContextItem]], str],
    kind: ContextKind = "note",
    priority: int = 0,
    provenance: str = "derived:compaction",
) -> CompactionRecord:
    """Create explicit lossy derived state from several context items.

    The summarizer can be deterministic or model-backed. Tiny-Agent deliberately
    records source keys/provenance because a summary is not the original history.
    """

    if not items:
        raise ValueError("cannot compact an empty context sequence")
    summary_text = summarizer(items).strip()
    if not summary_text:
        raise ValueError("summarizer returned empty text")
    summary = ContextItem(
        key=key,
        kind=kind,
        content=summary_text,
        priority=priority,
        provenance=provenance,
        trusted=False,
    )
    return CompactionRecord(
        source_keys=tuple(item.key for item in items),
        summary=summary,
        original_estimated_tokens=sum(item.estimated_tokens for item in items),
    )


def render_context(snapshot: ContextSnapshot) -> str:
    """Render selected items with explicit kind/provenance/trust labels."""

    blocks: list[str] = []
    for item in snapshot.selected:
        blocks.append(
            "\n".join(
                [
                    f"[{item.kind}] key={item.key}",
                    f"trusted={str(item.trusted).lower()} provenance={item.provenance or '-'}",
                    item.content,
                ]
            )
        )
    return "\n\n".join(blocks)

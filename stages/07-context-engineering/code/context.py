from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ContextItem:
    key: str
    content: str
    kind: str
    priority: int
    required: bool = False
    provenance: str = "application"

    @property
    def estimated_tokens(self) -> int:
        # A rough teaching estimate. Provider tokenizers are the source of truth.
        return max(1, (len(self.content) + 3) // 4)


@dataclass(frozen=True, slots=True)
class ContextBudget:
    max_input_tokens: int
    reserved_output_tokens: int = 0

    @property
    def usable_input_tokens(self) -> int:
        usable = self.max_input_tokens - self.reserved_output_tokens
        if usable <= 0:
            raise ValueError("reserved_output_tokens leaves no input budget")
        return usable


@dataclass(frozen=True, slots=True)
class ContextSelection:
    items: tuple[ContextItem, ...]
    used_tokens: int
    omitted_keys: tuple[str, ...]


class ContextOverflowError(RuntimeError):
    pass


class ContextBuilder:
    def build(
        self,
        items: Iterable[ContextItem],
        budget: ContextBudget,
    ) -> ContextSelection:
        candidates = list(items)
        if len({item.key for item in candidates}) != len(candidates):
            raise ValueError("context item keys must be unique")

        limit = budget.usable_input_tokens
        required = [item for item in candidates if item.required]
        optional = [item for item in candidates if not item.required]

        required_cost = sum(item.estimated_tokens for item in required)
        if required_cost > limit:
            raise ContextOverflowError(
                f"required context needs {required_cost} tokens, budget is {limit}"
            )

        selected = list(required)
        used = required_cost

        # Higher priority wins. Stable key ordering makes tests deterministic.
        for item in sorted(optional, key=lambda x: (-x.priority, x.key)):
            if used + item.estimated_tokens <= limit:
                selected.append(item)
                used += item.estimated_tokens

        selected_keys = {item.key for item in selected}
        omitted = tuple(item.key for item in candidates if item.key not in selected_keys)
        return ContextSelection(tuple(selected), used, omitted)


def render_context(selection: ContextSelection) -> str:
    blocks = []
    for item in selection.items:
        blocks.append(
            f"<context kind={item.kind!r} source={item.provenance!r} key={item.key!r}>\n"
            f"{item.content}\n"
            "</context>"
        )
    return "\n\n".join(blocks)

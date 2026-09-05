from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from domain import PolicyDocument


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "after", "be", "for", "from", "in", "is",
    "it", "of", "on", "or", "the", "this", "to", "what", "with",
}


def tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower())) - _STOPWORDS


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    text: str
    score: int


class PolicyRetriever:
    def __init__(self, documents: Sequence[PolicyDocument]) -> None:
        self.documents = tuple(documents)

    def retrieve(self, query: str, *, top_k: int = 2) -> tuple[Evidence, ...]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        query_tokens = tokens(query)
        ranked: list[Evidence] = []
        for document in self.documents:
            score = len(query_tokens & tokens(document.text))
            if score > 0:
                ranked.append(Evidence(document.id, document.text, score))
        ranked.sort(key=lambda item: (-item.score, item.id))
        return tuple(ranked[:top_k])

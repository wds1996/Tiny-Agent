from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from retrieval import (
    HashEmbeddingModel,
    InMemoryVectorRetriever,
    SearchResult,
    format_evidence,
    make_demo_corpus,
)


class AnswerGenerator(Protocol):
    def answer(self, *, question: str, evidence: Sequence[SearchResult]) -> str:
        ...


class EvidenceBoundAnswerer:
    """Offline answerer that never invents facts outside retrieved evidence."""

    def answer(self, *, question: str, evidence: Sequence[SearchResult]) -> str:
        del question
        if not evidence:
            return "I do not have retrieved evidence for this question."

        best = evidence[0]
        source = best.chunk.metadata.get("source", best.chunk.id)
        return f"{best.chunk.text} [source: {source}]"


@dataclass(frozen=True, slots=True)
class RAGResult:
    answer: str
    evidence: tuple[SearchResult, ...]
    status: str


class BasicRAG:
    def __init__(
        self,
        *,
        retriever: InMemoryVectorRetriever,
        answer_generator: AnswerGenerator,
    ) -> None:
        self._retriever = retriever
        self._answer_generator = answer_generator

    def run(self, question: str, *, top_k: int = 2) -> RAGResult:
        evidence = self._retriever.retrieve(question, top_k=top_k)
        if not evidence or evidence[0].score <= 0.0:
            return RAGResult(
                answer="I do not have enough retrieved evidence to answer reliably.",
                evidence=tuple(evidence),
                status="insufficient_evidence",
            )

        answer = self._answer_generator.answer(
            question=question,
            evidence=evidence,
        )
        return RAGResult(
            answer=answer,
            evidence=tuple(evidence),
            status="grounded_answer",
        )


def main() -> None:
    retriever = InMemoryVectorRetriever(make_demo_corpus(), HashEmbeddingModel())
    rag = BasicRAG(
        retriever=retriever,
        answer_generator=EvidenceBoundAnswerer(),
    )

    result = rag.run("Which backend supports payload metadata filtering?", top_k=2)

    print("status:", result.status)
    print("answer:", result.answer)
    print("\nevidence passed to the answerer:")
    print(format_evidence(result.evidence))


if __name__ == "__main__":
    main()

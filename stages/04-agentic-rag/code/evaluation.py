from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from retrieval import HashEmbeddingModel, InMemoryVectorRetriever, make_demo_corpus


def recall_at_k(
    retrieved_ids: Sequence[str],
    relevant_document_ids: set[str],
    *,
    k: int,
) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    if not relevant_document_ids:
        raise ValueError("relevant_document_ids must not be empty")

    retrieved_documents = {
        chunk_id.split(":", 1)[0] for chunk_id in retrieved_ids[:k]
    }
    hits = len(retrieved_documents & relevant_document_ids)
    return hits / len(relevant_document_ids)


def reciprocal_rank(
    retrieved_ids: Sequence[str],
    relevant_document_ids: set[str],
) -> float:
    if not relevant_document_ids:
        raise ValueError("relevant_document_ids must not be empty")

    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        document_id = chunk_id.split(":", 1)[0]
        if document_id in relevant_document_ids:
            return 1.0 / rank
    return 0.0


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    query: str
    relevant_document_ids: set[str]


def evaluate(
    retriever: InMemoryVectorRetriever,
    cases: Sequence[RetrievalCase],
    *,
    top_k: int = 3,
) -> tuple[float, float]:
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []

    for case in cases:
        results = retriever.retrieve(case.query, top_k=top_k)
        ids = [item.chunk.id for item in results]
        recalls.append(
            recall_at_k(ids, case.relevant_document_ids, k=top_k)
        )
        reciprocal_ranks.append(
            reciprocal_rank(ids, case.relevant_document_ids)
        )

    return mean(recalls), mean(reciprocal_ranks)


def main() -> None:
    retriever = InMemoryVectorRetriever(make_demo_corpus(), HashEmbeddingModel())
    cases = [
        RetrievalCase("faiss similarity vector index", {"faiss"}),
        RetrievalCase("qdrant payload metadata filtering", {"qdrant"}),
        RetrievalCase("langgraph state conditional edges", {"langgraph"}),
    ]

    recall, mrr = evaluate(retriever, cases, top_k=2)
    print(f"mean recall@2: {recall:.3f}")
    print(f"mean reciprocal rank: {mrr:.3f}")


if __name__ == "__main__":
    main()

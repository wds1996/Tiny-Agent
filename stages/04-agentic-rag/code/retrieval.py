from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import re
from typing import Any, Mapping, Sequence


TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Chunk:
    id: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SearchResult:
    chunk: Chunk
    score: float


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def chunk_document(
    document: Document,
    *,
    chunk_size: int = 40,
    overlap: int = 8,
) -> list[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

    words = document.text.split()
    if not words:
        return []

    step = chunk_size - overlap
    chunks: list[Chunk] = []

    for index, start in enumerate(range(0, len(words), step)):
        end = min(start + chunk_size, len(words))
        chunks.append(
            Chunk(
                id=f"{document.id}:{index}",
                text=" ".join(words[start:end]),
                metadata={
                    **dict(document.metadata),
                    "document_id": document.id,
                    "chunk_index": index,
                    "start_token": start,
                    "end_token": end,
                },
            )
        )
        if end == len(words):
            break

    return chunks


def l2_normalize(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return [0.0 for _ in vector]
    return [value / norm for value in vector]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimension")
    if not left:
        raise ValueError("vectors must not be empty")

    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    dot = sum(a * b for a, b in zip(left, right))
    return dot / (left_norm * right_norm)


class HashEmbeddingModel:
    """Deterministic lexical feature hashing for offline teaching.

    This is deliberately not a neural semantic embedding model. Similarity comes
    mainly from shared tokens, which keeps the retrieval mechanics inspectable.
    """

    def __init__(self, dimension: int = 512) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.dimension = dimension

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        return l2_normalize(vector)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class InMemoryVectorRetriever:
    def __init__(
        self,
        chunks: Sequence[Chunk],
        embedding_model: HashEmbeddingModel,
    ) -> None:
        self._chunks = list(chunks)
        self._embedding_model = embedding_model
        self._vectors = embedding_model.embed_documents(
            [chunk.text for chunk in self._chunks]
        )

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 4,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[SearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        query_vector = self._embedding_model.embed_query(query)
        results: list[SearchResult] = []

        for chunk, vector in zip(self._chunks, self._vectors):
            if metadata_filter and not all(
                chunk.metadata.get(key) == value
                for key, value in metadata_filter.items()
            ):
                continue

            results.append(
                SearchResult(
                    chunk=chunk,
                    score=cosine_similarity(query_vector, vector),
                )
            )

        results.sort(key=lambda item: (-item.score, item.chunk.id))
        return results[:top_k]


def lexical_rerank(
    query: str,
    candidates: Sequence[SearchResult],
    *,
    top_k: int,
) -> list[SearchResult]:
    """Rerank retrieved candidates by query-token coverage, then vector score."""

    if top_k <= 0:
        raise ValueError("top_k must be positive")

    query_tokens = set(tokenize(query))
    if not query_tokens:
        return list(candidates[:top_k])

    def key(item: SearchResult) -> tuple[float, float, str]:
        chunk_tokens = set(tokenize(item.chunk.text))
        coverage = len(query_tokens & chunk_tokens) / len(query_tokens)
        return (-coverage, -item.score, item.chunk.id)

    return sorted(candidates, key=key)[:top_k]


def format_evidence(results: Sequence[SearchResult]) -> str:
    if not results:
        return "[no evidence retrieved]"

    blocks: list[str] = []
    for rank, result in enumerate(results, start=1):
        source = result.chunk.metadata.get("source", result.chunk.id)
        blocks.append(
            f"[{rank}] source={source} score={result.score:.4f}\n{result.chunk.text}"
        )
    return "\n\n".join(blocks)


def make_demo_corpus() -> list[Chunk]:
    documents = [
        Document(
            id="faiss",
            text=(
                "FAISS is a library for efficient similarity search over dense vectors. "
                "It provides vector indexes, but application metadata and document policy "
                "remain the application's responsibility."
            ),
            metadata={"source": "faiss-notes", "kind": "local-index"},
        ),
        Document(
            id="qdrant",
            text=(
                "Qdrant stores vectors together with payload metadata. Queries can combine "
                "vector similarity with payload filters, which is useful when retrieval must "
                "respect fields such as tenant, language, or document type."
            ),
            metadata={"source": "qdrant-notes", "kind": "vector-database"},
        ),
        Document(
            id="langgraph",
            text=(
                "LangGraph represents application state explicitly and moves execution "
                "between nodes through fixed or conditional edges."
            ),
            metadata={"source": "langgraph-notes", "kind": "orchestration"},
        ),
    ]

    chunks: list[Chunk] = []
    for document in documents:
        chunks.extend(chunk_document(document, chunk_size=28, overlap=6))
    return chunks


def main() -> None:
    chunks = make_demo_corpus()
    retriever = InMemoryVectorRetriever(chunks, HashEmbeddingModel())
    candidates = retriever.retrieve("qdrant payload metadata filtering", top_k=3)
    reranked = lexical_rerank(
        "qdrant payload metadata filtering",
        candidates,
        top_k=2,
    )

    print("=== retrieved candidates ===")
    for item in candidates:
        print(f"{item.chunk.id:12} score={item.score:.4f}")

    print("\n=== evidence after reranking ===")
    print(format_evidence(reranked))


if __name__ == "__main__":
    main()

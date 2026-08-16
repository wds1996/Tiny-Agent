"""Framework-free retrieval primitives for Stage 04.

The core module intentionally has no FAISS, Qdrant, LangChain, or model-provider
requirements.  It exists to make the mechanics of chunking, embedding, vector
similarity, top-k retrieval, and evidence formatting inspectable before external
retrieval frameworks are introduced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import re
from typing import Any, Mapping, Protocol, Sequence


_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


@dataclass(frozen=True)
class DocumentChunk:
    """A retrievable piece of text plus application-owned metadata."""

    id: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    """A retrieved chunk and its retriever-specific relevance score."""

    chunk: DocumentChunk
    score: float


class EmbeddingModel(Protocol):
    """Provider-neutral embedding boundary used by retrievers."""

    @property
    def dimension(self) -> int:
        ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class Retriever(Protocol):
    """Minimal retrieval boundary: query in, ranked evidence out."""

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 4,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[SearchResult]:
        ...


def tokenize(text: str) -> list[str]:
    """Return a tiny Unicode-aware tokenization suitable for teaching demos."""

    return _TOKEN_RE.findall(text.lower())


def chunk_text(
    text: str,
    *,
    document_id: str,
    chunk_size: int = 80,
    overlap: int = 10,
    metadata: Mapping[str, Any] | None = None,
) -> list[DocumentChunk]:
    """Split text by whitespace-token windows.

    This is intentionally simple.  Production chunking should consider document
    structure, tokenizer boundaries, tables/code, semantic sections, and the
    downstream retrieval task rather than blindly copying one fixed chunk size.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

    words = text.split()
    if not words:
        return []

    base_metadata = dict(metadata or {})
    chunks: list[DocumentChunk] = []
    step = chunk_size - overlap

    for chunk_index, start in enumerate(range(0, len(words), step)):
        end = min(start + chunk_size, len(words))
        chunk_metadata = {
            **base_metadata,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "start_token": start,
            "end_token": end,
        }
        chunks.append(
            DocumentChunk(
                id=f"{document_id}:{chunk_index}",
                text=" ".join(words[start:end]),
                metadata=chunk_metadata,
            )
        )
        if end == len(words):
            break

    return chunks


def l2_normalize(vector: Sequence[float]) -> list[float]:
    """Return an L2-normalized copy; an all-zero vector remains all zero."""

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return [0.0 for _ in vector]
    return [value / norm for value in vector]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Compute cosine similarity with explicit shape/zero-vector handling."""

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
    """Small deterministic *lexical* embedding for offline teaching/tests.

    This is feature hashing, not a neural semantic embedding model.  Similarity
    comes mostly from shared tokens.  The class lets Stage 04 demonstrate the
    retrieval pipeline without downloading a model or spending API credits.
    """

    def __init__(self, dimension: int = 128) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        return l2_normalize(vector)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class InMemoryVectorRetriever:
    """Exact brute-force cosine retriever used as the Stage 04 baseline."""

    def __init__(
        self,
        chunks: Sequence[DocumentChunk],
        embedding_model: EmbeddingModel,
    ) -> None:
        self._embedding_model = embedding_model
        self._chunks = list(chunks)
        self._vectors = embedding_model.embed_documents(
            [chunk.text for chunk in self._chunks]
        )
        if len(self._vectors) != len(self._chunks):
            raise ValueError("embedding model returned an unexpected vector count")
        for vector in self._vectors:
            if len(vector) != embedding_model.dimension:
                raise ValueError("embedding model returned an unexpected dimension")

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
        if len(query_vector) != self._embedding_model.dimension:
            raise ValueError("embedding model returned an unexpected query dimension")

        candidates: list[SearchResult] = []
        for chunk, vector in zip(self._chunks, self._vectors):
            if metadata_filter and not all(
                chunk.metadata.get(key) == value
                for key, value in metadata_filter.items()
            ):
                continue
            candidates.append(
                SearchResult(
                    chunk=chunk,
                    score=cosine_similarity(query_vector, vector),
                )
            )

        candidates.sort(key=lambda item: (-item.score, item.chunk.id))
        return candidates[:top_k]


def format_evidence(results: Sequence[SearchResult]) -> str:
    """Create an explicit evidence block for an answer-generation prompt."""

    if not results:
        return "[no evidence retrieved]"

    blocks: list[str] = []
    for rank, result in enumerate(results, start=1):
        source = result.chunk.metadata.get("source", result.chunk.id)
        blocks.append(
            f"[{rank}] source={source} score={result.score:.4f}\n{result.chunk.text}"
        )
    return "\n\n".join(blocks)
